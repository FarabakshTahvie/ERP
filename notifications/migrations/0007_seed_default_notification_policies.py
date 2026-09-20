from django.db import migrations


def seed_default_policies(apps, schema_editor):
    NotificationPolicy = apps.get_model('notifications', 'NotificationPolicy')
    default_policies = [
        ("invoice_issued", "sms_only", 15),
        ("stage_approval_request", "push_then_sms_fallback", 15),
        ("progress_update", "push_only", 15),
        ("low_stock", "push_only", 15),
        ("manual", "push_only", 15),
    ]
    for n_type, c_policy, fallback_mins in default_policies:
        NotificationPolicy.objects.get_or_create(
            notification_type=n_type,
            defaults={
                "channel_policy": c_policy,
                "fallback_after_minutes": fallback_mins,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0006_notification_short_code_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_default_policies, migrations.RunPython.noop),
    ]
