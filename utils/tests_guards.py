from pathlib import Path
from django.conf import settings
from django.test import TestCase

BASE = Path(settings.BASE_DIR)


class SourceGuardTests(TestCase):
    def test_no_is_staff_for_decisions_in_finance_and_projects_views(self):
        for rel in ("finance/views.py", "finance/views_accounting.py", "projects/views.py", "projects/views_ops.py"):
            self.assertNotIn("is_staff", (BASE / rel).read_text(encoding="utf-8"), rel)

    def test_stale_template_names_and_forbidden_vocabulary(self):
        forbidden = ["زیان", "سود پروژه", "final_profit", "credit_open", "pending_extras", "internal_notes"]
        files = list((BASE / "templates" / "finance").rglob("*.html")) \
            + list((BASE / "templates" / "dashboard").rglob("*.html")) \
            + [BASE / "templates" / "projects" / "final_review.html"]
        for path in files:
            text = path.read_text(encoding="utf-8")
            for word in forbidden:
                self.assertNotIn(word, text, f"{path.name}: {word}")

    def test_banned_daisyui_classes_in_finance_and_dashboard_templates(self):
        banned = ["input-bordered", "select-bordered", "form-control", "label-text", "tabs-boxed"]
        for folder in ("finance", "dashboard"):
            for path in (BASE / "templates" / folder).rglob("*.html"):
                text = path.read_text(encoding="utf-8")
                for cls in banned:
                    self.assertNotIn(cls, text, f"{path.name}: {cls}")

    def test_no_is_staff_in_any_template(self):
        for path in (BASE / "templates").rglob("*.html"):
            self.assertNotIn("is_staff", path.read_text(encoding="utf-8"), path.name)

    def test_no_duplicate_top_level_functions_in_key_modules(self):
        import ast
        for rel in ("finance/views_accounting.py", "finance/views.py", "projects/views.py",
                    "projects/views_ops.py", "dashboard/views.py", "dashboard/services.py"):
            tree = ast.parse((BASE / rel).read_text(encoding="utf-8"))
            names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
            self.assertFalse({n for n in names if names.count(n) > 1}, rel)

