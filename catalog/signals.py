from django.db import transaction
from django.db.models.signals import post_delete, post_save

from .cache import bump
from .models import CatalogMedia, Item, ItemCategory, Service

# ذخیره‌ای که فقط فیلد بیرون از این مجموعه را عوض کند (مثل میانگین قیمت هنگام ورود کالا) کش را باطل نمی‌کند
CATALOG_FIELDS = {"name", "description", "cover", "cover_thumb", "show_to_clients", "is_active", "unit",
                  "category", "item_type", "specs", "parent", "code"}


def _touch(sender, update_fields=None, **kwargs):
    if update_fields is not None and not (set(update_fields) & CATALOG_FIELDS):
        return
    transaction.on_commit(bump)


for _model in (Service, Item, ItemCategory, CatalogMedia):
    post_save.connect(_touch, sender=_model)
    post_delete.connect(_touch, sender=_model)
