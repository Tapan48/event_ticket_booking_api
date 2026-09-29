from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.orders.models import Order
from apps.orders.services import mark_order_paid, place_order

pytestmark = pytest.mark.django_db

ORDERS = reverse("order-list")
TICKETS = reverse("ticket-list")


def detail(order, action=None):
    return reverse(f"order-{action}" if action else "order-detail", args=[order.pk])


def order_payload(ticket_type, quantity=1):
    return {
        "event": ticket_type.event_id,
        "items": [{"ticket_type": ticket_type.pk, "quantity": quantity}],
    }


@pytest.fixture
def ticket_type(db):
    return TicketTypeFactory(price=Decimal("499.00"), quantity_total=5)


class TestPlaceOrder:
    def test_requires_login(self, api_client, ticket_type):
        assert api_client.post(ORDERS, order_payload(ticket_type)).status_code == 401

    def test_creates_pending_order_without_codes(self, client_for, attendee, ticket_type):
        response = client_for(attendee).post(ORDERS, order_payload(ticket_type, 2))

        assert response.status_code == 201
        data = response.data
        assert data["status"] == "pending"
        assert data["total_amount"] == "998.00"
        assert data["event"]["id"] == ticket_type.event_id
        assert [t["code"] for t in data["tickets"]] == [None, None]
        ticket_type.refresh_from_db()
        assert ticket_type.quantity_available == 3

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"event": 1, "items": []},
            {"event": 1, "items": [{"ticket_type": 1, "quantity": 0}]},
            {"event": 1, "items": [{"ticket_type": 1, "quantity": 101}]},
        ],
    )
    def test_rejects_malformed_payloads(self, client_for, attendee, payload):
        assert client_for(attendee).post(ORDERS, payload).status_code == 400

    def test_past_event_is_400(self, client_for, attendee):
        started = TicketTypeFactory(
            event=EventFactory(
                starts_at=timezone.now() - timedelta(hours=1),
                ends_at=timezone.now() + timedelta(hours=1),
            )
        )

        response = client_for(attendee).post(ORDERS, order_payload(started))

        assert response.status_code == 400
        assert "already started" in str(response.data["event"])

    def test_sold_out_is_409(self, client_for, attendee, ticket_type):
        response = client_for(attendee).post(ORDERS, order_payload(ticket_type, 6))

        assert response.status_code == 409
        assert "Only 5" in response.data["detail"]

    def test_per_user_limit_is_400(self, client_for, attendee):
        limited = TicketTypeFactory(event=EventFactory(max_tickets_per_user=1))

        response = client_for(attendee).post(ORDERS, order_payload(limited, 2))

        assert response.status_code == 400
        assert "at most 1" in str(response.data["items"])


class TestOrderVisibility:
    def test_lists_only_your_orders(self, client_for, attendee, organizer, ticket_type):
        mine = place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 1)])
        place_order(organizer, ticket_type.event_id, [(ticket_type.pk, 1)])

        response = client_for(attendee).get(ORDERS)

        assert [o["id"] for o in response.data["results"]] == [mine.pk]

    def test_other_users_order_is_404(self, client_for, attendee, organizer, ticket_type):
        theirs = place_order(organizer, ticket_type.event_id, [(ticket_type.pk, 1)])

        assert client_for(attendee).get(detail(theirs)).status_code == 404
        assert client_for(attendee).post(detail(theirs, "pay")).status_code == 404

    def test_staff_see_all_but_cannot_pay_for_others(
        self, client_for, staff, attendee, ticket_type
    ):
        order = place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 1)])
        client = client_for(staff)

        assert client.get(ORDERS).data["count"] == 1
        assert client.post(detail(order, "pay")).status_code == 403

    def test_filter_by_status(self, client_for, attendee, ticket_type):
        paid = mark_order_paid(place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 1)]))
        place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 1)])

        response = client_for(attendee).get(ORDERS, {"status": "paid"})

        assert [o["id"] for o in response.data["results"]] == [paid.pk]


class TestPayAndCancel:
    def test_pay_reveals_ticket_codes(self, client_for, attendee, ticket_type):
        order = place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 2)])

        response = client_for(attendee).post(detail(order, "pay"))

        assert response.status_code == 200
        assert response.data["status"] == "paid"
        assert response.data["paid_at"] is not None
        assert all(len(t["code"]) == 16 for t in response.data["tickets"])

    def test_paying_twice_is_409(self, client_for, attendee, ticket_type):
        order = mark_order_paid(place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 1)]))

        assert client_for(attendee).post(detail(order, "pay")).status_code == 409

    def test_paying_an_expired_order_is_409_and_releases_it(
        self, client_for, attendee, ticket_type
    ):
        order = place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 2)])
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(seconds=1))

        response = client_for(attendee).post(detail(order, "pay"))

        assert response.status_code == 409
        assert "expired" in response.data["detail"]
        ticket_type.refresh_from_db()
        assert ticket_type.quantity_available == 5

    def test_cancel_restores_stock(self, client_for, attendee, ticket_type):
        order = place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 3)])

        response = client_for(attendee).post(detail(order, "cancel"))

        assert response.status_code == 200
        assert response.data["status"] == "cancelled"
        ticket_type.refresh_from_db()
        assert ticket_type.quantity_available == 5

    def test_cannot_cancel_a_paid_order(self, client_for, attendee, ticket_type):
        order = mark_order_paid(place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 1)]))

        assert client_for(attendee).post(detail(order, "cancel")).status_code == 409


class TestMyTickets:
    def test_lists_only_your_paid_tickets(self, client_for, attendee, organizer, ticket_type):
        paid = mark_order_paid(place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 2)]))
        place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 1)])  # still pending
        mark_order_paid(place_order(organizer, ticket_type.event_id, [(ticket_type.pk, 1)]))

        response = client_for(attendee).get(TICKETS)

        assert response.data["count"] == 2
        assert {t["order"] for t in response.data["results"]} == {paid.pk}
        assert response.data["results"][0]["event"]["title"] == ticket_type.event.title

    def test_filter_by_event(self, client_for, attendee, ticket_type):
        other = TicketTypeFactory()
        mark_order_paid(place_order(attendee, ticket_type.event_id, [(ticket_type.pk, 1)]))
        mark_order_paid(place_order(attendee, other.event_id, [(other.pk, 1)]))

        response = client_for(attendee).get(TICKETS, {"event": other.event_id})

        assert [t["ticket_type"]["id"] for t in response.data["results"]] == [other.pk]

    def test_requires_login(self, api_client):
        assert api_client.get(TICKETS).status_code == 401


def test_order_list_query_count_does_not_grow_with_rows(client_for, attendee):
    client = client_for(attendee)

    def book(n):
        for _ in range(n):
            tier = TicketTypeFactory()
            place_order(attendee, tier.event_id, [(tier.pk, 2)])

    def count():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(ORDERS).status_code == 200
        return len(ctx)

    book(2)
    baseline = count()
    book(5)

    assert count() == baseline
