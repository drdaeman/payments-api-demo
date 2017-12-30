import django_filters

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
