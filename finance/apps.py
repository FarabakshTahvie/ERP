from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finance'
    verbose_name = 'امور مالی و فاکتور'

    def ready(self):
        try:
            from . import celery_tasks  # noqa
        except ImportError:
            pass
