from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from core.models import Party
from utils.utils import normalize_phone
from inventory.services import create_purchase_from_form
from projects.services import create_project_from_technician_intake
from projects.models import Project
from django.contrib.auth import get_user_model

User = get_user_model()

class PhoneNormalizeTests(TestCase):
    def test_normalize_phone_logic(self):
        pairs = [
            ("۰۹۱۲۳۴۵۶۷۸۹", "09123456789"),
            ("٠٩١٢٣٤٥٦٧٨٩", "09123456789"),
            ("+98 912 345 6789", "09123456789"),
            ("0098-912-345-6789", "09123456789"),
            ("05133873734", "05133873734"),
            (None, ""),
        ]
        for raw, expected in pairs:
            self.assertEqual(normalize_phone(raw), expected)

    def test_party_save_normalizes_data(self):
        party = Party.objects.create(
            name="الف", is_client=True, 
            phone_number="۰۹۱۲۳۴۵۶۷۸۹", national_code="۱۲۳"
        )
        party.refresh_from_db()
        self.assertEqual(party.phone_number, "09123456789")
        self.assertEqual(party.national_code, "123")

    def test_create_project_deduplication(self):
        user = User.objects.create_user(username="testuser")
        data = {
            "name": "طرف‌حساب تست", "entity_type": "individual",
            "phone_number": "۰۹۱۲۳۴۵۶۷۸۹", "national_code": "1234567890",
            "is_client": True
        }
        
        # اولین بار
        create_project_from_technician_intake(
            created_by=user, party_data=data, project_name="پروژه ۱"
        )
        self.assertEqual(Party.objects.count(), 1)
        
        # بار دوم با شماره لاتین
        data2 = data.copy()
        data2["phone_number"] = "09123456789"
        with self.assertRaises(ValueError):
            create_project_from_technician_intake(
                created_by=user, party_data=data2, project_name="پروژه ۲"
            )
        self.assertEqual(Party.objects.count(), 1)

    def test_create_purchase_deduplication(self):
        # این تست نیاز به setup انبار و کالا دارد که در بریف A انجام شد
        # برای سادگی اینجا حداقل موارد را می‌سازیم
        from inventory.models import Warehouse
        from catalog.models import Item, ItemCategory
        Warehouse.objects.create(name="انبار", is_default=True)
        cat = ItemCategory.objects.create(name="دسته")
        item = Item.objects.create(name="کالا", category=cat)
        
        data = {
            "name": "تامین‌کننده", "entity_type": "individual",
            "phone_number": "۰۹۱۲۳۴۵۶۷۸۹"
        }
        
        create_purchase_from_form(
            supplier_party_data=data,
            purchased_at=timezone.now(),
            lines_raw=[{"id": item.id, "qty": "1", "unit_cost": "1000"}]
        )
        self.assertEqual(Party.objects.filter(is_supplier=True).count(), 1)
        
        # بار دوم
        data2 = data.copy()
        data2["phone_number"] = "09123456789"
        with self.assertRaises(ValueError):
             create_purchase_from_form(
                supplier_party_data=data2,
                purchased_at=timezone.now(),
                lines_raw=[{"id": item.id, "qty": "1", "unit_cost": "1000"}]
            )
        self.assertEqual(Party.objects.filter(is_supplier=True).count(), 1)
