import json
from decimal import Decimal
from django.test import TestCase
from utils.line_editor import Col, parse_rows, BAD


class LineEditorTests(TestCase):
    def setUp(self):
        self.cols = (
            Col("name", "نام", "text", required=True),
            Col("qty", "مقدار", "number", required=True, positive=True),
            Col("price", "قیمت", "money", required=False),
            Col("flag", "وضعیت", "checkbox"),
            Col("choice", "انتخاب", "select", required=False, choices=("a", "b")),
        )

    def test_money_decimal_and_negative_rejected(self):
        raw = json.dumps([{"name": "تست", "qty": "1", "price": "100.5"}])
        with self.assertRaises(ValueError):
            parse_rows(raw, self.cols)

        raw2 = json.dumps([{"name": "تست", "qty": "1", "price": "-100"}])
        with self.assertRaises(ValueError):
            parse_rows(raw2, self.cols)
