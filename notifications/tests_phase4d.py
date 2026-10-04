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
from projects.models import PartRequest, Project, ProjectStage, WorkflowStepTemplate, WorkflowTemplate
from projects.ops import notify_part_request
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


class PolicyCommandTests(NotifyBase):
    def test_creates_defaults_and_keeps_existing(self):
        NotificationPolicy.objects.update_or_create(
            notification_type=NotificationType.MANUAL,
            defaults={"channel_policy": ChannelPolicy.SMS_ONLY})
        call_command("setup_notification_policies")
        self.assertEqual(NotificationPolicy.objects.count(), 7)
        get = lambda t: NotificationPolicy.objects.get(notification_type=t).channel_policy
        self.assertEqual(get(NotificationType.MANUAL), ChannelPolicy.SMS_ONLY)
        self.assertEqual(get(NotificationType.STAGE_ASSIGNED), ChannelPolicy.PUSH_ONLY)

    def test_force_flag_resets_modified_policies(self):
        p, _ = NotificationPolicy.objects.update_or_create(
            notification_type=NotificationType.STAGE_ASSIGNED,
            defaults={"channel_policy": ChannelPolicy.SMS_ONLY, "fallback_after_minutes": 30})
        call_command("setup_notification_policies")
        self.assertEqual(NotificationPolicy.objects.get(notification_type=NotificationType.STAGE_ASSIGNED).channel_policy, ChannelPolicy.SMS_ONLY)
        call_command("setup_notification_policies", force=True)
        self.assertEqual(NotificationPolicy.objects.get(notification_type=NotificationType.STAGE_ASSIGNED).channel_policy, ChannelPolicy.PUSH_ONLY)


class SmsPolicyTests(NotifyBase):
    def test_no_device_is_in_app_not_failed(self):
        from notifications.services import send_push_channel
        n = self.note(status=Notification.Status.PENDING)
        self.assertFalse(send_push_channel(n))
        n.refresh_from_db()
        self.assertEqual(n.status, Notification.Status.IN_APP)

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

    def test_mark_all_seen_includes_in_app(self):
        n = self.note(self.tech, status=Notification.Status.IN_APP)
        c = Client(); c.force_login(self.tech)
        c.post(reverse("notifications:mark_all_seen"))
        n.refresh_from_db()
        self.assertEqual(n.status, Notification.Status.SEEN)


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

    def test_pool_members_all_notified_inactive_skipped(self):
        st = self.stage()
        st.candidate_users.add(self.tech, self.other)
        User.objects.filter(pk=self.other.pk).update(is_active=False)
        with self.captureOnCommitCallbacks(execute=True):
            notify_stage_responsible(st)
        self.assertEqual(list(Notification.objects.values_list("user_id", flat=True)), [self.tech.id])

    def test_notify_users_dedupes(self):
        with self.captureOnCommitCallbacks(execute=True):
            notify_users([self.tech, self.tech], notification_type=NotificationType.MANUAL, title="x", body="y")
        self.assertEqual(Notification.objects.count(), 1)


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

    def test_part_request_notifies_keepers_only(self):
        item = Item.objects.create(name="قطعه", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        st = self.stage()
        req = PartRequest.objects.create(project=self.project, stage=st, item=item, qty=Decimal("2"),
                                         note="کم آمد", requested_by=self.tech)
        with self.captureOnCommitCallbacks(execute=True):
            notify_part_request(req)
        self.assertEqual(list(Notification.objects.values_list("user_id", flat=True)), [self.keeper.id])


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

    def test_manager_pages_and_resend_view(self):
        n = self.note()
        urls = [reverse("dashboard:notifications"), reverse("dashboard:notifications_table"),
                reverse("dashboard:notification_detail", args=[n.id])]
        c = Client(); c.force_login(self.manager)
        for u in urls:
            self.assertEqual(c.get(u).status_code, 200, u)
        c.force_login(self.tech)
        for u in urls:
            self.assertEqual(c.get(u).status_code, 404, u)
        self.assertEqual(c.post(reverse("dashboard:notification_resend", args=[n.id])).status_code, 404)

    def test_detail_never_shows_extra_data(self):
        n = self.note()
        n.extra_data = {"password": "SuperSecret123"}
        n.save()
        c = Client(); c.force_login(self.manager)
        self.assertNotContains(c.get(reverse("dashboard:notification_detail", args=[n.id])), "SuperSecret123")
