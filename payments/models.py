from django.db import models
from django.utils import timezone

import djmoney.models.fields


class MoneyField(djmoney.models.fields.MoneyField):
    """
    A MoneyField subclass with tweaked defaults.

    This class also adds convenience/shortcut argument ``shared_currency``.
    When set to ``True`` it's essentially ``currency_field_name="currency"``.
    The default is ``False`` to avoid possible confusion.
    """

    def __init__(self, verbose_name=None, name=None, **kwargs):
        """Initialize MoneyField with useful defaults."""
        kwargs.setdefault("max_digits", 36)
        kwargs.setdefault("decimal_places", 18)
        kwargs.setdefault("default_currency", "USD")
        if kwargs.pop("shared_currency", False):
            kwargs.setdefault("currency_field_name", "currency")
        super().__init__(verbose_name, name, **kwargs)


class Owner(models.Model):
    """
    Owner is an account holder reference.

    It has limited information and currently only holds a name.
    """

    name = models.SlugField(
        unique=True,
        help_text="Unique string that identifies owner. May only contain"
                  " letters, numbers, underscores and hyphens."
    )

    def __str__(self):
        """Return text representation of the Owner, currently their name."""
        return self.name


class Account(models.Model):
    """A money-holding account."""

    name = models.SlugField(
        unique=True,
        help_text="Unique account identifier. May only contain letters,"
                  " numbers, underscores and hyphens."
    )
    owner = models.ForeignKey(
        Owner, on_delete=models.PROTECT, help_text="Account owner's ID."
    )
    balance = MoneyField(shared_currency=True, editable=False)

    def __str__(self):
        """Return text representation of the Account, currently its name."""
        return self.name


class Payment(models.Model):
    """
    A transaction between two accounts.

    One side (``from_account`` or ``to_account``) account can be ``None``,
    in case of money deposits or withdrawals.
    """

    # Essential properties (where from, where to, amount)
    from_account = models.ForeignKey(
        Account, blank=True, null=True, on_delete=models.CASCADE,
        related_name="payments_from"
    )
    to_account = models.ForeignKey(
        Account, blank=True, null=True, on_delete=models.CASCADE,
        related_name="payments_to"
    )
    amount = MoneyField(shared_currency=True)

    # Metadata
    time = models.DateTimeField(default=timezone.now, editable=False)

    # Confirmation / replay protection fields
    # See the PaymentViewSet for more information
    unique_id = models.CharField(max_length=64, unique=True)
    confirmed = models.BooleanField(blank=True)

    # Accounting helper properties, keep balance history
    source_balance_before = MoneyField(null=True, shared_currency=True)
    destination_balance_before = MoneyField(null=True, shared_currency=True)

    def __str__(self):
        """Return a short string describing the payment. Not i18n-aware."""
        amount = str(self.amount)
        source = str(self.from_account)
        destination = str(self.to_account)

        if self.from_account is None:
            return f"Deposit {amount} to {destination}"
        elif self.to_account is None:
            return f"Withdraw {amount} from {source}"
        else:
            return f"Transfer {amount} from {source} to {destination}"

    def confirm(self, commit: bool = True,
                from_account: Account = None,
                to_account: Account = None) -> None:
        """
        Confirm the payment, adjusting the account balances.

        Must be called in a transaction or bad things would happen.
        Also, if the accounts were not fetched for update you want
        to re-fetch and supply them separately.

        :param commit: Whenever to call `save` on the instance or not.
            Note, `from_account` and `to_account` are always saved.
        :param from_account: If specified, the `from_account` to use instead.
            This is if the `self.from_account` wasn't `select_for_update`d.
        :param to_account: If specified, the `to_account` to use instead.
            This is if the `self.to_account` wasn't `select_for_update`d.
        :raises ValueError: May be raised on various problems.
        """
        if self.confirmed:
            # TODO: Possibly, use a ValueError subclass AlreadyConfirmedError?
            raise ValueError("Payment is already confirmed")

        if from_account is None:
            from_account = self.from_account
        elif self.from_account is None or from_account != self.from_account:
            raise RuntimeError("Provided from_account does not match")

        if to_account is None:
            to_account = self.to_account
        elif self.to_account is None or to_account != self.to_account:
            raise RuntimeError("Provided to_account does not match")

        self.confirmed = True
        if from_account is not None:
            if from_account.balance < self.amount:
                raise ValueError("Insufficient funds")
            self.source_balance_before = from_account.balance
            from_account.balance -= self.amount
            from_account.save(update_fields=["balance"])
        if to_account is not None:
            self.destination_balance_before = to_account.balance
            to_account.balance += self.amount
            to_account.save(update_fields=["balance"])

        if commit:
            self.save()
