from django.contrib import admin

from .models import Branch, Chain, Membership


@admin.register(Chain)
class ChainAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "chain", "address")
    list_filter = ("chain",)
    search_fields = ("name", "chain__name", "address")
    list_select_related = ("chain",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "chain", "branch", "created_at")
    list_filter = ("chain", "branch")
    search_fields = ("user__username", "user__email", "chain__name", "branch__name")
    list_select_related = ("user", "chain", "branch")
