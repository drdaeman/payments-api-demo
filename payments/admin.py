from django.contrib import admin

from . import models


@admin.register(models.Owner)
class OwnerAdmin(admin.ModelAdmin):
    """Django admin configuration for the Owner model."""

    search_fields = ("name",)  # To support autocomplete_fields in other models


@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    """Django admin configuration for the Account model."""

    readonly_fields = ("currency", "balance")
    list_display = ("name", "balance", "owner")
    list_select_related = ("owner",)
    autocomplete_fields = ("owner",)
    search_fields = ("name",)


@admin.register(models.Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Django admin configuration for the Payment model."""

    autocomplete_fields = ("from_account", "to_account")
    list_display = (
        "time", "from_account", "to_account", "amount", "confirmed",
    )
    search_fields = ("unique_id",)
