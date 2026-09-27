from decimal import Decimal

import pytest
from django.db.models import ProtectedError
from django.utils import timezone

from apps.orders.models import Order, Ticket
from common.tests.helpers import assert_violates

from .factories import OrderFactory, TicketFactory

pytestmark = pytest.mark.django_db


class TestOrder:
    def test_defaults(self):
        order = OrderFactory()

        assert order.status == Order.Status.PENDING
        assert order.total_amount == 0
        assert order.paid_at is None
        assert str(order) == f"Order #{order.pk} (pending)"

    def test_paid_order_requires_paid_at(self):
        assert_violates(
            "order_paid_requires_paid_at", lambda: OrderFactory(status=Order.Status.PAID)
        )

        order = OrderFactory(status=Order.Status.PAID, paid_at=timezone.now())
        assert order.status == Order.Status.PAID

    def test_status_must_be_valid(self):
        assert_violates("order_status_valid", lambda: OrderFactory(status="refunded"))

    def test_total_cannot_be_negative(self):
        assert_violates(
            "order_total_non_negative", lambda: OrderFactory(total_amount=Decimal("-0.01"))
        )

    def test_deleting_order_deletes_its_tickets(self):
        ticket = TicketFactory()

        ticket.order.delete()

        assert not Ticket.objects.exists()

    def test_user_with_orders_is_protected(self):
        order = OrderFactory()

        with pytest.raises(ProtectedError):
            order.user.delete()


class TestTicket:
    def test_code_is_generated_unique_and_url_safe(self):
        first, second = TicketFactory(), TicketFactory()

        assert len(first.code) == 16
        assert first.code != second.code
        assert all(c.isalnum() or c in "-_" for c in first.code)
        assert str(first) == first.code

    def test_code_must_be_unique(self):
        existing = TicketFactory()

        assert_violates("unique_ticket_code", lambda: TicketFactory(code=existing.code))

    def test_price_paid_cannot_be_negative(self):
        assert_violates(
            "ticket_price_paid_non_negative", lambda: TicketFactory(price_paid=Decimal("-5"))
        )

    def test_check_in_needs_a_timestamp(self):
        ticket = TicketFactory()
        staff = ticket.order.user

        assert not ticket.is_checked_in
        assert_violates(
            "ticket_checked_in_by_requires_time",
            lambda: Ticket.objects.filter(pk=ticket.pk).update(checked_in_by=staff),
        )

        Ticket.objects.filter(pk=ticket.pk).update(
            checked_in_by=staff, checked_in_at=timezone.now()
        )
        ticket.refresh_from_db()
        assert ticket.is_checked_in

    def test_sold_ticket_type_and_event_are_protected(self):
        ticket = TicketFactory()

        with pytest.raises(ProtectedError):
            ticket.ticket_type.delete()
        with pytest.raises(ProtectedError):
            ticket.ticket_type.event.delete()
