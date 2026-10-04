from django.test import TestCase, override_settings
from django.urls import reverse
from accounts.models import User

@override_settings(NAJVA_ENABLED=True)
class NajvaHeadScriptTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test_najva_user", password="pw", role=User.Role.EMPLOYEE)

    def test_enabled_anonymous_login_page_has_script_in_head(self):
        resp = self.client.get(reverse("accounts:login"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        
        # ۱. شامل اسکریپت با مشخصات صحیح
        self.assertIn("https://van.najva.com/static/js/main-script.js", html)
        self.assertIn("data-najva-id", html)
        self.assertIn("najva-mini-script", html)
        
        # ۲. قرارگیری در head صفحه (قبل از بسته شدن تگ head)
        script_idx = html.find("main-script.js")
        head_close_idx = html.find("</head>")
        self.assertNotEqual(script_idx, -1)
        self.assertNotEqual(head_close_idx, -1)
        self.assertTrue(script_idx < head_close_idx)

    def test_enabled_logged_in_loads_script_only_once(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        
        self.assertEqual(html.count("main-script.js"), 1)
        self.assertEqual(html.count("najva-mini-script"), 1)

    def test_enabled_logged_in_still_registers_token_handler(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        
        self.assertIn("najvaUserSubscribed", html)
        self.assertIn(reverse("utils:register_push_device"), html)

    def test_enabled_anonymous_has_no_token_handler(self):
        resp = self.client.get(reverse("accounts:login"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        
        self.assertNotIn("register_push_device", html)
        self.assertNotIn("najvaUserSubscribed = sendToken", html)

    @override_settings(NAJVA_ENABLED=False)
    def test_disabled_has_no_najva_anywhere(self):
        # حالت غیر لاگین
        resp_anon = self.client.get(reverse("accounts:login"))
        self.assertNotIn("van.najva.com", resp_anon.content.decode("utf-8"))
        
        # حالت لاگین
        self.client.force_login(self.user)
        resp_auth = self.client.get(reverse("home"))
        self.assertNotIn("van.najva.com", resp_auth.content.decode("utf-8"))

    def test_head_snippet_is_verbatim(self):
        resp = self.client.get(reverse("accounts:login"))
        html = resp.content.decode("utf-8")
        expected_snippet = 'window.NAJVA={};var s=document.createElement("script");s.src="https://van.najva.com/static/js/main-script.js";'
        self.assertIn(expected_snippet, html)
        self.assertIn('s.setAttribute("data-najva-id","bee37675-c624-4422-a27f-6e25ec2472f5")', html)
