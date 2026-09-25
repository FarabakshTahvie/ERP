from django.db import migrations


def seed_default_workflow(apps, schema_editor):
    Specialty = apps.get_model('core', 'Specialty')
    WorkflowTemplate = apps.get_model('projects', 'WorkflowTemplate')
    WorkflowStepTemplate = apps.get_model('projects', 'WorkflowStepTemplate')

    sp_duct, _ = Specialty.objects.get_or_create(name="کانال‌کش")
    sp_design, _ = Specialty.objects.get_or_create(name="طراح اتوکد")
    sp_cnc, _ = Specialty.objects.get_or_create(name="اپراتور CNC")
    sp_assembler, _ = Specialty.objects.get_or_create(name="مونتاژکار")

    template, _ = WorkflowTemplate.objects.get_or_create(
        is_default=True,
        defaults={'name': 'گردش‌کار پیش‌فرض تهویه'}
    )

    steps_data = [
        # title, client_label, specialty, approval_by, allows_file_upload
        ("صدور پیش‌فاکتور", "صدور پیش‌فاکتور", None, "admin", False),
        ("تایید پیش‌فاکتور و انتخاب روش پرداخت", "تایید پیش‌فاکتور", None, "choose_at_runtime", False),
        ("بازدید کارگاهی", "بازدید و اندازه‌گیری", sp_duct, "none", False),
        ("طراحی اولیه اتوکد", "طراحی اولیه", sp_design, "none", True),
        ("تایید طرح اولیه", "تایید نقشه اولیه", None, "choose_at_runtime", False),
        ("تکمیل طراحی", "طراحی نهایی", sp_design, "none", True),
        ("جی‌کدگیری", "آماده‌سازی برش (جی‌کدگیری)", sp_cnc, "none", False),
        ("برش‌کاری", "برش", sp_duct, "none", False),
        ("مونتاژ", "مونتاژ", sp_assembler, "none", False),
        ("ارسال", "ارسال به محل نصب", None, "none", False),
        ("نصب", "نصب نهایی", sp_duct, "admin", False),
    ]

    step_objs = []
    for i, (title, client_label, specialty, approval, upload) in enumerate(steps_data, start=1):
        step, _ = WorkflowStepTemplate.objects.get_or_create(
            template=template,
            order=i,
            defaults=dict(
                title=title, client_label=client_label,
                responsible_specialty=specialty, approval_by=approval,
                allows_file_upload=upload, client_visible=True,
                estimated_duration_hours=8 if specialty else 4,
            )
        )
        step_objs.append(step)

    if len(step_objs) >= 5:
        step_objs[4].on_reject_go_to = step_objs[3]
        step_objs[4].save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0008_restructure_workflow_steps'),
        ('core', '0004_create_internal_party'),
    ]
    operations = [
        migrations.RunPython(seed_default_workflow, noop_reverse),
    ]
