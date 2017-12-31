from django.db import IntegrityError, transaction

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import mixins, response, status, viewsets
from rest_framework.response import Response

from . import filters, models, serializers


class OwnerViewSet(mixins.CreateModelMixin,
                   mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   viewsets.GenericViewSet):
    """
    This viewset allows to manage owners.

    list:
    Return a list of all owners registered in the system.

    retrieve:
    Returns the given owner.

    This is not particularly useful, since all the information
    the API currentyl handles about the owner is their name,
    and this is already present in the URL. Still, this could be
    used for existence checks.

    create:
    Creates the given owner.

    destroy:
    Deletes all the information about the owner, including their accounts.
    The deletion is only allowed if all accounts have zero balances.
    """

    queryset = models.Owner.objects.order_by("name")
    lookup_field = "name"
    serializer_class = serializers.OwnerSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("name",)

    def destroy(self, request, *args, **kwargs):
        """
        Delete the account.

        Only succeeds if the balance is zero.
        """
        try:
            with transaction.atomic():
                instance = self.get_object()
                if not instance.account_set.exclude(balance=0).exists():
                    # The condition above is merely a check, not a guarantee.
                    # At least, not with all possible serialization levels.
                    # We have `on_delete=PROTECT` on `Account.owner`, so here
                    # we delete only zero-balance accounts and if there's
                    # something still left, the `instance.delete` would fail.
                    instance.account_set.filter(balance=0).delete()
                    instance.delete()
                    return response.Response(status=status.HTTP_204_NO_CONTENT)
        except IntegrityError:  # pragma: nocover
            # Deletion had failed, transaction should be rolled back now.
            pass
        return response.Response(
            {"error": "All belonging accounts must have zero balance"},
            status=status.HTTP_400_BAD_REQUEST
        )


class AccountViewSet(mixins.CreateModelMixin,
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    This viewset allows to manage accounts.

    list:
    Returns a list of all accounts registered in the system.

    retrieve:
    Returns the given account.

    create:
    Creates a new account for the given owner.

    You must specify the currency, but the balance will always
    start at zero.

    destroy:
    Deletes the account. Only accounts with zero balance can be deleted.
    """

    queryset = models.Account.objects.order_by("name")
    lookup_field = "name"
    serializer_class = serializers.AccountSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.AccountFilter

    def get_serializer_class(self):
        """
        Return the appropriate serializer class.

        Normally it's AccountSerializer, but for the "create" action
        it's AccountCreateSerializer instead.
        """
        if self.action == "create":
            return serializers.AccountCreateSerializer
        else:
            return super().get_serializer_class()

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete the account.

        Only succeeds if the balance is zero.
        """
        instance = self.get_object()
        if instance.balance.amount == 0:
            instance.delete()
            return response.Response(status=status.HTTP_204_NO_CONTENT)
        return response.Response(
            {"error": "Only accounts with zero balance can be deleted"},
            status=status.HTTP_400_BAD_REQUEST
        )


class PaymentViewSet(mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.CreateModelMixin,
                     viewsets.GenericViewSet):
    """
    This viewset allows to view and perform payments.

    list:
    Returns a list of all payments known to the system.

    retrieve:
    Returns the given payment.

    create:
    Performs the new payment. See ``create`` method's docstring for details.
    """

    # TODO: Filters
    # TODO: Cursor or alike pagination, pages or offsets don't fit here.
    queryset = models.Payment.objects.select_related(
        "from_account", "to_account"
    ).order_by("pk")
    serializer_class = serializers.PaymentSerializer

    def get_serializer_class(self):
        """
        Return the appropriate serializer class.

        Normally it's PaymentSerializer, but for the update actions
        it's PaymentConfirmSerializer instead.
        """
        if self.action in ("partial_update", "update"):
            return serializers.PaymentConfirmSerializer
        else:
            return super().get_serializer_class()

    # NOTE: We don't need transaction.atomic on this method, because
    # the PaymentConfirmSerializer does transaction management on its own.
    def partial_update(self, request, *args, **kwargs):
        """Confirm the previously unconfirmed payment, adjusting balances."""
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        updated_instance = serializer.save()
        if getattr(updated_instance, "_not_modified", False):
            # HAX: Okay, responding with HTTP 304 is not exactly standard,
            # but this is the sanest I came up with. 409 was another option.
            # We should be retuning all the required headers anyway,
            # and empty body requirement is actually handy so we don't have
            # to switch serializers. But YMMV.
            return response.Response(status=status.HTTP_304_NOT_MODIFIED)

        if hasattr(instance, "_prefetched_objects_cache"):  # pragma: nocover
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Perform the new payment, adjusting the account balances.

        Either of the ``from_account`` and ``to_account`` fields can
        be omitted, but at least one is required. If only one account
        is specified, payment is treated as a deposit or withdrawal.

        If the ``unique_id`` is provided, the transaction is marked
        as ``confirmed`` and account balances are adjusted respectively.

        If not, the account balances are left intact and payment
        is created with ``confirmed`` set to ``False``, requiring a second
        step to commit the transaction.

        Note, the funds for uncommitted transactions are *not* frozen
        or otherwise reserved.
        """
        # The whole point of this function is in the ``atomic`` decorator.
        return super().create(request, *args, **kwargs)
