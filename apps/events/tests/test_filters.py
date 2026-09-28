from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event

from .factories import CategoryFactory, EventFactory, TicketTypeFactory, VenueFactory

pytestmark = pytest.mark.django_db

EVENTS = reverse("event-list")


def ids(response):
    assert response.status_code == 200, response.data
    return [event["id"] for event in response.data["results"]]


def at(day, hour=18):
    return timezone.make_aware(datetime(2030, 3, day, hour))


def event_with_prices(*prices, **kwargs):
    event = EventFactory(**kwargs)
    for price in prices:
        TicketTypeFactory(event=event, price=Decimal(price))
    return event


class TestEventFilters:
    def test_city_is_case_insensitive(self, api_client):
        pune = EventFactory(venue=VenueFactory(city="Pune"))
        EventFactory(venue=VenueFactory(city="Mumbai"))

        assert ids(api_client.get(EVENTS, {"city": "pUNE"})) == [pune.pk]

    def test_category_slug(self, api_client):
        music = CategoryFactory(slug="music")
        jazz_night = EventFactory()
        jazz_night.categories.add(music, CategoryFactory(slug="food"))
        EventFactory().categories.add(CategoryFactory(slug="tech"))

        assert ids(api_client.get(EVENTS, {"category": "music"})) == [jazz_night.pk]

    def test_date_range_accepts_plain_dates(self, api_client):
        early = EventFactory(starts_at=at(1), ends_at=at(1, 22))
        middle = EventFactory(starts_at=at(10), ends_at=at(10, 22))
        EventFactory(starts_at=at(20), ends_at=at(20, 22))

        response = api_client.get(
            EVENTS, {"starts_after": "2030-03-01", "starts_before": "2030-03-20"}
        )

        assert ids(response) == [early.pk, middle.pk]

    def test_upcoming(self, api_client):
        future = EventFactory()
        past = EventFactory(
            starts_at=timezone.now() - timedelta(days=2),
            ends_at=timezone.now() - timedelta(days=1),
        )

        assert ids(api_client.get(EVENTS, {"upcoming": "true"})) == [future.pk]
        assert ids(api_client.get(EVENTS, {"upcoming": "false"})) == [past.pk]

    def test_price_bounds_must_match_the_same_ticket_type(self, api_client):
        """A 50 + 500 event has no tier in 100-200, even though 500 >= 100 and 50 <= 200."""
        event_with_prices("50", "500")
        mid_priced = event_with_prices("150")

        response = api_client.get(EVENTS, {"min_price": "100", "max_price": "200"})

        assert ids(response) == [mid_priced.pk]

    def test_single_price_bounds(self, api_client):
        cheap = event_with_prices("20")
        pricey = event_with_prices("900")
        event_with_prices()  # no ticket types yet: never matches a price filter

        assert ids(api_client.get(EVENTS, {"max_price": "100"})) == [cheap.pk]
        assert ids(api_client.get(EVENTS, {"min_price": "100"})) == [pricey.pk]

    def test_price_filter_does_not_duplicate_events(self, api_client):
        event = event_with_prices("10", "20", "30")

        assert ids(api_client.get(EVENTS, {"max_price": "100"})) == [event.pk]

    def test_invalid_filter_value_is_400(self, api_client):
        response = api_client.get(EVENTS, {"min_price": "cheap"})

        assert response.status_code == 400
        assert "min_price" in response.data

    def test_status_lets_organizers_list_their_drafts(self, client_for, organizer):
        draft = EventFactory(organizer=organizer, status=Event.Status.DRAFT)
        EventFactory(organizer=organizer)

        response = client_for(organizer).get(EVENTS, {"status": "draft"})

        assert ids(response) == [draft.pk]

    def test_filters_combine(self, api_client):
        music = CategoryFactory(slug="music")
        match = event_with_prices("300", venue=VenueFactory(city="Pune"))
        match.categories.add(music)
        wrong_city = event_with_prices("300", venue=VenueFactory(city="Goa"))
        wrong_city.categories.add(music)
        too_pricey = event_with_prices("3000", venue=VenueFactory(city="Pune"))
        too_pricey.categories.add(music)

        response = api_client.get(EVENTS, {"city": "pune", "category": "music", "max_price": "500"})

        assert ids(response) == [match.pk]


class TestEventSearch:
    def test_searches_title_description_and_venue(self, api_client):
        by_title = EventFactory(title="Sunburn Arena Tour")
        by_description = EventFactory(description="An evening of SUNBURN classics")
        by_venue = EventFactory(venue=VenueFactory(name="Sunburn Grounds"))
        EventFactory(title="Chess Open")

        found = set(ids(api_client.get(EVENTS, {"search": "sunburn"})))

        assert found == {by_title.pk, by_description.pk, by_venue.pk}


class TestEventOrdering:
    def test_defaults_to_soonest_first(self, api_client):
        later = EventFactory(starts_at=at(20), ends_at=at(20, 22))
        sooner = EventFactory(starts_at=at(5), ends_at=at(5, 22))

        assert ids(api_client.get(EVENTS)) == [sooner.pk, later.pk]

    def test_order_by_cheapest_ticket(self, api_client):
        mid = event_with_prices("500", "80")  # cheapest tier is 80
        low = event_with_prices("40")
        high = event_with_prices("900")

        assert ids(api_client.get(EVENTS, {"ordering": "min_price"})) == [low.pk, mid.pk, high.pk]
        assert ids(api_client.get(EVENTS, {"ordering": "-min_price"})) == [
            high.pk,
            mid.pk,
            low.pk,
        ]

    def test_min_price_field(self, api_client):
        event_with_prices("500", "79.5")

        event = api_client.get(EVENTS).data["results"][0]

        assert event["min_price"] == "79.50"

    def test_min_price_is_null_without_ticket_types(self, client_for, organizer):
        response = client_for(organizer).post(
            EVENTS,
            {
                "title": "No tiers yet",
                "venue_id": VenueFactory().pk,
                "starts_at": at(1).isoformat(),
                "ends_at": at(2).isoformat(),
            },
        )

        assert response.status_code == 201
        assert response.data["min_price"] is None


class TestOtherLists:
    def test_venues_filter_by_city_and_search(self, api_client):
        pune = VenueFactory(name="Phoenix Hall", city="Pune")
        mumbai = VenueFactory(name="NESCO Centre", city="Mumbai")
        venues = reverse("venue-list")

        assert ids(api_client.get(venues, {"city": "PUNE"})) == [pune.pk]
        assert ids(api_client.get(venues, {"search": "phoenix"})) == [pune.pk]
        assert ids(api_client.get(venues, {"search": "mumbai"})) == [mumbai.pk]

    def test_categories_search_by_name(self, api_client):
        CategoryFactory(name="Stand-up Comedy", slug="comedy")
        CategoryFactory(name="Music", slug="music")

        response = api_client.get(reverse("category-list"), {"search": "comedy"})

        assert [c["slug"] for c in response.data["results"]] == ["comedy"]

    def test_ticket_types_filter_by_event_and_order_by_price(self, api_client):
        event = EventFactory()
        vip = TicketTypeFactory(event=event, price=Decimal("900"))
        general = TicketTypeFactory(event=event, price=Decimal("100"))
        TicketTypeFactory()  # another event's tier
        ticket_types = reverse("ticket-type-list")

        assert ids(api_client.get(ticket_types, {"event": event.pk})) == [general.pk, vip.pk]
        assert ids(api_client.get(ticket_types, {"event": event.pk, "ordering": "-price"})) == [
            vip.pk,
            general.pk,
        ]
