from django.db import migrations


def create_internal_party(apps, schema_editor):
    Party = apps.get_model('core', 'Party')
    Party.objects.get_or_create(
        is_internal=True,
        defaults={
            'name': 'فرابخش تهویه (حساب داخلی)',
            'entity_type': 'company',
            'is_partner': True,
        }
    )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_partycontact_remove_historicalparty_linked_user_and_more'),
    ]
    operations = [
        migrations.RunPython(create_internal_party, migrations.RunPython.noop),
    ]
