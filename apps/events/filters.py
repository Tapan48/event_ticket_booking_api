import django_filters as filters
from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework.exceptions import NotAuthenticated

from .models import Event, TicketType, Venue


class VenueFilter(filters.FilterSet):
    city = filters.CharFilter(lookup_expr="iexact", help_text="City (case-insensitive).")
    mine = filters.BooleanFilter(method="filter_mine", help_text="Only venues you created.")

    def filter_mine(self, queryset, name, value):
        if not value:
            return queryset
        if not self.request.user.is_authenticated:
            raise NotAuthenticated()
        return queryset.filter(created_by=self.request.user)

    class Meta:
        model = Venue
        fields = ["city"]


class EventFilter(filters.FilterSet):
    mine = filters.BooleanFilter(method="filter_mine", help_text="Only events you organize.")

    def filter_mine(self, queryset, name, value):
        if not value:
            return queryset
        if not self.request.user.is_authenticated:
            raise NotAuthenticated()
        return queryset.filter(organizer=self.request.user)

    city = filters.CharFilter(
        field_name="venue__city", lookup_expr="iexact", help_text="Venue city (case-insensitive)."
    )
    category = filters.CharFilter(field_name="categories__slug", help_text="Category slug.")
    starts_after = filters.IsoDateTimeFilter(
        field_name="starts_at",
        lookup_expr="gte",
        help_text="Starts at or after this ISO date/datetime (UTC if no offset).",
    )
    starts_before = filters.IsoDateTimeFilter(
        field_name="starts_at",
        lookup_expr="lt",
        help_text="Starts before this ISO date/datetime (UTC if no offset).",
    )
    upcoming = filters.BooleanFilter(
        method="filter_upcoming", help_text="true: not started yet; false: already started."
    )
    # Applied together in filter_queryset so both bounds hit the same ticket type.
    min_price = filters.NumberFilter(
        method="filter_price", help_text="Has a ticket type priced at least this."
    )
    max_price = filters.NumberFilter(
        method="filter_price", help_text="Has a ticket type priced at most this."
    )

    class Meta:
        model = Event
        fields = ["status"]

    def filter_upcoming(self, queryset, name, value):
        now = timezone.now()
        return queryset.filter(starts_at__gt=now) if value else queryset.filter(starts_at__lte=now)

    def filter_price(self, queryset, name, value):
        return queryset  # see filter_queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        low = self.form.cleaned_data.get("min_price")
        high = self.form.cleaned_data.get("max_price")
        if low is None and high is None:
            return queryset
        # One EXISTS over a single ticket type: chaining two filters on the multi-valued
        # relation could satisfy min and max with different tiers (and duplicate rows).
        tiers = TicketType.objects.filter(event=OuterRef("pk"))
        if low is not None:
            tiers = tiers.filter(price__gte=low)
        if high is not None:
            tiers = tiers.filter(price__lte=high)
        return queryset.filter(Exists(tiers))
