"""
The overselling proof: many buyers hit place_order at the same instant on real
PostgreSQL. Run repeatedly with: pytest apps/orders/tests/test_concurrency.py --count=20
"""

import time
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.tests.factories import OrganizerFactory, UserFactory
from apps.events.models import TicketType
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.orders.models import Order, Ticket
from apps.orders.services import SoldOut, check_in, mark_order_paid, place_order
from common.exceptions import Conflict
from common.tests.helpers import run_concurrently

pytestmark = pytest.mark.django_db(transaction=True)


def split(results, *expected_errors):
    """Separate successful orders from expected failures; anything else fails the test."""
    orders = [r for r in results if isinstance(r, Order)]
    errors = [r for r in results if not isinstance(r, Order)]
    unexpected = [e for e in errors if not isinstance(e, expected_errors)]
    assert not unexpected, unexpected
    return orders, errors


def stock(ticket_type):
    ticket_type.refresh_from_db()
    return ticket_type.quantity_available


def test_last_ticket_is_sold_exactly_once():
    ticket_type = TicketTypeFactory(quantity_total=1)
    buyers = UserFactory.create_batch(20)

    results = run_concurrently(
        lambda user: place_order(user, ticket_type.event_id, [(ticket_type.pk, 1)]), buyers
    )

    orders, errors = split(results, SoldOut)
    assert len(orders) == 1
    assert len(errors) == 19
    assert stock(ticket_type) == 0
    assert Ticket.objects.count() == 1


def test_stock_is_never_exceeded():
    ticket_type = TicketTypeFactory(quantity_total=10)
    buyers = UserFactory.create_batch(30)

    results = run_concurrently(
        lambda user: place_order(user, ticket_type.event_id, [(ticket_type.pk, 1)]), buyers
    )

    orders, _ = split(results, SoldOut)
    assert len(orders) == 10
    assert stock(ticket_type) == 0
    assert Ticket.objects.count() == 10


def test_multi_ticket_orders_never_split_the_last_seats():
    ticket_type = TicketTypeFactory(quantity_total=10)
    buyers = UserFactory.create_batch(8)

    results = run_concurrently(
        lambda user: place_order(user, ticket_type.event_id, [(ticket_type.pk, 3)]), buyers
    )

    orders, _ = split(results, SoldOut)
    assert len(orders) == 3  # 3 x 3 = 9; a fourth order of 3 can't fit in the last seat
    assert stock(ticket_type) == 1
    assert Ticket.objects.count() == 9


def test_per_user_limit_holds_when_one_user_races_themselves():
    ticket_type = TicketTypeFactory(event=EventFactory(max_tickets_per_user=2), quantity_total=50)
    user = UserFactory()

    results = run_concurrently(
        lambda _: place_order(user, ticket_type.event_id, [(ticket_type.pk, 1)]), range(10)
    )

    orders, _ = split(results, ValidationError)
    assert len(orders) == 2
    assert Ticket.objects.filter(order__user=user).count() == 2
    assert stock(ticket_type) == 48


def test_orders_listing_tiers_in_opposite_order_do_not_deadlock():
    """Locks are always taken in pk order, whatever order the items arrive in."""
    first = TicketTypeFactory(quantity_total=100)
    second = TicketTypeFactory(event=first.event, quantity_total=100)
    buyers = UserFactory.create_batch(20)

    def book(user):
        items = [(first.pk, 1), (second.pk, 1)]
        if user.pk % 2:
            items.reverse()
        return place_order(user, first.event_id, items)

    orders, _ = split(run_concurrently(book, buyers))
    assert len(orders) == 20
    assert (stock(first), stock(second)) == (80, 80)


def naive_place_order(user, ticket_type_id):
    """What booking looks like WITHOUT locks or F(): read, check, then write."""
    ticket_type = TicketType.objects.get(pk=ticket_type_id)
    if ticket_type.quantity_available < 1:
        raise SoldOut()  # pragma: no cover - every racer reads the stale 1
    time.sleep(0.05)  # a little work between the check and the write widens the race window
    ticket_type.quantity_available -= 1
    ticket_type.save(update_fields=["quantity_available"])
    order = Order.objects.create(user=user, expires_at=timezone.now() + timedelta(minutes=15))
    Ticket.objects.create(order=order, ticket_type=ticket_type, price_paid=ticket_type.price)
    return order


def test_negative_control_naive_booking_oversells():
    """
    Proves the harness really produces races: under the same conditions that
    place_order survives, the naive version sells one seat many times over.
    The constraint can't catch it either, because every stale write sets 0, not -1.
    """
    ticket_type = TicketTypeFactory(quantity_total=1)
    buyers = UserFactory.create_batch(10)

    results = run_concurrently(lambda user: naive_place_order(user, ticket_type.pk), buyers)

    orders, _ = split(results, SoldOut)
    assert len(orders) > 1, "expected the unlocked version to oversell"
    assert stock(ticket_type) == 0
    assert Ticket.objects.count() == len(orders)


def test_simultaneous_scans_admit_a_ticket_once():
    organizer = OrganizerFactory()
    ticket_type = TicketTypeFactory(event=EventFactory(organizer=organizer))
    order = mark_order_paid(place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 1)]))
    code = order.tickets.get().code

    results = run_concurrently(lambda _: check_in(code, organizer), range(10))

    admitted = [r for r in results if isinstance(r, Ticket)]
    rejected = [r for r in results if isinstance(r, Conflict)]
    assert (len(admitted), len(rejected)) == (1, 9)
    assert Ticket.objects.get(code=code).checked_in_at == admitted[0].checked_in_at
