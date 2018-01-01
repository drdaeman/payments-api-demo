from django.db.models import BooleanField

import django_filters
from django_filters.widgets import BooleanWidget

from . import models


class AccountFilter(django_filters.FilterSet):
    """Filter set for Accounts API endpoint."""

    owner = django_filters.CharFilter(
        name="owner__name", help_text="Owner's name (exact lookups only)"
    )

    class Meta:
        model = models.Account
        # TODO: Generated schema's missing descriptions for those params
        fields = ("name", "owner", "currency", "balance")


class PaymentFilter(django_filters.FilterSet):
    """Filter set for Payments API endpoint."""

    from_account = django_filters.CharFilter(
        name="from_account__name",
        help_text="Source account's name (exact lookups only)"
    )
    to_account = django_filters.CharFilter(
        name="to_account__name",
        help_text="Destination account's name (exact lookups only)"
    )
    from_owner = django_filters.CharFilter(
        name="from_account__owner__name",
        help_text="Source account owner's name (exact lookups only)"
    )
    to_owner = django_filters.CharFilter(
        name="to_account__owner__name",
        help_text="Destination account owner's name (exact lookups only)"
    )

    class Meta:
        model = models.Payment
        fields = {
            "time": ("exact", "gt", "lt", "gte", "lte"),
            "confirmed": ("exact",)
        }
        filter_overrides = {
            # If we don't specify this override to use BooleanWidget,
            # the Django built-in NullBooleanField (with its widget)
            # will be used, and that doesn't recognize lowercase "true"
            # and "false" and has other oddities.
            # https://github.com/encode/django-rest-framework/issues/2122
            BooleanField: {
                "filter_class": django_filters.BooleanFilter,
                "extra": lambda f: {
                    "widget": BooleanWidget
                }
            }
        }
