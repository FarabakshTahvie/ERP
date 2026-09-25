from django.db import migrations

def set_internal_partner(apps, schema_editor):
    Party = apps.get_model("core", "Party")
    Party.objects.filter(is_internal=True).update(is_partner=True)

class Migration(migrations.Migration):
    dependencies = [("core", "0004_create_internal_party")]
    operations = [migrations.RunPython(set_internal_partner, migrations.RunPython.noop)]
