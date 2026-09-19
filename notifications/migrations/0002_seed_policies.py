from django.db import migrations


def seed_policies(apps, schema_editor):
    NotificationPolicy = apps.get_model('notifications', 'NotificationPolicy')
    NotificationPolicy.objects.get_or_create(
        notification_type='invoice_issued',
        defaults={'channel_policy': 'push_and_sms', 'fallback_after_minutes': 15}
    )
    NotificationPolicy.objects.get_or_create(
        notification_type='progress_update',
        defaults={'channel_policy': 'push_only', 'fallback_after_minutes': 15}
    )
    NotificationPolicy.objects.get_or_create(
        notification_type='manual',
        defaults={'channel_policy': 'push_then_sms_fallback', 'fallback_after_minutes': 30}
    )


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_policies, migrations.RunPython.noop),
    ]
