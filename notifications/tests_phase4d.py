from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Item
from core.models import Party, Specialty
from inventory.models import Warehouse
from inventory.services import consume_stock, receive_stock
from notifications.models import ChannelPolicy, Notification, NotificationPolicy, NotificationType
from notifications.services import notify_users, resend_notification
from projects.models import Project, ProjectStage, WorkflowStepTemplate, WorkflowTemplate
from projects.services import assign_stage, notify_stage_responsible


def SPEC(name):
    return Specialty.objects.get_or_create(name=name)[0]


class NotifyBase(TestCase):
    def setUp(self):
        mk = User.objects.create_user
        self.manager = mk(username="n_mgr", password="pw", role=User.Role.ADMIN)
        self.tech = mk(username="n_tech", password="pw", role=User.Role.EMPLOYEE)
        self.tech.specialties.add(SPEC("کانال‌کش"))
        self.other = mk(username="n_other", password="pw", role=User.Role.EMPLOYEE)
        self.other.specialties.add(SPEC("کانال‌کش"))
        self.keeper = mk(username="n_keeper", password="pw", role=User.Role.EMPLOYEE)
        self.keeper.specialties.add(SPEC("انباردار"))
        self.partner = Party.objects.create(name="شریک اعلان", is_partner=True, phone_number="09125559001")
        tpl = WorkflowTemplate.objects.create(name="قالب اعلان")
        self.step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="برش",
                                                        responsible_specialty=SPEC("کانال‌کش"))
        self.project = Project.objects.create(name="پروژه اعلان", partner=self.partner, workflow_template=tpl,
                                              status=Project.Status.IN_PROGRESS)

    def stage(self, **kw):
        return ProjectStage.objects.create(project=self.project, step_template=self.step, order=1, title="برش",
                                           status=ProjectStage.Status.IN_PROGRESS, started_at=timezone.now(), **kw)

    def note(self, user=None, ntype=NotificationType.MANUAL, status=Notification.Status.FAILED):
        return Notification.objects.create(user=user or self.tech, notification_type=ntype, title="عنوان",
                                           body="متن", status=status)


class SmsPolicyTests(NotifyBase):
    def test_sms_only_for_types_with_template(self):
        from notifications.services import send_sms_channel
        self.tech.phone_number = "09120000077"
        self.tech.save()
        n = self.note(ntype=NotificationType.STAGE_ASSIGNED, status=Notification.Status.PENDING)
        with mock.patch("notifications.services.SMSService") as sms:
            self.assertFalse(send_sms_channel(n))
        sms.assert_not_called()
        n.refresh_from_db()
        self.assertEqual(n.status, Notification.Status.PENDING)

    def test_invoice_sms_still_sent_and_password_cleared(self):
        from notifications.services import send_sms_channel
        self.tech.phone_number = "09120000078"
        self.tech.save()
        n = self.note(ntype=NotificationType.INVOICE_ISSUED, status=Notification.Status.PENDING)
        n.extra_data = {"invoice_number": "INV-1", "username": "u", "password": "Secret123"}
        n.save()
        with mock.patch("notifications.services.SMSService.send_invoice_issued", return_value={"success": True}) as m:
            self.assertTrue(send_sms_channel(n))
        m.assert_called_once()
        n.refresh_from_db()
        self.assertEqual((n.status, n.extra_data["password"]), (Notification.Status.SMS_SENT, ""))


class StageNotificationTests(NotifyBase):
    def test_assign_notifies_new_owner_after_commit(self):
        st = self.stage()
        with self.captureOnCommitCallbacks(execute=True):
            assign_stage(st, self.tech, self.manager, "فوری")
        n = Notification.objects.get(user=self.tech)
        self.assertEqual(n.notification_type, NotificationType.STAGE_ASSIGNED)
        self.assertEqual(n.real_target_url, f"/my-tasks/{st.id}/")

    def test_nothing_is_sent_before_commit(self):
        st = self.stage()
        assign_stage(st, self.tech, self.manager, "فوری")
        self.assertEqual(Notification.objects.count(), 0)


class WarehouseNotificationTests(NotifyBase):
    def test_low_stock_notifies_once_when_crossing(self):
        item = Item.objects.create(name="کالای کم", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE,
                                   reorder_point=5, responsible_user=self.keeper)
        wh = Warehouse.objects.create(name="انبار اعلان", is_default=True)
        receive_stock(item=item, warehouse=wh, qty=10, unit_cost=100, received_at=timezone.now())
        with self.captureOnCommitCallbacks(execute=True):
            consume_stock(item=item, qty=3)          # ۷
        self.assertEqual(Notification.objects.count(), 0)
        with self.captureOnCommitCallbacks(execute=True):
            consume_stock(item=item, qty=3)          # ۴: عبور از حد
        self.assertEqual(Notification.objects.filter(notification_type=NotificationType.LOW_STOCK).count(), 1)
        with self.captureOnCommitCallbacks(execute=True):
            consume_stock(item=item, qty=1)          # ۳: دوباره خبر نده
        self.assertEqual(Notification.objects.count(), 1)


class ResendTests(NotifyBase):
    def test_guards(self):
        n = self.note()
        with self.assertRaises(ValueError):
            resend_notification(n, actor=self.tech)
        with self.assertRaises(ValueError):
            resend_notification(self.note(ntype=NotificationType.INVOICE_ISSUED), actor=self.manager)
        with self.assertRaises(ValueError):
            resend_notification(self.note(status=Notification.Status.SEEN), actor=self.manager)

    def test_resend_dispatches_again(self):
        n = self.note()
        with mock.patch("notifications.services.dispatch_notification") as dispatch:
            resend_notification(n, actor=self.manager)
        dispatch.assert_called_once()
        n.refresh_from_db()
        self.assertEqual(n.status, Notification.Status.PENDING)


class CenterAndDashboardTests(NotifyBase):
    def test_center_shows_only_own_and_mark_seen_is_scoped(self):
        mine, theirs = self.note(self.tech, status=Notification.Status.PUSH_SENT), self.note(self.other)
        mine.title, theirs.title = "پیام من", "پیام دیگری"
        mine.save(); theirs.save()
        c = Client(); c.force_login(self.tech)
        resp = c.get(reverse("notifications:center"))
        self.assertContains(resp, "پیام من")
        self.assertNotContains(resp, "پیام دیگری")
        self.assertEqual(resp.context["unread_notifications_count"], 1)
        c.post(reverse("notifications:mark_all_seen"))
        mine.refresh_from_db(); theirs.refresh_from_db()
        self.assertIsNotNone(mine.seen_at)
        self.assertEqual(mine.status, Notification.Status.SEEN)
        self.assertIsNone(theirs.seen_at)

    def test_detail_never_shows_extra_data(self):
        n = self.note()
        n.extra_data = {"password": "SuperSecret123"}
        n.save()
        c = Client(); c.force_login(self.manager)
        self.assertNotContains(c.get(reverse("dashboard:notification_detail", args=[n.id])), "SuperSecret123")
