from django.contrib.auth.models import AnonymousUser
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from core.capabilities import CAPABILITIES, can, capabilities_for
from core.models import Specialty
from inventory.services import WAREHOUSE_KEEPER_SPECIALTY_NAME, user_can_manage_inventory
from projects import ops
from projects.services import (
    ACCOUNTANT_SPECIALTY_NAME, INTAKE_SPECIALTY_NAME,
    can_edit_pricing, user_can_access_accounting, user_can_create_projects, user_is_accountant,
)

MGR = {"manager", "superuser"}
MGR_ACC = MGR | {"accountant"}
EXPECTED = {
    "dashboard.manager": MGR, "periods.unlock": MGR, "people.edit": MGR, "activity.view": MGR, "stages.assign": MGR,
    "admin.panel": MGR, "projects.cancel": MGR, "invoice.cancel": MGR, "notifications.manage": MGR,
    "projects.restore": MGR,
    "accounting.access": MGR_ACC, "payments.review": MGR_ACC, "pricing.edit": MGR_ACC, "costs.manage": MGR_ACC,
    "final_review.view": MGR_ACC, "money.view": MGR_ACC, "periods.lock": MGR_ACC, "invoice.adjust": MGR_ACC,
    "people.view": MGR_ACC, "suspended.view": MGR_ACC, "tasks.manage": MGR_ACC,
    "inventory.manage": {"warehouse", "accountant"},
    "projects.create": {"reception", "accountant"},
    "broadcast.use": MGR | {"accountant", "reception"},
}


def _employee(username, *specs):
    user = User.objects.create_user(username=username, password="pw", role=User.Role.EMPLOYEE)
    user.specialties.add(*[Specialty.objects.get_or_create(name=n)[0] for n in specs])
    return user


class CapabilityMatrixTests(TestCase):
    def setUp(self):
        self.people = {
            "manager": User.objects.create_user(username="cap_m", password="pw", role=User.Role.ADMIN),
            "superuser": User.objects.create_superuser(username="cap_su", password="pw"),
            "accountant": _employee("cap_acc", "حسابدار"),
            "reception": _employee("cap_rec", "پذیرش"),
            "warehouse": _employee("cap_wh", "انباردار"),
            "installer": _employee("cap_ins", "نصاب"),
            "client": User.objects.create_user(username="cap_cl", password="pw", role=User.Role.CLIENT),
            "anon": AnonymousUser(),
        }

    def test_every_capability_is_in_the_matrix(self):
        self.assertEqual(set(EXPECTED), set(CAPABILITIES))

    def test_matrix(self):
        for cap, allowed in EXPECTED.items():
            for who, user in self.people.items():
                self.assertEqual(can(user, cap), who in allowed, f"{cap} / {who}")

    def test_capabilities_for_matches_can(self):
        for who, user in self.people.items():
            self.assertEqual(capabilities_for(user), {c: can(user, c) for c in CAPABILITIES}, who)

    def test_legacy_wrappers_follow_the_table(self):
        for who, user in self.people.items():
            self.assertEqual(user_can_access_accounting(user), can(user, "accounting.access"), who)
            self.assertEqual(can_edit_pricing(user), can(user, "pricing.edit"), who)
            self.assertEqual(user_can_create_projects(user), can(user, "projects.create"), who)
            self.assertEqual(user_can_manage_inventory(user), can(user, "inventory.manage"), who)
            self.assertEqual(user_is_accountant(user), who == "accountant", who)
            self.assertEqual(ops.can_view_final_review(user, None), can(user, "final_review.view"), who)
            self.assertEqual(ops.can_manage_costs(user, None), can(user, "costs.manage"), who)

    def test_unknown_capability_raises(self):
        with self.assertRaises(KeyError):
            can(self.people["manager"], "nope.nope")

    def test_specialty_names_match_services(self):
        self.assertEqual(WAREHOUSE_KEEPER_SPECIALTY_NAME, "انباردار")
        self.assertEqual(ACCOUNTANT_SPECIALTY_NAME, "حسابدار")
        self.assertEqual(INTAKE_SPECIALTY_NAME, "پذیرش")

    def test_template_context_exposes_caps(self):
        client = Client()
        client.force_login(self.people["accountant"])
        resp = client.get(reverse("home"))
        self.assertTrue(resp.context["caps"]["accounting_access"])
        self.assertFalse(resp.context["caps"]["people_edit"])
