from django.db import migrations


def seed_stage_approval_policy(apps, schema_editor):
    NotificationPolicy = apps.get_model("notifications", "NotificationPolicy")
    NotificationPolicy.objects.get_or_create(
        notification_type="stage_approval_request",
        defaults={"channel_policy": "sms_only", "fallback_after_minutes": 15},
    )


class Migration(migrations.Migration):
    dependencies = [("notifications", "0008_default_invoice_notification_policy")]
    operations = [migrations.RunPython(seed_stage_approval_policy, migrations.RunPython.noop)]
