from django.db import migrations


def create_default_policy(apps, schema_editor):
    NotificationPolicy = apps.get_model('notifications', 'NotificationPolicy')
    NotificationPolicy.objects.get_or_create(
        notification_type='invoice_issued',
        defaults={'channel_policy': 'sms_only', 'fallback_after_minutes': 15},
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0007_seed_default_notification_policies'),
    ]
    operations = [
        migrations.RunPython(create_default_policy, noop_reverse),
    ]
