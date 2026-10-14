from django.db import migrations


def forward(apps, schema_editor):
    for name in ("WorkflowStepTemplate", "ProjectStage"):
        apps.get_model("projects", name).objects.filter(title="مونتاژ", kind="generic").update(kind="assembly")


class Migration(migrations.Migration):
    dependencies = [("projects", "0025_stage_usage_remove_shipping")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
