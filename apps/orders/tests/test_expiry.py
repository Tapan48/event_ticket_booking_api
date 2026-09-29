from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.orders.models import Order
from apps.orders.services import cancel_order, expire_stale_orders, mark_order_paid, place_order
from apps.orders.tasks import expire_stale_orders as expire_task
from config import celery_app

pytestmark = pytest.mark.django_db


def backdate(order):
    Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))


def stock(ticket_type):
    ticket_type.refresh_from_db()
    return ticket_type.quantity_available


def status(order):
    order.refresh_from_db()
    return order.status


@pytest.fixture
def ticket_type():
    return TicketTypeFactory(quantity_total=20)


def book(ticket_type, quantity=2, user=None):
    return place_order(user or UserFactory(), ticket_type.event_id, [(ticket_type.pk, quantity)])


def test_expires_overdue_orders_and_restores_stock(ticket_type):
    overdue = [book(ticket_type), book(ticket_type)]
    for order in overdue:
        backdate(order)
    fresh = book(ticket_type)

    assert expire_stale_orders() == 2

    assert [status(o) for o in overdue] == [Order.Status.EXPIRED] * 2
    assert status(fresh) == Order.Status.PENDING
    assert stock(ticket_type) == 18  # only the fresh order's 2 tickets are still held


def test_leaves_paid_and_cancelled_orders_alone(ticket_type):
    paid = mark_order_paid(book(ticket_type))
    cancelled = cancel_order(book(ticket_type))
    backdate(paid)
    backdate(cancelled)

    assert expire_stale_orders() == 0

    assert (status(paid), status(cancelled)) == (Order.Status.PAID, Order.Status.CANCELLED)
    assert stock(ticket_type) == 18


def test_is_idempotent(ticket_type):
    backdate(book(ticket_type, 5))

    assert expire_stale_orders() == 1
    assert expire_stale_orders() == 0
    assert stock(ticket_type) == 20


def test_processes_at_most_limit_per_run(ticket_type):
    for _ in range(3):
        backdate(book(ticket_type, 1))

    assert expire_stale_orders(limit=2) == 2
    assert expire_stale_orders(limit=2) == 1


def test_expiry_frees_the_per_user_limit():
    ticket_type = TicketTypeFactory(event=EventFactory(max_tickets_per_user=2))
    user = UserFactory()
    backdate(book(ticket_type, 2, user=user))
    expire_stale_orders()

    assert book(ticket_type, 2, user=user).tickets.count() == 2


def test_task_wraps_the_service(ticket_type):
    backdate(book(ticket_type))

    assert expire_task.delay().get() == 1


def test_beat_runs_the_task_every_minute():
    entry = settings.CELERY_BEAT_SCHEDULE["expire-stale-orders"]

    assert entry["schedule"] == 60.0
    assert entry["task"] in celery_app.tasks
