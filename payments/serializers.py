import djmoney.settings

import moneyed

from rest_framework import serializers

from . import models


class OwnerSerializer(serializers.ModelSerializer):
    """Serializer for the Owner model."""

    class Meta:
        model = models.Owner
        fields = (
            "url",
            "name",
        )
        extra_kwargs = {
            "url": {"lookup_field": "name"},
        }


class AccountSerializer(serializers.ModelSerializer):
    """Serializer for the Account model, except for creation."""

    owner = serializers.SlugRelatedField(
        slug_field="name", queryset=models.Owner.objects.all()
    )

    class Meta:
        model = models.Account
        fields = (
            "url",
            "name",
            "owner",
            "currency",
            "balance",
        )
        extra_kwargs = {
            "url": {"lookup_field": "name"},
        }


class AccountCreateSerializer(AccountSerializer):
    """Serializer to create new Account instances."""

    currency = serializers.ChoiceField(
        required=True,
        choices=djmoney.settings.CURRENCY_CHOICES,
        help_text="Currency of the account (3-char ISO code from"
                  " the supported options, e.g. \"USD\")"
    )

    class Meta(AccountSerializer.Meta):
        pass

    def save(self, **kwargs):
        """Create the new account with zero balance in a given currency."""
        currency = self.validated_data.pop("currency")
        kwargs["balance"] = moneyed.Money(
            amount=0,
            currency=currency
        )
        return super().save(**kwargs)
