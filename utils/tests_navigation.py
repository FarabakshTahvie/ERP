from django.test import RequestFactory, SimpleTestCase
from utils.navigation import MAX_NEXT, safe_internal_path


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
