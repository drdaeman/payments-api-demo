import decimal
import uuid

from django.db import transaction

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
        # TODO: Replace this with `create` method? (Possibly in base class?)
        currency = self.validated_data.pop("currency")
        kwargs["balance"] = moneyed.Money(
            amount=0,
            currency=currency
        )
        return super().save(**kwargs)


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for Payment model instances.

    Note, this serializer assumes the
    """

    from_account = serializers.SlugRelatedField(
        slug_field="name", queryset=models.Account.objects.select_for_update(),
        required=False, allow_null=True,
        help_text="Account ID to transfer from (omit for deposits)"
    )
    to_account = serializers.SlugRelatedField(
        slug_field="name", queryset=models.Account.objects.select_for_update(),
        required=False, allow_null=True,
        help_text="Account ID to transfer to (omit for withdrawals)"
    )
    currency = serializers.ChoiceField(
        required=True,
        choices=djmoney.settings.CURRENCY_CHOICES,
        help_text="Currency of the payment (3-char ISO code from"
                  " the supported options, e.g. \"USD\")."
                  " Must match the account(s)."
    )

    class Meta:
        model = models.Payment
        fields = (
            "url",
            "from_account",
            "to_account",
            "amount",
            "currency",
            "time",
            "unique_id",
            "confirmed",
        )
        read_only_fields = (
            "currency",
            "confirmed",
        )
        extra_kwargs = {
            "amount": {
                "required": True,
                "help_text": "Payment amount",
            },
            "unique_id": {
                "required": False,
                "help_text": (
                    "An unique identifier to associate with this transaction. "
                    "It's strongly recommended to provide this to avoid "
                    "possible duplicates. If not specified, a random UUIDv4 "
                    "will be generated."
                ),
            }
        }

    def validate(self, attrs):
        """Perform field validation and verify the accounts for the payment."""
        if transaction.get_autocommit():  # pragma: nocover
            # You must wrap the ViewSet.create in transaction.atomic
            # This check is a safety measure as the code in create relies on
            # transactions and select_for_update in the from/to_account QSes.
            #
            # Note, with PostgreSQL this check is not really necessary as it
            # would raise exception upon seeing select_for_update on the
            # account fields. However, not all databases support this and
            # the exception won't happen if connection.has_select_for_update
            # is not set. It is a bad idea to test against unsupported DB,
            # but this check doesn't hurt as well.
            #
            # Remove if this somehow blips on perf instrumentation radar.
            raise RuntimeError("BUG: The code is not running in a transaction")

        validated_data = super().validate(attrs)

        from_account = validated_data.get("from_account", None)
        to_account = validated_data.get("to_account", None)
        amount = validated_data["amount"]

        # Ensure there is exactly one currency for all the defined account
        # Also ensures at least one account is specified
        currencies = set()
        if from_account is not None:
            currencies.add(from_account.currency)
        if to_account is not None:
            currencies.add(to_account.currency)
        if len(currencies) < 1:
            raise serializers.ValidationError(
                "At least one account (from_account or to_account) is required"
            )
        currencies.add(validated_data["currency"])
        if len(currencies) != 1:
            # No currency conversion support for now.
            raise serializers.ValidationError(
                "Accounts and payment must all use the same currency"
            )

        if isinstance(amount, decimal.Decimal):  # pragma: no branch
            # Add currency (DRF doesn't do this for us), or comparison'll fail
            amount = moneyed.Money(amount, next(iter(currencies)))

        # If this transfer has a source, ensure no overdraft is possible
        if from_account is not None and from_account.balance < amount:
            raise serializers.ValidationError(
                "Source account balance is too low for this payment"
            )

        return validated_data

    def create(self, validated_data):
        """Perform the requested payment, adjusting the account balances."""
        payment = self.Meta.model(**validated_data)
        if not payment.unique_id:
            # TODO: Consider GCing unconfirmed Payments after a while
            payment.unique_id = str(uuid.uuid4())
            payment.confirmed = False
        else:
            try:
                payment.confirm(commit=False)
            except ValueError as e:
                raise serializers.ValidationError(*e.args)
            assert payment.confirmed is True

        payment.save(force_insert=True)  # Force INSERT to be extra safe
        return payment

    def update(self, instance, validated_data):  # pragma: nocover
        """Ensure that updates to Payments are not possible."""
        # This method should be never called, since the relevant ViewSet
        # should not implement `update` or `partial_update` methods.
        # Still, if there is some accidental mistake let's fail explicitly.
        #
        # The only updates possible are for the `confirm` field, and
        # for such updates you must use PaymentConfirmSerializer.
        raise RuntimeError("PaymentSerializer.update is not allowed")


class PaymentConfirmSerializer(serializers.ModelSerializer):
    """
    Serializer used to confirm payments in the two-step protocol mode.

    It only exposes a single field, ``confirmed`` and only accepts ``True``
    as a valid value.
    """

    class Meta:
        model = models.Payment
        fields = PaymentSerializer.Meta.fields
        read_only_fields = tuple(
            f for f in PaymentSerializer.Meta.fields
            if f != "confirmed"
        )

    def create(self, validated_data):  # pragma: nocover
        """Ensure that this serializer can't be used to create new Payments."""
        raise RuntimeError("PaymentConfirmSerializer.create was called")

    @transaction.atomic
    def update(self, instance, validated_data):
        """
        Confirm (commit) previously created payment.

        If a payment was created without any ``unique_id``, we don't perform
        it immediately, but use a two-phase commit protocol variation instead.
        We ask the client to follow the created payment and confirm it,
        completing the transaction.
        """
        if not validated_data.get("confirmed", None):
            raise serializers.ValidationError(
                "The only valid value for 'confirmed' is 'true'"
            )

        # Unfortunately, DRF doesn't allow action-dependent use
        # of select_for_update, so we have to re-fetch the objects.
        # See https://github.com/encode/django-rest-framework/issues/4675
        #
        # Also note we can't do Payment.objects.select_related() here,
        # as SELECT FOR UPDATE doesn't work for the nullable side
        # of the OUTER JOINs.
        payments = models.Payment.objects.select_for_update()
        accounts = models.Account.objects.select_for_update()

        payment = payments.get(pk=instance.pk)
        if payment.confirmed:
            # TODO: Or maybe throw an exception here?
            payment._not_modified = True  # HAX: Signal ViewSet about 304
            return payment

        # Note: select_related won't create a lock, so select independently
        if payment.from_account is not None:
            from_account = accounts.get(pk=payment.from_account.pk)
        else:
            from_account = None
        if payment.to_account is not None:
            to_account = accounts.get(pk=payment.to_account.pk)
        else:
            to_account = None

        try:
            payment.confirm(
                commit=True,
                from_account=from_account,
                to_account=to_account
            )
        except ValueError as e:
            raise serializers.ValidationError(*e.args)
        return payment
