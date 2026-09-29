from datetime import timedelta
from unittest import mock

import pytest
from celery.exceptions import Retry
from django.core import mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.events.tests.factories import EventFactory, TicketTypeFactory, VenueFactory
from apps.orders.models import Order
from apps.orders.services import mark_order_paid, place_order
from apps.orders.tasks import send_ticket_email
from common.exceptions import Conflict

pytestmark = pytest.mark.django_db


@pytest.fixture
def order():
    event = EventFactory(title="Indie Rock Night", venue=VenueFactory(name="Palace Grounds"))
    general = TicketTypeFactory(event=event, name="General")
    vip = TicketTypeFactory(event=event, name="VIP")
    buyer = UserFactory(email="fan@example.com", first_name="Asha")
    return place_order(buyer, event.pk, [(general.pk, 2), (vip.pk, 1)])


def test_paying_emails_the_tickets(order, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        mark_order_paid(order)

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == ["fan@example.com"]
    assert email.subject == "Your tickets for Indie Rock Night"
    assert "Hi Asha" in email.body
    assert "Palace Grounds" in email.body
    html, mimetype = email.alternatives[0]
    assert mimetype == "text/html"
    for ticket in order.tickets.all():
        assert ticket.code in email.body
        assert ticket.code in html


def test_pay_endpoint_sends_the_email(order, client_for, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(order.user).post(reverse("order-pay", args=[order.pk]))

    assert response.status_code == 200
    assert len(mail.outbox) == 1


def test_rolled_back_payment_sends_nothing(order, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks() as callbacks:
        with pytest.raises(RuntimeError), transaction.atomic():
            mark_order_paid(order)
            raise RuntimeError("payment provider blew up")

    assert callbacks == []
    order.refresh_from_db()
    assert order.status == Order.Status.PENDING


def test_expired_payment_attempt_sends_nothing(order, django_capture_on_commit_callbacks):
    Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(seconds=1))

    with django_capture_on_commit_callbacks(execute=True), pytest.raises(Conflict):
        mark_order_paid(order)

    assert mail.outbox == []


def test_task_ignores_orders_that_are_not_paid(order):
    send_ticket_email.delay(order.pk)
    send_ticket_email.delay(999_999)

    assert mail.outbox == []


def test_task_retries_smtp_failures_then_gives_up(order):
    Order.objects.filter(pk=order.pk).update(status=Order.Status.PAID, paid_at=timezone.now())

    with mock.patch(
        "apps.orders.tasks.send_tickets_email", side_effect=ConnectionRefusedError
    ) as send:
        # First failure: Celery schedules a retry instead of failing.
        with pytest.raises(Retry):
            send_ticket_email.apply(args=[order.pk], throw=True)
        # Last allowed attempt: the original error surfaces.
        with pytest.raises(ConnectionRefusedError):
            send_ticket_email.apply(args=[order.pk], retries=5, throw=True)

    assert send.call_count == 2
    assert send_ticket_email.max_retries == 5
