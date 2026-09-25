from django.db import migrations

def set_payment_step(apps, schema_editor):
    WorkflowStepTemplate = apps.get_model("projects", "WorkflowStepTemplate")
    WorkflowStepTemplate.objects.filter(template__is_default=True, order=2).update(requires_payment_selection=True)

class Migration(migrations.Migration):
    dependencies = [("projects", "0010_workflowsteptemplate_requires_payment_selection")]
    operations = [migrations.RunPython(set_payment_step, migrations.RunPython.noop)]
