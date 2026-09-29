from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.tests.factories import UserFactory
from apps.events.models import Event
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.orders import services
from apps.orders.models import Order, Ticket
from apps.orders.services import (
    SoldOut,
    cancel_order,
    mark_order_paid,
    place_order,
    release_order,
)
from common.exceptions import Conflict

pytestmark = pytest.mark.django_db


def stock(ticket_type):
    ticket_type.refresh_from_db()
    return ticket_type.quantity_available


class TestPlaceOrder:
    def test_reserves_tickets_and_decrements_stock(self, settings):
        settings.ORDER_TTL_MINUTES = 15
        user = UserFactory()
        general = TicketTypeFactory(price=Decimal("100.00"), quantity_total=10)
        vip = TicketTypeFactory(event=general.event, price=Decimal("250.00"), quantity_total=5)

        order = place_order(user, general.event_id, [(general.pk, 2), (vip.pk, 1)])

        assert order.status == Order.Status.PENDING
        assert order.user == user
        assert order.total_amount == Decimal("450.00")
        assert timedelta(minutes=14) < order.expires_at - timezone.now() <= timedelta(minutes=15)
        assert (stock(general), stock(vip)) == (8, 4)
        assert sorted(order.tickets.values_list("price_paid", flat=True)) == [
            Decimal("100.00"),
            Decimal("100.00"),
            Decimal("250.00"),
        ]

    def test_merges_duplicate_items(self):
        ticket_type = TicketTypeFactory(quantity_total=10)

        order = place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 1)] * 3)

        assert order.tickets.count() == 3
        assert stock(ticket_type) == 7

    @pytest.mark.parametrize("items", [[], [(1, 0)], [(1, -2)]])
    def test_rejects_empty_or_non_positive_items(self, items):
        with pytest.raises(ValidationError):
            place_order(UserFactory(), 1, items)

    def test_rejects_ticket_types_from_another_event(self):
        ticket_type = TicketTypeFactory()
        other_event = EventFactory()

        with pytest.raises(ValidationError, match="belong to this event"):
            place_order(UserFactory(), other_event.pk, [(ticket_type.pk, 1)])

    @pytest.mark.parametrize("status", [Event.Status.DRAFT, Event.Status.CANCELLED])
    def test_rejects_unpublished_events(self, status):
        ticket_type = TicketTypeFactory(event=EventFactory(status=status))

        with pytest.raises(ValidationError, match="isn't open"):
            place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 1)])

    def test_rejects_events_that_have_started(self):
        started = EventFactory(
            starts_at=timezone.now() - timedelta(minutes=5),
            ends_at=timezone.now() + timedelta(hours=2),
        )
        ticket_type = TicketTypeFactory(event=started)

        with pytest.raises(ValidationError, match="already started"):
            place_order(UserFactory(), started.pk, [(ticket_type.pk, 1)])

    def test_sold_out_leaves_everything_untouched(self):
        general = TicketTypeFactory(quantity_total=5)
        scarce = TicketTypeFactory(event=general.event, name="Front Row", quantity_total=1)

        with pytest.raises(SoldOut, match="Only 1 'Front Row'"):
            place_order(UserFactory(), general.event_id, [(general.pk, 2), (scarce.pk, 2)])

        assert (stock(general), stock(scarce)) == (5, 1)
        assert not Order.objects.exists()

    def test_per_user_limit_spans_orders(self):
        ticket_type = TicketTypeFactory(event=EventFactory(max_tickets_per_user=3))
        user = UserFactory()
        place_order(user, ticket_type.event_id, [(ticket_type.pk, 2)])

        with pytest.raises(ValidationError, match="at most 3 tickets"):
            place_order(user, ticket_type.event_id, [(ticket_type.pk, 2)])

        place_order(user, ticket_type.event_id, [(ticket_type.pk, 1)])  # exactly at the limit
        place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 3)])  # others unaffected

    def test_released_orders_do_not_count_toward_the_limit(self):
        ticket_type = TicketTypeFactory(event=EventFactory(max_tickets_per_user=2))
        user = UserFactory()
        cancel_order(place_order(user, ticket_type.event_id, [(ticket_type.pk, 2)]))

        order = place_order(user, ticket_type.event_id, [(ticket_type.pk, 2)])

        assert order.tickets.count() == 2

    def test_database_constraint_is_mapped_to_sold_out(self, monkeypatch):
        """If the app-level check were skipped, the CHECK constraint still refuses the sale."""
        ticket_type = TicketTypeFactory(quantity_total=1)
        monkeypatch.setattr(services, "_check_availability", lambda *args: None)

        with pytest.raises(SoldOut):
            place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 2)])

        assert stock(ticket_type) == 1

    def test_other_integrity_errors_are_not_masked(self, monkeypatch):
        ticket_type = TicketTypeFactory()

        def broken_create(**kwargs):
            raise IntegrityError("some_other_constraint")

        monkeypatch.setattr(services.Order.objects, "create", broken_create)

        with pytest.raises(IntegrityError, match="some_other_constraint"):
            place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 1)])

        assert stock(ticket_type) == 100


class TestReleaseAndCancel:
    def test_cancel_restores_stock(self):
        ticket_type = TicketTypeFactory(quantity_total=10)
        order = place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 4)])

        cancelled = cancel_order(order)

        assert cancelled.status == Order.Status.CANCELLED
        assert stock(ticket_type) == 10

    def test_release_is_idempotent(self):
        ticket_type = TicketTypeFactory(quantity_total=10)
        order = place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 4)])

        release_order(order, Order.Status.EXPIRED)
        release_order(order, Order.Status.EXPIRED)
        release_order(order, Order.Status.CANCELLED)

        order.refresh_from_db()
        assert order.status == Order.Status.EXPIRED
        assert stock(ticket_type) == 10

    def test_paid_orders_cannot_be_cancelled(self):
        ticket_type = TicketTypeFactory(quantity_total=10)
        order = mark_order_paid(
            place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 1)])
        )

        with pytest.raises(Conflict, match="this one is paid"):
            cancel_order(order)

        assert stock(ticket_type) == 9


class TestMarkOrderPaid:
    def test_marks_pending_order_paid(self):
        ticket_type = TicketTypeFactory()
        order = place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 1)])

        paid = mark_order_paid(order)

        assert paid.status == Order.Status.PAID
        assert paid.paid_at is not None

    def test_cannot_pay_twice(self):
        ticket_type = TicketTypeFactory()
        order = mark_order_paid(
            place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 1)])
        )

        with pytest.raises(Conflict, match="this one is paid"):
            mark_order_paid(order)

    def test_paying_after_expiry_releases_the_tickets(self):
        ticket_type = TicketTypeFactory(quantity_total=10)
        order = place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 3)])
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(seconds=1))

        with pytest.raises(Conflict, match="expired"):
            mark_order_paid(order)

        order.refresh_from_db()
        assert order.status == Order.Status.EXPIRED
        assert stock(ticket_type) == 10
        assert Ticket.objects.filter(order=order).count() == 3  # kept for the record
