import pytest
from django.urls import reverse

from .factories import CategoryFactory, TicketTypeFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("model", ["venue", "category", "event", "tickettype"])
def test_changelist_and_add_pages_render(admin_client, model):
    TicketTypeFactory()  # creates a venue, event and organizer too
    CategoryFactory()

    for view in ("changelist", "add"):
        url = reverse(f"admin:events_{model}_{view}")
        assert admin_client.get(url).status_code == 200, url


def test_event_change_page_shows_ticket_type_inline(admin_client):
    ticket_type = TicketTypeFactory(name="Early Bird")

    response = admin_client.get(reverse("admin:events_event_change", args=[ticket_type.event_id]))

    assert response.status_code == 200
    assert b"Early Bird" in response.content
