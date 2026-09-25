from django.db import migrations


def restructure_default_workflow(apps, schema_editor):
    Specialty = apps.get_model('core', 'Specialty')
    WorkflowTemplate = apps.get_model('projects', 'WorkflowTemplate')
    WorkflowStepTemplate = apps.get_model('projects', 'WorkflowStepTemplate')

    cnc_specialty, _ = Specialty.objects.get_or_create(name="اپراتور CNC")
    assembler_specialty, _ = Specialty.objects.get_or_create(name="مونتاژکار")

    for template in WorkflowTemplate.objects.all():
        steps = {s.title: s for s in template.steps.all()}

        # فاز ۱: همه‌ی مراحل موجود را موقتاً به بازه‌ی بالا می‌بریم
        # تا تداخل با unique_together(template, order) پیش نیاید
        for s in steps.values():
            s.order += 100
            s.save(update_fields=["order"])

        # فاز ۲: مراحل کاملاً جدید را در جای نهایی‌شان می‌سازیم
        step_design = steps.get("طراحی اولیه اتوکد")

        WorkflowStepTemplate.objects.get_or_create(
            template=template, title="تایید پیش‌فاکتور و انتخاب روش پرداخت",
            defaults=dict(order=2, client_label="تایید پیش‌فاکتور", approval_by="choose_at_runtime"),
        )

        if step_design:
            WorkflowStepTemplate.objects.get_or_create(
                template=template, title="تایید طرح اولیه",
                defaults=dict(order=5, client_label="تایید نقشه اولیه",
                              approval_by="choose_at_runtime", on_reject_go_to=step_design),
            )

        WorkflowStepTemplate.objects.get_or_create(
            template=template, title="مونتاژ",
            defaults=dict(order=9, client_label="مونتاژ", responsible_specialty=assembler_specialty),
        )
        WorkflowStepTemplate.objects.get_or_create(
            template=template, title="ارسال",
            defaults=dict(order=10, client_label="ارسال به محل نصب"),
        )

        # فاز ۳: مراحل موجود را به ترتیب و نام نهایی‌شان برمی‌گردانیم
        final_orders = {
            "صدور پیش‌فاکتور": 1,
            "بازدید کارگاهی": 3,
            "طراحی اولیه اتوکد": 4,
            "تکمیل طراحی": 6,
            "داکت‌گیری": 7,      # هم‌زمان تغییر نام به جی‌کدگیری
            "برش‌کاری": 8,
            "نصب و تحویل": 11,   # هم‌زمان تغییر نام به نصب
        }
        for old_title, final_order in final_orders.items():
            step = steps.get(old_title)
            if not step:
                continue
            step.order = final_order
            if old_title == "داکت‌گیری":
                step.title = "جی‌کدگیری"
                step.client_label = "آماده‌سازی برش (جی‌کدگیری)"
                step.responsible_specialty = cnc_specialty
            elif old_title == "طراحی اولیه اتوکد":
                step.approval_by = "none"   # تاییدش به مرحله‌ی جدید «تایید طرح اولیه» منتقل شد
            elif old_title == "نصب و تحویل":
                step.title = "نصب"
                step.client_label = "نصب نهایی"
            step.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0007_alter_projectfile_kind'),
        ('core', '0004_create_internal_party'),
    ]
    operations = [
        migrations.RunPython(restructure_default_workflow, noop_reverse),
    ]
