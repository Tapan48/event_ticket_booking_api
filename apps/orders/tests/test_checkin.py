import pytest
from django.urls import reverse
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.fields import DateTimeField

from apps.accounts.tests.factories import OrganizerFactory, StaffFactory, UserFactory
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.orders.services import check_in, mark_order_paid, place_order
from common.exceptions import Conflict

pytestmark = pytest.mark.django_db

CHECKIN = reverse("checkin")


@pytest.fixture
def paid_ticket(organizer):
    ticket_type = TicketTypeFactory(event=EventFactory(organizer=organizer))
    order = mark_order_paid(
        place_order(
            UserFactory(email="fan@example.com"), ticket_type.event_id, [(ticket_type.pk, 1)]
        )
    )
    return order.tickets.get()


class TestCheckInService:
    def test_admits_a_paid_ticket_once(self, organizer, paid_ticket):
        ticket = check_in(paid_ticket.code, organizer)

        assert ticket.checked_in_at is not None
        assert ticket.checked_in_by == organizer
        with pytest.raises(Conflict) as excinfo:
            check_in(paid_ticket.code, organizer)
        expected = DateTimeField().to_representation(ticket.checked_in_at)
        assert excinfo.value.detail["checked_in_at"] == expected

    def test_staff_can_check_in_any_event(self, paid_ticket):
        assert check_in(paid_ticket.code, StaffFactory()).is_checked_in

    def test_other_organizers_cannot(self, paid_ticket):
        with pytest.raises(PermissionDenied):
            check_in(paid_ticket.code, OrganizerFactory())

    def test_unknown_code(self, organizer):
        with pytest.raises(NotFound):
            check_in("no-such-code", organizer)

    def test_unpaid_ticket_is_rejected(self, organizer):
        ticket_type = TicketTypeFactory(event=EventFactory(organizer=organizer))
        pending = place_order(UserFactory(), ticket_type.event_id, [(ticket_type.pk, 1)])

        with pytest.raises(ValidationError, match="pending, not paid"):
            check_in(pending.tickets.get().code, organizer)


class TestCheckInEndpoint:
    def test_organizer_scans_their_event(self, client_for, organizer, paid_ticket):
        response = client_for(organizer).post(CHECKIN, {"code": paid_ticket.code})

        assert response.status_code == 200
        assert response.data["code"] == paid_ticket.code
        assert response.data["attendee"] == "fan@example.com"
        assert response.data["checked_in_at"] is not None

    def test_second_scan_is_409_with_first_scan_time(self, client_for, organizer, paid_ticket):
        client = client_for(organizer)
        first = client.post(CHECKIN, {"code": paid_ticket.code})

        second = client.post(CHECKIN, {"code": paid_ticket.code})

        assert second.status_code == 409
        assert "already been checked in" in second.data["detail"]
        assert second.data["checked_in_at"] == first.data["checked_in_at"]

    @pytest.mark.parametrize(
        ("who", "status"), [(None, 401), ("attendee", 403), ("other_organizer", 403)]
    )
    def test_who_may_scan(self, request, client_for, paid_ticket, who, status):
        user = request.getfixturevalue(who) if who else None

        assert client_for(user).post(CHECKIN, {"code": paid_ticket.code}).status_code == status

    def test_staff_may_scan(self, client_for, staff, paid_ticket):
        assert client_for(staff).post(CHECKIN, {"code": paid_ticket.code}).status_code == 200

    def test_unknown_code_is_404_and_bad_payload_400(self, client_for, organizer):
        client = client_for(organizer)

        assert client.post(CHECKIN, {"code": "nope"}).status_code == 404
        assert client.post(CHECKIN, {}).status_code == 400
