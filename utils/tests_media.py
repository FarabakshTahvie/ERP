import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import Party, Specialty
from finance.models import Invoice, Payment
from projects.models import Project

User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProtectedMediaTests(TestCase):
    def setUp(self):
        self.media_root = Path(settings.MEDIA_ROOT) if hasattr(settings, 'MEDIA_ROOT') else Path(tempfile.gettempdir())
        self.manager = User.objects.create_user(username="m_admin", role=User.Role.ADMIN, password="pw")
        self.accountant = User.objects.create_user(username="m_acc", role=User.Role.EMPLOYEE, password="pw")
        self.accountant.specialties.add(Specialty.objects.get_or_create(name="حسابدار")[0])
        self.tech = User.objects.create_user(username="m_tech", role=User.Role.EMPLOYEE, password="pw")
        self.client_user = User.objects.create_user(username="m_client", role=User.Role.CLIENT, password="pw")
        self.party = Party.objects.create(name="مشتری", entity_type=Party.EntityType.INDIVIDUAL, is_client=True)
        self.client_user.party = self.party
        self.client_user.save()

        self.other_client_user = User.objects.create_user(username="m_other_client", role=User.Role.CLIENT, password="pw")
        self.other_party = Party.objects.create(name="سایر", entity_type=Party.EntityType.INDIVIDUAL, is_client=True)
        self.other_client_user.party = self.other_party
        self.other_client_user.save()

        self.project = Project.objects.create(name="پروژه تست", owner=self.party, partner=self.party)
        self.invoice = Invoice.objects.create(project=self.project, billed_party=self.party, total_amount=1000, issue_date=timezone.now())
        self.payment = Payment.objects.create(invoice=self.invoice, method=Payment.Method.RECEIPT, amount=1000, receipt_file="payments/receipts/test_rec.jpg")
        
        # Create test files
        (self.media_root / "payments" / "receipts").mkdir(parents=True, exist_ok=True)
        (self.media_root / "projects" / "1").mkdir(parents=True, exist_ok=True)
        (self.media_root / "avatars").mkdir(parents=True, exist_ok=True)
        
        with open(self.media_root / "payments" / "receipts" / "test_rec.jpg", "wb") as f:
            f.write(b"fake image data")
        with open(self.media_root / "projects" / "1" / "design.pdf", "wb") as f:
            f.write(b"%PDF-1.4 fake pdf")
        with open(self.media_root / "avatars" / "av.jpg", "wb") as f:
            f.write(b"avatar")
        with open(self.media_root / "projects" / "../../manage.py", "wb") as f:
            f.write(b"traversal")

    def tearDown(self):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get("/media/payments/receipts/test_rec.jpg")
        self.assertEqual(resp.status_code, 302)

    def test_payment_receipt_access(self):
        # Owner client can access
        self.client.force_login(self.client_user)
        resp = self.client.get("/media/payments/receipts/test_rec.jpg")
        self.assertEqual(resp.status_code, 200)

        # Other client gets 404
        self.client.force_login(self.other_client_user)
        resp = self.client.get("/media/payments/receipts/test_rec.jpg")
        self.assertEqual(resp.status_code, 404)

        # Accountant can access
        self.client.force_login(self.accountant)
        resp = self.client.get("/media/payments/receipts/test_rec.jpg")
        self.assertEqual(resp.status_code, 200)

        # Tech cannot access payment receipt unless accountant/manager
        self.client.force_login(self.tech)
        resp = self.client.get("/media/payments/receipts/test_rec.jpg")
        self.assertEqual(resp.status_code, 404)

    def test_project_file_access(self):
        # Client gets 404 for project files directly via media URL
        self.client.force_login(self.client_user)
        resp = self.client.get("/media/projects/1/design.pdf")
        self.assertEqual(resp.status_code, 404)

        # Tech gets 200
        self.client.force_login(self.tech)
        resp = self.client.get("/media/projects/1/design.pdf")
        self.assertEqual(resp.status_code, 200)

    def test_avatar_access(self):
        self.client.force_login(self.client_user)
        resp = self.client.get("/media/avatars/av.jpg")
        self.assertEqual(resp.status_code, 200)

    def test_path_traversal_blocked(self):
        secret = Path(settings.MEDIA_ROOT).parent / "fb_secret_guard.txt"
        secret.write_text("x", encoding="utf-8")
        try:
            self.client.force_login(self.manager)
            self.assertEqual(self.client.get("/media/projects/../../fb_secret_guard.txt").status_code, 404)
        finally:
            secret.unlink(missing_ok=True)

    def test_non_image_non_pdf_is_always_attachment(self):
        (self.media_root / "projects" / "1" / "page.html").write_bytes(b"<script>1</script>")
        self.client.force_login(self.tech)
        r = self.client.get("/media/projects/1/page.html")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertNotIn("attachment", self.client.get("/media/projects/1/design.pdf")["Content-Disposition"])

    def test_unknown_media_path_404(self):
        self.client.force_login(self.manager)
        resp = self.client.get("/media/secret/x.txt")
        self.assertEqual(resp.status_code, 404)
