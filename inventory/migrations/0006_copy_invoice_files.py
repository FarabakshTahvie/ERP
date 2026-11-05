import os
from django.db import migrations


def copy_invoice_files(apps, schema_editor):
    Purchase = apps.get_model("inventory", "Purchase")
    PurchaseFile = apps.get_model("inventory", "PurchaseFile")
    for purchase in Purchase.objects.exclude(invoice_file__isnull=True).exclude(invoice_file=""):
        PurchaseFile.objects.create(
            purchase=purchase, file=purchase.invoice_file.name,
            original_name=os.path.basename(purchase.invoice_file.name)[:255])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0005_purchase_file")]
    operations = [migrations.RunPython(copy_invoice_files, migrations.RunPython.noop)]
