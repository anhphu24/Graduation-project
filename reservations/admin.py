from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "lot",
        "quantity",
        "status",
        "pickup_deadline",
        "paid_at",
    )
    list_filter = ("status", "lot__branch__chain", "lot__branch")
    search_fields = ("id", "pickup_code", "customer__username", "lot__code")
    list_select_related = ("customer", "lot", "lot__product", "lot__branch")
    readonly_fields = (
        "id",
        "customer",
        "lot",
        "quantity",
        "unit_price",
        "pickup_code",
        "request_token",
        "status",
        "pickup_deadline",
        "created_at",
        "paid_at",
        "collected_by",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
