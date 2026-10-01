import json
from decimal import Decimal
from django.test import TestCase
from utils.line_editor import Col, parse_row, parse_rows, BAD


class LineEditorTests(TestCase):
    def setUp(self):
        self.cols = (
            Col("name", "نام", "text", required=True),
            Col("qty", "مقدار", "number", required=True, positive=True),
            Col("price", "قیمت", "money", required=False),
            Col("flag", "وضعیت", "checkbox"),
            Col("choice", "انتخاب", "select", required=False, choices=("a", "b")),
        )

    def test_parse_rows_none_returns_none(self):
        self.assertIsNone(parse_rows(None, self.cols))

    def test_invalid_json_raises_value_error(self):
        with self.assertRaises(ValueError) as cm:
            parse_rows("not a json", self.cols)
        self.assertEqual(str(cm.exception), BAD)

    def test_fa_and_arabic_digits_and_commas(self):
        raw = json.dumps([{"name": "تست", "qty": "۱۲٫۵", "price": "۱٬۰۰۰"}])
        res = parse_rows(raw, self.cols)
        self.assertEqual(res[0]["qty"], Decimal("12.5"))
        self.assertEqual(res[0]["price"], Decimal("1000"))

    def test_money_decimal_and_negative_rejected(self):
        raw = json.dumps([{"name": "تست", "qty": "1", "price": "100.5"}])
        with self.assertRaises(ValueError):
            parse_rows(raw, self.cols)

        raw2 = json.dumps([{"name": "تست", "qty": "1", "price": "-100"}])
        with self.assertRaises(ValueError):
            parse_rows(raw2, self.cols)

    def test_children_rows(self):
        child_cols = (Col("title", "عنوان", "text"),)
        raw = json.dumps([{
            "name": "والد", "qty": "1", "kids": [{"title": "فرزند ۱"}, {"title": "فرزند ۲"}]
        }])
        res = parse_rows(raw, self.cols, children_key="kids", children_columns=child_cols)
        self.assertEqual(len(res[0]["kids"]), 2)
        self.assertEqual(res[0]["kids"][0]["title"], "فرزند ۱")

    def test_max_rows_limit(self):
        raw = json.dumps([{"name": "تست", "qty": "1"}] * 5)
        with self.assertRaises(ValueError):
            parse_rows(raw, self.cols, max_rows=4)
