import inspect
import re
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

    def test_removed_css_classes_in_templates(self):
        """قانون‌های ۱۰، ۱۳ و حذف‌شده‌های daisyUI 5 / Tailwind 4 در کلاس‌های تمپلیت."""
        bad_exact = {"form-control", "label-text", "tabs-boxed", "tabs-lift", "rounded-btn", "flex-shrink-0",
                     "flex-grow", "badge", "btn-warning", "btn-outline", "shadow-sm", "fb-page--md",
                     "fb-badge-accent"}
        problems = []
        for path in (BASE / "templates").rglob("*.html"):
            rel = str(path.relative_to(BASE / "templates")).replace("\\", "/")
            if rel.startswith("admin/") or "dev_test" in rel:
                continue
            for attr in re.findall(r'class="([^"]*)"', path.read_text(encoding="utf-8")):
                tokens = set(attr.split())
                for t in tokens:
                    if (t in bad_exact or t.endswith("-bordered") or t.startswith(("bg-opacity-", "text-opacity-"))
                            or (t.startswith("badge-") and not t.startswith("fb-"))):
                        problems.append(f"{rel}: {t}")
                if "btn-error" in tokens and "btn-soft" not in tokens:
                    problems.append(f"{rel}: btn-error بدون btn-soft")
        self.assertEqual(sorted(set(problems)), [])

    def test_generic_table_cell_types(self):
        for path in BASE.rglob("*views*.py"):
            if any(p in path.parts for p in ("venv", ".venv", "node_modules", "staticfiles")):
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('{"type": "html"', text, path.name)
            self.assertNotIn('{"type": "amount"', text, path.name)

    def test_digest_and_create_broadcast_are_keyword_only(self):
        from notifications import broadcast
        for fn in (broadcast.calculate_digest, broadcast.create_broadcast):
            kinds = {p.kind for p in inspect.signature(fn).parameters.values()}
            self.assertEqual(kinds, {inspect.Parameter.KEYWORD_ONLY}, fn.__name__)

    def test_design_system_rules_are_numbered_continuously(self):
        text = (BASE / "docs" / "DESIGN_SYSTEM.md").read_text(encoding="utf-8")
        nums = [int(m.group(1)) for m in re.finditer(r"(?m)^(\d+)\. ", text)]
        self.assertEqual(nums, list(range(1, 60)))

    def test_no_windows_identifier_files_and_vendor_docs_exist(self):
        for path in BASE.rglob("*.Identifier"):
            if not any(p in path.parts for p in ("venv", ".venv", "node_modules")):
                self.fail(str(path))
        self.assertTrue((BASE / "docs" / "vendor" / "najva-api.md").is_file())
        self.assertTrue((BASE / "docs" / "vendor" / "smsir-api.md").is_file())

    def test_no_public_broadcast_image_route(self):
        from django.test import Client
        self.assertEqual(Client().get("/b/" + "a" * 32 + ".jpg").status_code, 404)
        self.assertNotIn('"/b/"', (BASE / "accounts" / "middleware.py").read_text(encoding="utf-8"))

    def test_image_upload_points_call_optimizer(self):
        import ast
        points = {"projects/stage_ops.py": "add_stage_file", "projects/services.py": "attach_project_files",
                  "inventory/services.py": "create_purchase_from_form", "tasks/services.py": "add_attachment"}
        for rel, func in points.items():
            tree = ast.parse((BASE / rel).read_text(encoding="utf-8"))
            node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == func)
            names = {c.func.id for c in ast.walk(node) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
            self.assertTrue(names & {"optimize_named", "optimize_upload"}, f"{rel}:{func}")

    def test_celery_publish_calls_only_in_known_places(self):
        allowed = {"notifications/broadcast.py", "notifications/celery_tasks.py", "accounts/services.py", "messenger/services.py"}
        found = set()
        for path in BASE.rglob("*.py"):
            if (any(p in path.parts for p in ("venv", ".venv", "node_modules", "migrations", "staticfiles"))
                    or path.name.startswith("test")):
                continue
            if re.search(r"\.(delay|apply_async)\(", path.read_text(encoding="utf-8")):
                found.add(str(path.relative_to(BASE)).replace("\\", "/"))
        self.assertEqual(found, allowed)

    def test_celery_tasks_ignore_results_and_return_nothing(self):
        import ast
        for rel in ("notifications/celery_tasks.py", "accounts/celery_tasks.py", "messenger/celery_tasks.py"):
            tree = ast.parse((BASE / rel).read_text(encoding="utf-8"))
            tasks = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                     and any("shared_task" in ast.dump(d) for d in n.decorator_list)]
            self.assertTrue(tasks, rel)
            for fn in tasks:
                deco = " ".join(ast.dump(d) for d in fn.decorator_list)
                self.assertIn("ignore_result", deco, f"{rel}:{fn.name}")
                for node in ast.walk(fn):
                    if isinstance(node, ast.Return):
                        self.assertTrue(node.value is None or (isinstance(node.value, ast.Constant) and node.value.value is None),
                                        f"{rel}:{fn.name} مقدار بازگشتی دارد")

    def test_celery_deploy_files_are_consistent(self):
        self.assertTrue((BASE / "deploy" / "farabakhsh-celery.service").is_file())
        self.assertTrue((BASE / "deploy" / "farabakhsh-celerybeat.service").is_file())
        beat = (BASE / "deploy" / "farabakhsh-celerybeat.service").read_text(encoding="utf-8")
        self.assertIn("--schedule=/var/lib/", beat)
        self.assertIn("StateDirectory=", beat)
        worker = (BASE / "deploy" / "farabakhsh-celery.service").read_text(encoding="utf-8")
        self.assertIn("-A config worker", worker)
        update = (BASE / "deploy" / "update.sh").read_text(encoding="utf-8")
        self.assertIn("farabakhsh-celery.service", update)
        self.assertIn("daemon-reload", update)
        self.assertIn("inspect ping", update)

    def test_toast_container_does_not_capture_clicks(self):
        text = (BASE / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("toast toast-top toast-center z-50 p-4 space-y-2 max-w-md w-full pointer-events-none", text)
        self.assertIn("pointer-events-auto", text)
        self.assertIn('aria-label="بستن پیام"', text)

    def test_multi_entry_links_use_nav_url(self):
        """در همه‌ی تمپلیت‌ها (به‌جز base.html، admin/ و dev_test) هیچ {% url 'N' با N در MULTI_ENTRY وجود نداشته باشد."""
        from utils.navigation import MULTI_ENTRY
        import re

        pattern = re.compile(r"{%\s*url\s+['\"]([\w:]+)['\"]")
        # تمپلیت‌های ویرایش/ویرایشگر که والد ثابتشان همان صفحه جزئیات است
        allowed_templates = {
            "people/user_edit.html",
            "people/party_edit.html",
            "people/password_reset_done.html",
        }
        violations = []

        for path in (BASE / "templates").rglob("*.html"):
            rel = str(path.relative_to(BASE / "templates")).replace("\\", "/")
            if rel == "base.html" or rel.startswith("admin/") or "dev_test" in rel or rel in allowed_templates:
                continue
            text = path.read_text(encoding="utf-8")
            for m in pattern.finditer(text):
                name = m.group(1)
                if name in MULTI_ENTRY:
                    violations.append(f"{rel}: {name}")

        self.assertEqual(violations, [])

    def test_multi_entry_reverse_in_python_goes_through_navigation(self):
        """در فایل‌های *views*.py، */services.py و utils/generic_table.py هیچ reverse("N" با N در MULTI_ENTRY نباشد (به‌جز فایل‌های استثنا)."""
        from utils.navigation import MULTI_ENTRY
        import re

        pattern = re.compile(r"reverse\(\s*['\"]([\w:]+)['\"]")
        allowed_files = {
            "utils/navigation.py",
            "people/services.py",  # activity_feed
            "projects/services.py",  # notification targets
            "projects/views.py",  # redirects after POST
            "dashboard/services.py",  # notification targets
            "dashboard/views.py",  # redirects after POST
            "notifications/broadcast_views.py",  # redirects after POST
        }
        violations = []

        for path in BASE.rglob("*.py"):
            if any(p in path.parts for p in ("venv", ".venv", "node_modules", "migrations", "staticfiles")) or path.name.startswith("test"):
                continue
            rel = str(path.relative_to(BASE)).replace("\\", "/")
            if not (rel.endswith("views.py") or "views" in rel or rel.endswith("services.py") or rel == "utils/generic_table.py"):
                continue
            if rel in allowed_files:
                continue
            text = path.read_text(encoding="utf-8")
            for m in pattern.finditer(text):
                name = m.group(1)
                if name in MULTI_ENTRY:
                    violations.append(f"{rel}: {name}")

        self.assertEqual(violations, [])


