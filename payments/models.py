from django.db import models

from djmoney.models.fields import MoneyField


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
    balance = MoneyField(
        max_digits=36, decimal_places=18,
        default_currency="USD",
        currency_field_name="currency",
        editable=False
    )

    def __str__(self):
        """Return text representation of the Account, currently its name."""
        return self.name
