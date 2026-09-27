import pytest
from django.urls import reverse

from apps.accounts.models import User

from .factories import UserFactory

pytestmark = pytest.mark.django_db


def test_user_admin_pages_render(admin_client):
    user = UserFactory()

    for url in (
        reverse("admin:accounts_user_changelist"),
        reverse("admin:accounts_user_add"),
        reverse("admin:accounts_user_change", args=[user.pk]),
    ):
        assert admin_client.get(url).status_code == 200, url


def test_user_admin_add_creates_user_with_profile(admin_client):
    response = admin_client.post(
        reverse("admin:accounts_user_add"),
        {
            "email": "New.Organizer@Example.com",
            "role": User.Role.ORGANIZER,
            "usable_password": "true",
            "password1": "a-strong-pass-123",
            "password2": "a-strong-pass-123",
        },
    )

    assert response.status_code == 302, response.context["adminform"].form.errors
    user = User.objects.get(email="new.organizer@example.com")
    assert user.is_organizer
    assert user.profile is not None
