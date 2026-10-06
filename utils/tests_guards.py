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

    def test_forbidden_ui_words_in_templates(self):
        words = ["اختیاری", "فعلاً", "اتمیک", "FIFO", "اسنپ‌شات"]
        for path in (BASE / "templates").rglob("*.html"):
            rel = str(path.relative_to(BASE / "templates")).replace("\\", "/")
            if rel.startswith("admin/") or "dev_test" in rel:
                continue
            text = path.read_text(encoding="utf-8")
            for w in words:
                self.assertNotIn(w, text, f"{rel}: {w}")

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

    def test_fbsend_never_uses_bare_csrf_variable(self):
        import re
        files = list((BASE / "templates").rglob("*.html")) + list((BASE / "static" / "js").glob("*.js"))
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"fbSend\([^;]*,\s*csrf\s*[,)]", text), path.name)

    def test_no_start_margin_on_stage_blocks(self):
        for rel in ("projects/partials/stage_files.html", "projects/partials/stage_ops.html",
                    "projects/partials/stage_cuts.html", "projects/staff_project_overview.html"):
            self.assertNotIn("ms-10", (BASE / "templates" / rel).read_text(encoding="utf-8"), rel)

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



