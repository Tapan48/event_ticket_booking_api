from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event, TicketType, Venue
from apps.orders.tests.factories import TicketFactory

from .factories import CategoryFactory, EventFactory, TicketTypeFactory, VenueFactory

pytestmark = pytest.mark.django_db


def url(name, *args):
    return reverse(name, args=args)


def event_payload(venue, **overrides):
    starts_at = timezone.now() + timedelta(days=10)
    return {
        "title": "Launch Party",
        "venue_id": venue.pk,
        "starts_at": starts_at.isoformat(),
        "ends_at": (starts_at + timedelta(hours=3)).isoformat(),
        **overrides,
    }


class TestVenues:
    def test_anyone_can_list(self, api_client):
        VenueFactory()

        response = api_client.get(url("venue-list"))

        assert response.status_code == 200
        assert response.data["count"] == 1

    @pytest.mark.parametrize(("who", "status"), [(None, 401), ("attendee", 403)])
    def test_only_organizers_can_create(self, request, client_for, who, status):
        user = request.getfixturevalue(who) if who else None
        payload = {"name": "Hall", "address": "1 Road", "city": "Pune", "capacity": 100}

        assert client_for(user).post(url("venue-list"), payload).status_code == status

    def test_organizer_creates_venue_as_owner(self, client_for, organizer):
        response = client_for(organizer).post(
            url("venue-list"), {"name": "Hall", "address": "1 Road", "city": "Pune", "capacity": 99}
        )

        assert response.status_code == 201
        assert Venue.objects.get(pk=response.data["id"]).created_by == organizer

    def test_capacity_must_be_positive(self, client_for, organizer):
        response = client_for(organizer).post(
            url("venue-list"), {"name": "Hall", "address": "1 Road", "city": "Pune", "capacity": 0}
        )

        assert response.status_code == 400
        assert "capacity" in response.data

    @pytest.mark.parametrize(("who", "status"), [("other_organizer", 403), ("staff", 200)])
    def test_only_owner_or_staff_can_edit(self, request, client_for, organizer, who, status):
        venue = VenueFactory(created_by=organizer)
        user = request.getfixturevalue(who)

        response = client_for(user).patch(url("venue-detail", venue.pk), {"city": "Goa"})

        assert response.status_code == status
        assert client_for(organizer).patch(url("venue-detail", venue.pk), {}).status_code == 200

    def test_deleting_venue_with_events_is_a_conflict(self, client_for, organizer):
        event = EventFactory(venue=VenueFactory(created_by=organizer))

        response = client_for(organizer).delete(url("venue-detail", event.venue_id))

        assert response.status_code == 409
        assert Venue.objects.filter(pk=event.venue_id).exists()


class TestCategories:
    def test_public_read_by_slug(self, api_client):
        CategoryFactory(name="Music", slug="music")

        response = api_client.get(url("category-detail", "music"))

        assert response.status_code == 200
        assert response.data["name"] == "Music"

    @pytest.mark.parametrize(("who", "status"), [("organizer", 403), ("staff", 201)])
    def test_only_staff_can_create(self, request, client_for, who, status):
        user = request.getfixturevalue(who)

        response = client_for(user).post(url("category-list"), {"name": "Jazz", "slug": "jazz"})

        assert response.status_code == status


class TestEventVisibility:
    def test_public_sees_only_published(self, api_client):
        published = EventFactory()
        EventFactory(status=Event.Status.DRAFT)
        EventFactory(status=Event.Status.CANCELLED)

        response = api_client.get(url("event-list"))

        assert [e["id"] for e in response.data["results"]] == [published.pk]

    def test_organizer_also_sees_own_drafts_only(self, client_for, organizer):
        mine = EventFactory(organizer=organizer, status=Event.Status.DRAFT)
        theirs = EventFactory(status=Event.Status.DRAFT)
        client = client_for(organizer)

        ids = {e["id"] for e in client.get(url("event-list")).data["results"]}

        assert mine.pk in ids
        assert theirs.pk not in ids
        assert client.get(url("event-detail", theirs.pk)).status_code == 404

    def test_staff_sees_everything(self, client_for, staff):
        EventFactory(status=Event.Status.DRAFT)
        EventFactory()

        assert client_for(staff).get(url("event-list")).data["count"] == 2

    def test_detail_nests_venue_categories_and_ticket_types(self, api_client):
        ticket_type = TicketTypeFactory(name="VIP")
        event = ticket_type.event
        event.categories.add(CategoryFactory(slug="music"))

        data = api_client.get(url("event-detail", event.pk)).data

        assert data["venue"] == {
            "id": event.venue_id,
            "name": event.venue.name,
            "city": event.venue.city,
        }
        assert data["categories"] == ["music"]
        assert data["ticket_types"][0]["name"] == "VIP"
        assert data["organizer"] == event.organizer_id


class TestEventWrites:
    @pytest.mark.parametrize(("who", "status"), [(None, 401), ("attendee", 403)])
    def test_only_organizers_can_create(self, request, client_for, who, status):
        user = request.getfixturevalue(who) if who else None

        response = client_for(user).post(url("event-list"), event_payload(VenueFactory()))

        assert response.status_code == status

    def test_organizer_is_always_the_requester(self, client_for, organizer, other_organizer):
        CategoryFactory(slug="tech")
        payload = event_payload(VenueFactory(), organizer=other_organizer.pk, categories=["tech"])

        response = client_for(organizer).post(url("event-list"), payload)

        assert response.status_code == 201
        event = Event.objects.get(pk=response.data["id"])
        assert event.organizer == organizer
        assert event.status == Event.Status.DRAFT
        assert list(event.categories.values_list("slug", flat=True)) == ["tech"]

    @pytest.mark.parametrize(("who", "status"), [("other_organizer", 403), ("staff", 200)])
    def test_only_owner_or_staff_can_edit(self, request, client_for, organizer, who, status):
        event = EventFactory(organizer=organizer)
        user = request.getfixturevalue(who)

        response = client_for(user).patch(url("event-detail", event.pk), {"title": "Renamed"})

        assert response.status_code == status

    def test_owner_can_publish(self, client_for, organizer):
        event = EventFactory(organizer=organizer, status=Event.Status.DRAFT)

        response = client_for(organizer).patch(
            url("event-detail", event.pk), {"status": "published"}
        )

        assert response.status_code == 200
        event.refresh_from_db()
        assert event.status == Event.Status.PUBLISHED

    def test_anonymous_cannot_edit(self, api_client):
        event = EventFactory()

        assert api_client.patch(url("event-detail", event.pk), {"title": "x"}).status_code == 401

    def test_deleting_event_with_sold_tickets_is_a_conflict(self, client_for, organizer):
        ticket = TicketFactory(
            ticket_type=TicketTypeFactory(event=EventFactory(organizer=organizer))
        )

        response = client_for(organizer).delete(url("event-detail", ticket.ticket_type.event_id))

        assert response.status_code == 409

    def test_owner_can_delete_unsold_event(self, client_for, organizer):
        event = EventFactory(organizer=organizer)

        assert client_for(organizer).delete(url("event-detail", event.pk)).status_code == 204


class TestEventValidation:
    def test_must_end_after_start(self, client_for, organizer):
        starts_at = timezone.now() + timedelta(days=5)
        payload = event_payload(
            VenueFactory(), starts_at=starts_at.isoformat(), ends_at=starts_at.isoformat()
        )

        response = client_for(organizer).post(url("event-list"), payload)

        assert response.status_code == 400
        assert "ends_at" in response.data

    def test_partial_update_is_checked_against_stored_dates(self, client_for, organizer):
        event = EventFactory(organizer=organizer)

        response = client_for(organizer).patch(
            url("event-detail", event.pk), {"ends_at": event.starts_at.isoformat()}
        )

        assert response.status_code == 400

    def test_new_events_cannot_start_in_the_past(self, client_for, organizer):
        starts_at = timezone.now() - timedelta(days=1)
        payload = event_payload(
            VenueFactory(),
            starts_at=starts_at.isoformat(),
            ends_at=(starts_at + timedelta(hours=2)).isoformat(),
        )

        response = client_for(organizer).post(url("event-list"), payload)

        assert response.status_code == 400
        assert "starts_at" in response.data

    def test_max_tickets_per_user_must_be_positive(self, client_for, organizer):
        payload = event_payload(VenueFactory(), max_tickets_per_user=0)

        response = client_for(organizer).post(url("event-list"), payload)

        assert response.status_code == 400
        assert "max_tickets_per_user" in response.data


class TestTicketTypes:
    def payload(self, event, **overrides):
        return {
            "event": event.pk,
            "name": "General",
            "price": "25.00",
            "quantity_total": 50,
            **overrides,
        }

    def test_owner_creates_with_full_stock(self, client_for, organizer):
        event = EventFactory(organizer=organizer)

        response = client_for(organizer).post(url("ticket-type-list"), self.payload(event))

        assert response.status_code == 201
        assert response.data["quantity_available"] == 50

    @pytest.mark.parametrize(("who", "status"), [("attendee", 403), ("other_organizer", 403)])
    def test_only_event_owner_can_create(self, request, client_for, organizer, who, status):
        event = EventFactory(organizer=organizer)
        user = request.getfixturevalue(who)

        response = client_for(user).post(url("ticket-type-list"), self.payload(event))

        assert response.status_code == status
        assert not TicketType.objects.exists()

    def test_other_organizer_cannot_edit(self, client_for, other_organizer):
        ticket_type = TicketTypeFactory()

        response = client_for(other_organizer).patch(
            url("ticket-type-detail", ticket_type.pk), {"price": "1.00"}
        )

        assert response.status_code == 403

    def test_rejects_negative_price_and_duplicate_name(self, client_for, organizer):
        event = EventFactory(organizer=organizer)
        TicketTypeFactory(event=event, name="General")
        client = client_for(organizer)

        negative = client.post(url("ticket-type-list"), self.payload(event, price="-1"))
        duplicate = client.post(url("ticket-type-list"), self.payload(event))

        assert negative.status_code == 400
        assert "price" in negative.data
        assert duplicate.status_code == 400

    def test_quantity_available_is_read_only(self, client_for, organizer):
        ticket_type = TicketTypeFactory(event=EventFactory(organizer=organizer))

        client_for(organizer).patch(
            url("ticket-type-detail", ticket_type.pk), {"quantity_available": 0}
        )

        ticket_type.refresh_from_db()
        assert ticket_type.quantity_available == 100

    def test_changing_total_keeps_sold_count(self, client_for, organizer):
        ticket_type = TicketTypeFactory(
            event=EventFactory(organizer=organizer), quantity_total=100, quantity_available=70
        )

        response = client_for(organizer).patch(
            url("ticket-type-detail", ticket_type.pk), {"quantity_total": 50}
        )

        assert response.status_code == 200
        assert response.data["quantity_available"] == 20  # 30 sold stay sold

    def test_total_cannot_drop_below_sold(self, client_for, organizer):
        ticket_type = TicketTypeFactory(
            event=EventFactory(organizer=organizer), quantity_total=100, quantity_available=70
        )

        response = client_for(organizer).patch(
            url("ticket-type-detail", ticket_type.pk), {"quantity_total": 29}
        )

        assert response.status_code == 400
        assert "quantity_total" in response.data

    def test_cannot_move_to_another_event(self, client_for, organizer):
        ticket_type = TicketTypeFactory(event=EventFactory(organizer=organizer))
        other_event = EventFactory(organizer=organizer)

        response = client_for(organizer).patch(
            url("ticket-type-detail", ticket_type.pk), {"event": other_event.pk}
        )

        assert response.status_code == 400
        assert "event" in response.data

    def test_hidden_with_their_draft_event(self, api_client):
        TicketTypeFactory(event=EventFactory(status=Event.Status.DRAFT))
        visible = TicketTypeFactory()

        response = api_client.get(url("ticket-type-list"))

        assert [t["id"] for t in response.data["results"]] == [visible.pk]


def test_event_list_query_count_does_not_grow_with_rows(api_client):
    """select_related/prefetch_related keep the list at a fixed number of queries."""

    def count():
        with CaptureQueriesContext(connection) as ctx:
            assert api_client.get(url("event-list")).status_code == 200
        return len(ctx)

    def add_events(n):
        for _ in range(n):
            event = TicketTypeFactory().event
            TicketTypeFactory(event=event)
            event.categories.add(CategoryFactory())

    add_events(2)
    baseline = count()
    add_events(5)

    assert count() == baseline
