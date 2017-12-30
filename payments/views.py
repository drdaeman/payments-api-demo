from django.db import IntegrityError, transaction

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import mixins, response, status, viewsets

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
