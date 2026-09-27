from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.models import F, ProtectedError
from django.utils import timezone

from apps.events.models import Event, TicketType
from common.tests.helpers import assert_violates

from .factories import CategoryFactory, EventFactory, TicketTypeFactory, VenueFactory

pytestmark = pytest.mark.django_db


class TestTicketType:
    def test_quantity_available_defaults_to_total(self):
        ticket_type = TicketTypeFactory(quantity_total=40)

        assert ticket_type.quantity_available == 40
        assert ticket_type.quantity_sold == 0

    def test_database_blocks_overselling(self):
        """Even a raw decrement that skips app checks can't push stock below zero."""
        ticket_type = TicketTypeFactory(quantity_total=2)
        queryset = TicketType.objects.filter(pk=ticket_type.pk)

        queryset.update(quantity_available=F("quantity_available") - 2)
        assert_violates(
            "ticket_type_quantity_available_non_negative",
            lambda: queryset.update(quantity_available=F("quantity_available") - 1),
        )
        ticket_type.refresh_from_db()
        assert ticket_type.quantity_available == 0

    def test_available_cannot_exceed_total(self):
        assert_violates(
            "ticket_type_available_lte_total",
            lambda: TicketTypeFactory(quantity_total=10, quantity_available=11),
        )

    def test_price_cannot_be_negative(self):
        assert_violates(
            "ticket_type_price_non_negative", lambda: TicketTypeFactory(price=Decimal("-1"))
        )

    def test_quantity_total_cannot_be_negative(self):
        # Rejected via available >= 0 (available defaults to total).
        assert_violates(
            "ticket_type_quantity_available_non_negative",
            lambda: TicketTypeFactory(quantity_total=-1),
        )

    def test_name_is_unique_per_event_only(self):
        event = EventFactory()
        TicketTypeFactory(event=event, name="VIP")
        TicketTypeFactory(name="VIP")  # same name on another event is fine

        assert_violates(
            "unique_ticket_type_name_per_event", lambda: TicketTypeFactory(event=event, name="VIP")
        )

    def test_full_clean_reports_constraint_as_validation_error(self):
        """The admin calls full_clean, so constraint violations become form errors, not 500s."""
        ticket_type = TicketTypeFactory.build(
            event=EventFactory(), quantity_total=5, quantity_available=6
        )

        with pytest.raises(ValidationError, match="cannot exceed the total"):
            ticket_type.full_clean()

    def test_full_clean_fills_in_available_quantity(self):
        ticket_type = TicketTypeFactory.build(event=EventFactory(), quantity_total=5)

        ticket_type.full_clean()

        assert ticket_type.quantity_available == 5


class TestEvent:
    def test_must_end_after_it_starts(self):
        starts_at = timezone.now() + timedelta(days=1)

        assert_violates(
            "event_ends_after_starts", lambda: EventFactory(starts_at=starts_at, ends_at=starts_at)
        )

    def test_max_tickets_per_user_must_be_positive(self):
        assert_violates(
            "event_max_tickets_per_user_positive", lambda: EventFactory(max_tickets_per_user=0)
        )

    def test_status_must_be_valid(self):
        assert_violates("event_status_valid", lambda: EventFactory(status="postponed"))

    def test_defaults(self):
        event = Event.objects.create(
            organizer=EventFactory().organizer,
            venue=VenueFactory(),
            title="Defaults",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=2),
        )

        assert event.status == Event.Status.DRAFT
        assert event.max_tickets_per_user == 10
        assert str(event) == "Defaults"

    def test_has_started(self):
        assert not EventFactory().has_started
        assert EventFactory(starts_at=timezone.now() - timedelta(hours=1)).has_started

    def test_categories(self):
        event = EventFactory()
        music = CategoryFactory(name="Music")
        event.categories.add(music)

        assert list(music.events.all()) == [event]
        assert str(music) == "Music"

    def test_deleting_event_deletes_its_ticket_types(self):
        ticket_type = TicketTypeFactory()

        ticket_type.event.delete()

        assert not TicketType.objects.exists()

    def test_venue_and_organizer_with_events_are_protected(self):
        event = EventFactory()

        with pytest.raises(ProtectedError):
            event.venue.delete()
        with pytest.raises(ProtectedError):
            event.organizer.delete()


class TestVenue:
    def test_capacity_must_be_positive(self):
        assert_violates("venue_capacity_positive", lambda: VenueFactory(capacity=0))

    def test_str(self):
        assert str(VenueFactory(name="Arena", city="Pune")) == "Arena, Pune"
