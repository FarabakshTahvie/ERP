import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("farabakhsh")
app.config_from_object("django.conf:settings", namespace="CELERY")
# فایل تسک‌ها در هر اپ celery_tasks.py نام دارد (نه tasks.py) تا با اپ «tasks» قاطی نشود
app.autodiscover_tasks(related_name="celery_tasks")
