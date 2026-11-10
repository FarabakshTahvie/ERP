from django.db import transaction
from django.db.models.signals import post_delete, post_save

from .cache import bump
from .models import CatalogMedia, Item, ItemCategory, MarginRule, Service

# ذخیره‌ای که فقط فیلد بیرون از این مجموعه را عوض کند (مثل updated_at) کش را باطل نمی‌کند.
# moving_average_cost داخل مجموعه است چون قیمت کالا در ویترین از آن ساخته می‌شود؛ MarginRule هم همین‌طور.
CATALOG_FIELDS = {"name", "description", "cover", "cover_thumb", "show_to_clients", "is_active", "unit",
                  "category", "item_type", "specs", "parent", "code", "moving_average_cost"}


def _touch(sender, update_fields=None, **kwargs):
    if update_fields is not None and not (set(update_fields) & CATALOG_FIELDS):
        return
    transaction.on_commit(bump)


for _model in (Service, Item, ItemCategory, CatalogMedia, MarginRule):
    post_save.connect(_touch, sender=_model)
    post_delete.connect(_touch, sender=_model)
