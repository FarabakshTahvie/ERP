from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from accounts.models import User
from core.capabilities import CAPABILITIES, can, capabilities_for
from core.models import Specialty

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
    "purchases.create": MGR | {"warehouse", "accountant"},
    "projects.create": MGR | {"reception", "accountant"},
    "broadcast.use": MGR | {"accountant", "reception"},
    "messenger.use": MGR | {"accountant", "reception", "warehouse", "installer"},
    "messenger.reach_all": MGR_ACC,
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

    def test_unknown_capability_raises(self):
        with self.assertRaises(KeyError):
            can(self.people["manager"], "nope.nope")
