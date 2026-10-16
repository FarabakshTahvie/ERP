from pathlib import Path
from django.conf import settings
from django.test import TestCase

BASE = Path(settings.BASE_DIR)


class SourceGuardTests(TestCase):
    def test_no_is_staff_for_decisions_in_finance_and_projects_views(self):
        for rel in ("finance/views.py", "finance/views_accounting.py", "projects/views.py", "projects/views_ops.py"):
            self.assertNotIn("is_staff", (BASE / rel).read_text(encoding="utf-8"), rel)

    def test_people_views_use_capabilities_not_roles(self):
        for rel in ("people/views.py", "people/services.py"):
            text = (BASE / rel).read_text(encoding="utf-8")
            self.assertNotIn("is_staff", text, rel)
        self.assertNotIn("is_staff", (BASE / "accounts" / "middleware.py").read_text(encoding="utf-8"))

    def test_select_for_update_with_select_related_needs_of(self):
        import ast
        problems = []
        for path in BASE.rglob("*.py"):
            if (any(p in path.parts for p in ("venv", ".venv", "node_modules", "migrations", "staticfiles"))
                    or path.name.startswith("tests")):
                continue
            src = path.read_text(encoding="utf-8")
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, (ast.Assign, ast.Expr, ast.Return, ast.AugAssign)):
                    seg = ast.get_source_segment(src, node) or ""
                    if "select_for_update()" in seg and "select_related(" in seg:
                        problems.append(f"{path.relative_to(BASE)}:{node.lineno}")
        self.assertEqual(problems, [])

    def test_sms_send_text_usage_guard(self):
        """send_text( فقط در utils/sms.py، core/management/commands/send_test_sms.py و notifications/broadcast.py مجاز است."""
        allowed = {
            "utils/sms.py",
            "core/management/commands/send_test_sms.py",
            "notifications/broadcast.py",
            "notifications/management/commands/process_broadcasts.py"
        }
        violations = []
        for path in BASE.rglob("*.py"):
            if (any(p in path.parts for p in ("venv", ".venv", "node_modules", "migrations", "staticfiles"))
                    or path.name.startswith("test")):
                continue
            rel = str(path.relative_to(BASE)).replace("\\", "/")
            if rel in allowed:
                continue
            text = path.read_text(encoding="utf-8")
            if "send_text(" in text:
                violations.append(rel)
        self.assertEqual(violations, [])

    def test_no_public_broadcast_image_route(self):
        from django.test import Client
        self.assertEqual(Client().get("/b/" + "a" * 32 + ".jpg").status_code, 404)
        self.assertNotIn('"/b/"', (BASE / "accounts" / "middleware.py").read_text(encoding="utf-8"))


