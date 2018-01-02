import base64
import collections
import re
from typing import Optional

import coreapi

import coreschema

from django.utils.encoding import force_text

from rest_framework import pagination
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param


class Cursor(collections.namedtuple("Cursor", "cmp pk")):
    """
    A pagination cursor data.

    Cursors refer to specific `pk` value and comparision (`cmp`) to use
    relative to this PK. E.g. if "this" page ends at PK=100, the "next"
    page should be `Cursor(cmp="<", pk=100)` (it's less than 100, because
    we assume that PK values increase with time)

    See `MonotonicCursorPagination` for more details.
    """

    @classmethod
    def decode(cls, text: str) -> "Cursor":
        """
        Decode cursor string and return new instance (or raise ValueError).

        It is not recommended to generate encoded strings with anything else
        but the `Cursor.encode` method.

        :param text: An encoded cursor data, as received from client.
        :return: The decoded Cursor instance (or a subclass).
        :raises ValueError: In case of any problems with the encoded data
        """
        try:
            padded_text = text + "=" * (-len(text) % 4)
            data = base64.urlsafe_b64decode(padded_text).decode("ascii")
        except UnicodeDecodeError:
            raise ValueError("Invalid cursor value")
        m = re.match(r"^([><]=?)(\d+)$", data)
        if not m:
            raise ValueError("Invalid cursor value")
        return cls(
            cmp=m.group(1),
            pk=int(m.group(2))
        )

    def encode(self) -> str:
        """
        Encode the Cursor as a string.

        The data can be decoded back using `Cursor.decode` method.
        """
        return base64.urlsafe_b64encode(
            "{cmp}{pk}".format(
                cmp=self.cmp,
                pk=self.pk
            ).encode("ascii")
        ).rstrip(b"=").decode("ascii")

    @property
    def cmp_name(self) -> str:
        """Return a comparision name usable with Django QuerySet filters."""
        return {
            ">": "gt",
            "<": "lt",
            ">=": "gte",
            "<=": "lte"
        }[self.cmp]


class MonotonicCursorPagination(pagination.BasePagination):
    """
    A pagination class that implements cursor-like pagination on ordered data.

    This class assumes queryset has is a totally ordered unique sequential IDs,
    like PostgreSQL's SERIAL fields and that those ID values monotonically
    increase over time. Very frequently, the "pk" fields are exactly like this.

    For each request, three links are returned:

    - `links.this` - the URL one can use to refresh the page. Should return
      the same data. May be `null` under some rare circumstance, like an
      empty database.

    - `links.next` - the URL to go deeper in history, to the older items.
      If `null`, this means there are no more items available.

    - `links.prev` - the URL to check for the new items (if any).
      May be `null` under the same rare conditions as `links.this`.

    The links differ by their `cursor` query string argument (this name can
    be changed using `cursor_query_param` class attribute). The values of
    the `cursor` argument should be treated as opaque and only used intact.

    Number of items is controlled by the `limit` query argument, and the
    argument's name can be changed using `page_size_query_param` attribute.
    The default value is `page_size` and maximum possible custom value
    is defined by the `max_page_size` attribute.
    """

    pk_field = "pk"
    cursor_query_param = "cursor"
    page_size_query_param = "limit"
    page_size = 100
    max_page_size = 1000

    # TODO: I18N: Consider wrapping those in gettext() for better reusability
    cursor_query_description = "The pagination cursor value."
    page_size_query_description = "Number of results to return per page."

    def __init__(self):  # noqa: D107
        super().__init__()

        # This is not strictly required as DRF is always supposed to call
        # the paginate_queryset, which makes sure the attributes would be
        # properly set. But it is here just to keep PyCharm's static
        # analyzer happy.
        self.base_url = None
        self.cursor = None
        self.next_cursor = None
        self.prev_cursor = None

    def paginate_queryset(self, queryset, request, view=None):
        """Perform the queryset pagination based on request data."""
        self.base_url = request.build_absolute_uri()

        limit = self.get_page_size(request)
        self.cursor = self.get_cursor(request)

        order_desc = True
        if self.cursor:
            flt = {f"{self.pk_field}__{self.cursor.cmp_name}": self.cursor.pk}
            queryset = queryset.filter(**flt)
            if self.cursor.cmp.startswith(">"):
                # ">" and ">=" cmps means we look forward, for newer entries
                # In such case we don't need a limit+1 and we need to fetch
                # the oldest entries that match the cursor cutoff
                order_desc = False

        if order_desc:
            # Fetch one more item over the limit to see if there is next page
            results = list(queryset.order_by("-" + self.pk_field)[:limit + 1])
        else:
            results = list(queryset.order_by(self.pk_field)[:limit])
            results.reverse()

        if len(results) > limit:
            # Use next item's PK as a reference. Next page should start
            # with that item, so use "<=" lookup.
            next_pk = getattr(results[limit], self.pk_field)
            self.next_cursor = Cursor("<=", next_pk)
        else:
            # There is no more items. We've fetched everything there is.
            # (Assuming that no one would insert items with low PKs, of course)
            self.next_cursor = None

        if len(results) > 0:
            first_pk = getattr(results[0], self.pk_field)
            # Previous page should start with PK greater than first one
            # we have on this page, so ">" lookup (PKs increase).
            #
            # Note, the "previous" actually means "newer" - that's because
            # the direction is from future to the past and "next"
            # means "continue with older results".
            self.prev_cursor = Cursor(">", first_pk)
            if not self.cursor:
                # If we don't have cursor, define one for this page.
                # Start with first item and do down the PK ("<=")
                self.cursor = Cursor("<=", first_pk)
        elif self.cursor:
            # We don't have any results, but we have the cursor.
            # This could've happened if the item was there but is now gone.
            # Therefore, "this" is "<=pk" and "prev" is ">pk".
            self.prev_cursor = Cursor(">", self.cursor.pk)
        else:
            # There are no results and no cursor, so no PK to refer to.
            # The client should retry with bare endpoint URL (w/o cursor arg)
            self.prev_cursor = None

        return list(results[:limit])

    def get_paginated_response(self, data):
        """Return a paginated response with `links` and `results` objects."""
        return Response({
            "links": {
                "this": self.get_link(self.cursor),
                "next": self.get_link(self.next_cursor),
                "prev": self.get_link(self.prev_cursor),
            },
            "results": data,
        })

    def get_link(self, cursor: Cursor) -> Optional[str]:
        """
        Return a link a page with a specific cursor value encoded.

        For convenience, returns `None` if `cursor` is `None`.
        """
        if cursor is None:
            return None
        return replace_query_param(
            self.base_url, self.cursor_query_param, cursor.encode()
        )

    def get_cursor(self, request) -> Optional[Cursor]:
        """Return the cursor parameter, if provided and None otherwise."""
        cursor_text = request.query_params.get(self.cursor_query_param, None)
        if not cursor_text:
            return None
        try:
            return Cursor.decode(cursor_text)
        except ValueError:
            raise ValidationError("Bad cursor value")

    def get_page_size(self, request) -> int:
        """
        Return the requested page size, as defined by `page_size_query_param`.

        The query value is limited by `max_page_size` and cannot exceed it.
        If not requested or invalid value is passed `page_size` is returned.
        """
        limit = request.query_params.get(self.page_size_query_param, None)
        if limit and re.match(r"^\d+$", limit):
            limit = int(limit)
            if limit > 0:
                return min(limit, self.max_page_size)
        return self.page_size

    def to_html(self):  # pragma: nocover
        """Supposed to return HTML page controls, but not yet implemented."""
        # We're not using BrowsableAPIRenderer anyway, so not important
        raise NotImplementedError("Page controls are not implemented")

    def get_schema_fields(self, view):  # pragma: nocover
        """Return list of fields for the CoreAPI schema generator."""
        assert coreapi is not None, \
            "coreapi must be installed to use `get_schema_fields()`"
        assert coreschema is not None,\
            "coreschema must be installed to use `get_schema_fields()`"

        fields = [
            coreapi.Field(
                name=self.cursor_query_param,
                required=False,
                location="query",
                schema=coreschema.String(
                    title="Cursor",
                    description=force_text(self.cursor_query_description)
                )
            )
        ]
        if self.page_size_query_param is not None:
            fields.append(coreapi.Field(
                name=self.page_size_query_param,
                required=False,
                location="query",
                schema=coreschema.Integer(
                    title="Page size",
                    description=force_text(self.page_size_query_description)
                )
            ))
        return fields
