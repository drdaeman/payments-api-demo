from django.db.models import BooleanField

import django_filters
from django_filters.widgets import BooleanWidget

from . import models


class AccountFilter(django_filters.FilterSet):
    """Filter set for Accounts API endpoint."""

    currency = django_filters.CharFilter(
        name="name",
        help_text="Currency of the account (3-char ISO code from"
                  " the supported options, e.g. \"USD\")"
    )
    owner = django_filters.CharFilter(
        name="owner__name", help_text="Owner's name (exact lookups only)"
    )
    balance_lte = django_filters.NumberFilter(
        name="balance", lookup_expr="lte",
        help_text="Maximum balance to include in the list"
    )
    balance_gte = django_filters.NumberFilter(
        name="balance", lookup_expr="gte",
        help_text="Minimum balance to include in the list"
    )

    class Meta:
        model = models.Account
        fields = ("owner", "currency")


class PaymentFilter(django_filters.FilterSet):
    """Filter set for Payments API endpoint."""

    # TODO: Add tests that check that filters are set up correctly and work
    # (while this should be django-filter responsibility to test that
    #  filters do what they're supposed to do, it should be a good idea
    #  to test the API contract here too)
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
    confirmed = django_filters.BooleanFilter(
        # Explicit widget declaration is required here.
        # If we don't specify it, Django's built-in NullBooleanField
        # will be used with its own default widget, and that doesn't
        # recognize lowercase "true" and "false" and has other oddities.
        # https://github.com/encode/django-rest-framework/issues/2122
        name="currency", widget=BooleanWidget,
        help_text="Whenever to look only for confirmed (`true`)"
                  " or unconfirmed (`false`) payments only"
    )
    time__lte = django_filters.IsoDateTimeFilter(
        name="time", lookup_expr="lte",
        help_text="Maximum payment time for inclusion, in ISO 8601 format."
                  " Newer payments won't be listed."
    )
    time__gte = django_filters.IsoDateTimeFilter(
        name="time", lookup_expr="gte",
        help_text="Minimum payment time for inclusion, in ISO 8601 format."
                  " Older payments won't be listed."
    )

    class Meta:
        model = models.Payment
        fields = tuple()
