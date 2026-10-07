from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import URLPattern, URLResolver, get_resolver, resolve, reverse

from utils.navigation import (
    MAX_NEXT,
    PAGE_PARENTS,
    TOP_LEVEL,
    _strip_next,
    current_page_url,
    nav_reverse,
    resolve_back,
    safe_internal_path,
    with_next,
)


class NavigationTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_safe_internal_path_accepts_only_internal_resolvable_paths(self):
        req = self.rf.get("/")
        # معتبر
        self.assertEqual(safe_internal_path(req, "/people/"), "/people/")
        self.assertEqual(safe_internal_path(req, "/people/?x=1"), "/people/?x=1")

        # نامعتبر
        self.assertIsNone(safe_internal_path(req, "https://evil.com/"))
        self.assertIsNone(safe_internal_path(req, "//evil.com"))
        self.assertIsNone(safe_internal_path(req, "/\\evil.com"))
        self.assertIsNone(safe_internal_path(req, "javascript:alert(1)"))
        self.assertIsNone(safe_internal_path(req, "/no-such-page/"))
        self.assertIsNone(safe_internal_path(req, "/" + "a" * (MAX_NEXT + 1)))
        self.assertIsNone(safe_internal_path(req, "/people/\n"))
        self.assertIsNone(safe_internal_path(req, None))
        self.assertIsNone(safe_internal_path(req, ""))

    def test_resolve_back_uses_valid_next_first(self):
        req = self.rf.get("/manager/stages/?next=/people/")
        req.resolver_match = resolve("/manager/stages/")
        self.assertEqual(resolve_back(req), "/people/")

    def test_resolve_back_ignores_invalid_or_self_next(self):
        req = self.rf.get("/manager/stages/?next=https://evil.com/")
        req.resolver_match = resolve("/manager/stages/")
        self.assertEqual(resolve_back(req), reverse("dashboard:overview"))

        # self next
        req_self = self.rf.get("/manager/stages/?next=/manager/stages/")
        req_self.resolver_match = resolve("/manager/stages/")
        self.assertEqual(resolve_back(req_self), reverse("dashboard:overview"))

    def test_resolve_back_falls_back_to_parent_with_kwargs(self):
        # projects:proforma_editor -> projects:staff_project_overview
        req = self.rf.get("/staff/projects/42/proforma/")
        req.resolver_match = resolve("/staff/projects/42/proforma/")
        self.assertEqual(resolve_back(req), reverse("projects:staff_project_overview", kwargs={"project_id": 42}))

        # tasks:edit -> tasks:detail
        req2 = self.rf.get("/tasks/7/edit/")
        req2.resolver_match = resolve("/tasks/7/edit/")
        self.assertEqual(resolve_back(req2), reverse("tasks:detail", kwargs={"task_id": 7}))

        # inventory:item_edit -> /?tab=stock
        req3 = self.rf.get("/inventory/items/5/edit/")
        req3.resolver_match = resolve("/inventory/items/5/edit/")
        self.assertEqual(resolve_back(req3), "/?tab=stock")

    def test_top_level_pages_have_no_back(self):
        for path in ("/", "/manager/", "/accounts/login/", "/accounts/set-password/"):
            req = self.rf.get(path)
            req.resolver_match = resolve(path)
            self.assertIsNone(resolve_back(req), f"Expected None for {path}")

    def test_with_next_strips_pages_own_next_and_encodes(self):
        req = self.rf.get("/finance/x/?a=1&next=/old/")
        target = "/p/1/"
        res = with_next(req, target)
        self.assertEqual(res, "/p/1/?next=%2Ffinance%2Fx%2F%3Fa%3D1")

    def test_current_page_url_uses_hx_current_url_for_htmx(self):
        # HX-Request با HX-Current-URL معتبر
        req = self.rf.get(
            "/payments/table/?py_q=a",
            HTTP_HX_REQUEST="true",
            HTTP_HX_CURRENT_URL="http://testserver/payments/?py_q=a&tab=x",
        )
        self.assertEqual(current_page_url(req), "/payments/?py_q=a&tab=x")

        # دامنه‌ی بیگانه
        req_foreign = self.rf.get(
            "/payments/table/?py_q=a",
            HTTP_HX_REQUEST="true",
            HTTP_HX_CURRENT_URL="http://evil.com/payments/?py_q=a&tab=x",
        )
        self.assertEqual(current_page_url(req_foreign), "/payments/table/?py_q=a")

    def test_page_parents_are_reversible(self):
        # بررسی صحت تمام مدخل‌های PAGE_PARENTS
        route_converters = {}

        def walk(patterns, ns, prefix):
            for p in patterns:
                if isinstance(p, URLResolver):
                    walk(p.url_patterns, ns + ([p.namespace] if p.namespace else []), prefix + str(p.pattern))
                elif isinstance(p, URLPattern) and p.name:
                    full = ":".join(ns + [p.name])
                    converters = list(p.pattern.converters.keys())
                    route_converters[full] = converters

        walk(get_resolver().url_patterns, [], "")

        for child_name, (parent_name, parent_kwargs, query) in PAGE_PARENTS.items():
            self.assertIn(child_name, route_converters, f"Child {child_name} not found in url patterns")
            self.assertIn(parent_name, route_converters, f"Parent {parent_name} not found in url patterns")

            # kwargs والد باید زیرمجموعه kwargs صفحه فرزند باشند
            child_convs = route_converters[child_name]
            for kw in parent_kwargs:
                self.assertIn(kw, child_convs, f"Kwarg {kw} of parent {parent_name} not in child {child_name}")

            # بررسی reverse پذیری با مقادیر تستی
            sample_kwargs = {}
            for kw in parent_kwargs:
                sample_kwargs[kw] = "00000000-0000-0000-0000-000000000000" if "uuid" in kw else 1
            try:
                url = reverse(parent_name, kwargs=sample_kwargs)
                self.assertTrue(url.startswith("/"))
            except Exception as e:
                self.fail(f"Failed to reverse parent {parent_name} with kwargs {sample_kwargs}: {e}")


class NavigationHeaderIntegrationTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username="manager_nav",
            phone_number="09123456789",
            first_name="مدیر",
            role="manager",
        )

    def test_back_link_rendered_with_parent_href(self):
        from unittest.mock import patch
        with patch("core.capabilities.capabilities_for", return_value={"accounting_access": True}):
            self.client.force_login(self.user)
            res = self.client.get("/manager/stages/")
            self.assertEqual(res.status_code, 200)
            self.assertContains(res, 'data-fb-back')
            self.assertContains(res, 'href="/manager/"')

    def test_back_link_uses_valid_next_and_ignores_evil_next(self):
        from unittest.mock import patch
        with patch("core.capabilities.capabilities_for", return_value={"accounting_access": True}):
            self.client.force_login(self.user)
            res1 = self.client.get("/manager/stages/?next=/people/")
            self.assertContains(res1, 'href="/people/"')

            res2 = self.client.get("/manager/stages/?next=https://evil.com/")
            self.assertContains(res2, 'href="/manager/"')

    def test_no_back_link_on_home_and_login(self):
        from unittest.mock import patch
        with patch("core.capabilities.capabilities_for", return_value={"accounting_access": True}):
            self.client.force_login(self.user)
            res_home = self.client.get("/")
            self.assertNotContains(res_home, 'data-fb-back')

        self.client.logout()
        res_login = self.client.get("/accounts/login/")
        self.assertNotContains(res_login, 'data-fb-back')

    def test_standalone_markers_present(self):
        from pathlib import Path
        from django.conf import settings
        base = Path(settings.BASE_DIR)
        html = (base / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("fb-standalone", html)
        self.assertIn("fb_standalone", html)

        css = (base / "static" / "src" / "input.css").read_text(encoding="utf-8")
        self.assertIn("html:not(.fb-standalone) .fb-back { display: none; }", css)

    def test_back_url_failure_never_breaks_page(self):
        from unittest.mock import patch
        with patch("core.capabilities.capabilities_for", return_value={"accounting_access": True}):
            self.client.force_login(self.user)
            with patch("utils.navigation.reverse", side_effect=Exception("Reverse failed")):
                res = self.client.get("/manager/stages/")
                self.assertEqual(res.status_code, 200)
                self.assertNotContains(res, 'data-fb-back')

    def test_multi_entry_link_in_table_includes_next_param(self):
        from unittest.mock import patch
        with patch("core.capabilities.capabilities_for", return_value={"accounting_access": True, "people_view": True}):
            self.client.force_login(self.user)
            # GET روی لیست افراد شامل nav_url یا لینک چندورودی به user_detail
            res = self.client.get("/people/")
            self.assertEqual(res.status_code, 200)
            self.assertContains(res, '?next=%2Fpeople%2F')

            # درخواست HTMX با HX-Current-URL
            res_htmx = self.client.get(
                "/people/table/",
                headers={"HX-Request": "true", "HX-Current-URL": "http://testserver/people/?pe_q=test"},
            )
            self.assertEqual(res_htmx.status_code, 200)
            self.assertContains(res_htmx, '?next=%2Fpeople%2F%3Fpe_q%3Dtest')


def all_url_names():
    from django.urls import URLPattern, URLResolver, get_resolver
    out = set()
    def walk(patterns, ns):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, ns + ([p.namespace] if p.namespace else []))
            elif isinstance(p, URLPattern) and p.name:
                out.add(":".join(ns + [p.name]))
    walk(get_resolver().url_patterns, [])
    return {n for n in out if not n.startswith("admin:")}


class NavigationClassificationTests(SimpleTestCase):
    def test_every_url_name_is_classified_exactly_once(self):
        from utils.navigation import NON_PAGE, PAGE_PARENTS, TOP_LEVEL
        names = all_url_names()
        known = set(PAGE_PARENTS) | TOP_LEVEL | NON_PAGE
        self.assertEqual(sorted(names - known), [], "URL بدون طبقه‌بندی")
        self.assertEqual(sorted(known - names), [], "مدخل قدیمی در فهرست ناوبری")
        self.assertFalse(set(PAGE_PARENTS) & TOP_LEVEL | set(PAGE_PARENTS) & NON_PAGE | TOP_LEVEL & NON_PAGE)

    def test_multi_entry_pages_are_real_pages(self):
        from utils.navigation import MULTI_ENTRY, PAGE_PARENTS
        self.assertFalse(MULTI_ENTRY - set(PAGE_PARENTS))



