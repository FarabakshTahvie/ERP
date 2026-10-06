from django.conf import settings
from django.test import SimpleTestCase


class CeleryConfigTests(SimpleTestCase):
    def test_celery_is_eager_and_offline_in_tests(self):
        from config import celery_app
        self.assertTrue(settings.CELERY_TASK_ALWAYS_EAGER)
        self.assertTrue(settings.CELERY_TASK_EAGER_PROPAGATES)
        self.assertEqual(settings.CELERY_BROKER_URL, "memory://")
        self.assertTrue(celery_app.conf.task_always_eager)

    def test_results_are_ignored_and_ack_is_early(self):
        self.assertTrue(settings.CELERY_TASK_IGNORE_RESULT)
        self.assertFalse(settings.CELERY_TASK_ACKS_LATE)
