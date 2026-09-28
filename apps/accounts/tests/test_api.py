import pytest
from django.urls import reverse

from apps.accounts.models import User

from .factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

REGISTER = reverse("register")
LOGIN = reverse("login")
REFRESH = reverse("token-refresh")
LOGOUT = reverse("logout")
ME = reverse("me")


def login(api_client, email, password=DEFAULT_PASSWORD):
    return api_client.post(LOGIN, {"email": email, "password": password})


class TestRegister:
    def test_registers_attendee_by_default(self, api_client):
        response = api_client.post(
            REGISTER, {"email": "New@Example.com", "password": "correct-horse-42"}
        )

        assert response.status_code == 201
        assert response.data["email"] == "new@example.com"
        assert response.data["role"] == User.Role.ATTENDEE
        assert "password" not in response.data
        user = User.objects.get(email="new@example.com")
        assert user.check_password("correct-horse-42")
        assert user.profile is not None

    def test_can_register_as_organizer(self, api_client):
        response = api_client.post(
            REGISTER,
            {"email": "org@example.com", "password": "correct-horse-42", "role": "organizer"},
        )

        assert response.status_code == 201
        assert User.objects.get(email="org@example.com").is_organizer

    def test_cannot_make_yourself_staff(self, api_client):
        api_client.post(
            REGISTER,
            {"email": "sneaky@example.com", "password": "correct-horse-42", "is_staff": True},
        )

        assert not User.objects.get(email="sneaky@example.com").is_staff

    def test_rejects_duplicate_email_in_any_case(self, api_client):
        UserFactory(email="taken@example.com")

        response = api_client.post(
            REGISTER, {"email": "TAKEN@example.com", "password": "correct-horse-42"}
        )

        assert response.status_code == 400
        assert "email" in response.data

    @pytest.mark.parametrize("password", ["short1!", "12345678901", "password123"])
    def test_rejects_weak_passwords(self, api_client, password):
        response = api_client.post(REGISTER, {"email": "weak@example.com", "password": password})

        assert response.status_code == 400
        assert not User.objects.filter(email="weak@example.com").exists()

    def test_rejects_invalid_role(self, api_client):
        response = api_client.post(
            REGISTER, {"email": "x@example.com", "password": "correct-horse-42", "role": "admin"}
        )

        assert response.status_code == 400
        assert "role" in response.data


class TestTokens:
    def test_login_returns_token_pair_and_is_case_insensitive(self, api_client):
        UserFactory(email="jane@example.com")

        response = login(api_client, "JANE@example.com")

        assert response.status_code == 200
        assert {"access", "refresh"} <= response.data.keys()

    def test_login_rejects_wrong_password(self, api_client):
        user = UserFactory()

        assert login(api_client, user.email, "wrong-password").status_code == 401

    def test_access_token_authenticates_requests(self, api_client):
        user = UserFactory()
        access = login(api_client, user.email).data["access"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        assert api_client.get(ME).data["email"] == user.email

    def test_refresh_rotates_and_blacklists_the_old_token(self, api_client):
        user = UserFactory()
        refresh = login(api_client, user.email).data["refresh"]

        response = api_client.post(REFRESH, {"refresh": refresh})

        assert response.status_code == 200
        assert response.data["refresh"] != refresh
        assert api_client.post(REFRESH, {"refresh": refresh}).status_code == 401

    def test_logout_blacklists_refresh_token(self, api_client):
        user = UserFactory()
        refresh = login(api_client, user.email).data["refresh"]

        assert api_client.post(LOGOUT, {"refresh": refresh}).status_code == 200
        assert api_client.post(REFRESH, {"refresh": refresh}).status_code == 401


class TestMe:
    def test_requires_authentication(self, api_client):
        assert api_client.get(ME).status_code == 401

    def test_returns_user_with_profile(self, client_for, attendee):
        response = client_for(attendee).get(ME)

        assert response.status_code == 200
        assert response.data["email"] == attendee.email
        assert response.data["profile"] == {"phone": "", "bio": "", "city": ""}

    def test_patch_updates_names_and_profile(self, client_for, attendee):
        response = client_for(attendee).patch(
            ME, {"first_name": "Asha", "profile": {"city": "Pune"}}
        )

        assert response.status_code == 200
        attendee.refresh_from_db()
        assert attendee.first_name == "Asha"
        assert attendee.profile.city == "Pune"
        assert attendee.profile.bio == ""

    def test_cannot_change_email_role_or_staff(self, client_for, attendee):
        client_for(attendee).patch(
            ME, {"email": "new@example.com", "role": "organizer", "is_staff": True}
        )

        attendee.refresh_from_db()
        assert attendee.email != "new@example.com"
        assert not attendee.is_organizer
        assert not attendee.is_staff

    def test_put_is_not_allowed(self, client_for, attendee):
        assert client_for(attendee).put(ME, {"first_name": "X"}).status_code == 405
