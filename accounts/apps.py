from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'مدیریت کاربران و دسترسی‌ها'

    def ready(self):
        import accounts.signals  # noqa
