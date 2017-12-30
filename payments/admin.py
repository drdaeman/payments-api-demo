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
    autocomplete_fields = ("owner",)
    search_fields = ("name",)
