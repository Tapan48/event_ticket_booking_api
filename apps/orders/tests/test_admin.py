import pytest
from django.urls import reverse

from .factories import TicketFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("model", ["order", "ticket"])
def test_changelist_and_add_pages_render(admin_client, model):
    TicketFactory()

    for view in ("changelist", "add"):
        url = reverse(f"admin:orders_{model}_{view}")
        assert admin_client.get(url).status_code == 200, url


def test_order_change_page_lists_tickets(admin_client):
    ticket = TicketFactory()

    response = admin_client.get(reverse("admin:orders_order_change", args=[ticket.order_id]))

    assert response.status_code == 200
    assert ticket.code.encode() in response.content


def test_ticket_search_by_code(admin_client):
    ticket, other = TicketFactory(), TicketFactory()

    response = admin_client.get(reverse("admin:orders_ticket_changelist"), {"q": ticket.code})

    assert ticket.code.encode() in response.content
    assert other.code.encode() not in response.content
