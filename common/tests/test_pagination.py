import pytest
from django.urls import reverse

from apps.events.tests.factories import VenueFactory

pytestmark = pytest.mark.django_db

VENUES = reverse("venue-list")


def test_lists_are_paginated_20_per_page(api_client):
    VenueFactory.create_batch(25)

    first = api_client.get(VENUES).data
    second = api_client.get(VENUES, {"page": 2}).data

    assert first["count"] == 25
    assert len(first["results"]) == 20
    assert first["previous"] is None
    assert "page=2" in first["next"]
    assert len(second["results"]) == 5
    assert second["next"] is None
    # Deterministic ordering: pages never overlap.
    assert not {v["id"] for v in first["results"]} & {v["id"] for v in second["results"]}


def test_page_size_is_client_adjustable_but_capped(api_client):
    VenueFactory.create_batch(101)

    assert len(api_client.get(VENUES, {"page_size": 5}).data["results"]) == 5
    assert len(api_client.get(VENUES, {"page_size": 1000}).data["results"]) == 100


def test_out_of_range_page_is_404(api_client):
    VenueFactory()

    assert api_client.get(VENUES, {"page": 99}).status_code == 404


def test_unknown_ordering_field_is_ignored(api_client):
    first, second = VenueFactory(name="B"), VenueFactory(name="A")

    response = api_client.get(VENUES, {"ordering": "created_by__password"})

    assert response.status_code == 200
    assert [v["id"] for v in response.data["results"]] == [second.pk, first.pk]
