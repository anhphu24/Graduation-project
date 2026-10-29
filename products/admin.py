from django.contrib import admin

from .models import Lot, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "chain", "expiry_type")
    list_filter = ("chain", "expiry_type")
    search_fields = ("name", "chain__name", "allergens")
    list_select_related = ("chain",)


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "product",
        "branch",
        "sale_price",
        "available_quantity",
        "reserve_end",
        "is_active",
    )
    list_filter = ("is_active", "branch__chain", "branch")
    search_fields = ("code", "product__name", "branch__name")
    list_select_related = ("product", "branch", "branch__chain")

    def has_change_permission(self, request, obj=None):
        if obj and obj.orders.exists():
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.orders.exists():
            return False
        return super().has_delete_permission(request, obj)
