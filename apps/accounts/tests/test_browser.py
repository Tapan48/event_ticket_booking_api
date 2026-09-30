import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.events.tests.factories import EventFactory, VenueFactory

pytestmark = pytest.mark.django_db
SESSION = "/api/auth/session/"


def browser_login(client, user, **extra):
    token = client.get(SESSION).data["csrf_token"]
    return client.post(
        SESSION,
        {"email": user.email.upper(), "password": DEFAULT_PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
        **extra,
    )


def test_session_bootstrap_is_public_and_not_cached():
    response = APIClient().get(SESSION)
    assert response.data["authenticated"] is False
    assert response.data["csrf_token"]
    assert "no-store" in response["Cache-Control"]


def test_login_requires_csrf_even_for_anonymous_browser():
    user = UserFactory()
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(SESSION, {"email": user.email, "password": DEFAULT_PASSWORD})
    assert response.status_code == 403
    assert client.get("/api/auth/me/").status_code == 401


def test_session_persists_enforces_csrf_and_logs_out():
    client = APIClient(enforce_csrf_checks=True)
    user = UserFactory()
    response = browser_login(client, user)
    assert response.status_code == 200
    assert response.data["authenticated"] is True
    assert client.cookies["sessionid"]["httponly"]
    assert client.get("/api/auth/me/").data["id"] == user.pk
    assert client.patch("/api/auth/me/", {"first_name": "Changed"}).status_code == 403
    token = response.data["csrf_token"]
    assert (
        client.patch("/api/auth/me/", {"first_name": "Changed"}, HTTP_X_CSRFTOKEN=token).status_code
        == 200
    )
    assert client.delete(SESSION).status_code == 403
    assert client.delete(SESSION, HTTP_X_CSRFTOKEN=token).status_code == 200
    assert client.get("/api/auth/me/").status_code == 401


@pytest.mark.parametrize("inactive", [False, True])
def test_invalid_or_inactive_login(inactive):
    client = APIClient(enforce_csrf_checks=True)
    user = UserFactory(is_active=not inactive)
    if not inactive:
        user.set_password("different-password")
        user.save()
    assert browser_login(client, user).status_code == 401
    assert not client.get(SESSION).data["authenticated"]


def test_rejects_foreign_origin():
    client = APIClient(enforce_csrf_checks=True)
    assert (
        browser_login(client, UserFactory(), HTTP_ORIGIN="https://evil.example").status_code == 403
    )


@override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
def test_production_cookie_flags():
    client = APIClient(enforce_csrf_checks=True)
    response = browser_login(client, UserFactory())
    assert response.status_code == 200
    assert client.cookies["sessionid"]["secure"]
    assert client.cookies["sessionid"]["samesite"] == "Lax"
    assert client.cookies["csrftoken"]["secure"]


def test_login_validates_payload_and_anonymous_logout():
    client = APIClient(enforce_csrf_checks=True)
    token = client.get(SESSION).data["csrf_token"]
    assert client.post(SESSION, {}, HTTP_X_CSRFTOKEN=token).status_code == 400
    assert client.delete(SESSION, HTTP_X_CSRFTOKEN=token).status_code == 200


@pytest.mark.parametrize("kind", ["events", "venues"])
def test_mine_filter_is_scoped_before_pagination(kind, organizer, other_organizer, client_for):
    if kind == "events":
        own = EventFactory(organizer=organizer, status="draft")
        EventFactory(organizer=other_organizer)
        EventFactory(organizer=other_organizer, status="draft")
    else:
        own = VenueFactory(created_by=organizer)
        VenueFactory(created_by=other_organizer)
    client = client_for(organizer)
    response = client.get(f"/api/{kind}/?mine=true&page_size=1")
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == own.pk
    assert client.get(f"/api/{kind}/?mine=false").data["count"] == 2
    assert APIClient().get(f"/api/{kind}/?mine=true").status_code == 401
