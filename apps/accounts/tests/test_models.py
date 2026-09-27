import pytest
from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction

from apps.accounts.models import Profile, User

from .factories import DEFAULT_PASSWORD, OrganizerFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_create_user_normalizes_email_and_defaults():
    user = User.objects.create_user("Jane.Doe@Example.COM", password="s3cret-pass")

    assert user.email == "jane.doe@example.com"
    assert user.check_password("s3cret-pass")
    assert user.role == User.Role.ATTENDEE
    assert not user.is_staff
    assert not user.is_superuser
    assert str(user) == "jane.doe@example.com"


def test_create_user_requires_email():
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user("", password="x")


def test_create_superuser_sets_flags():
    admin = User.objects.create_superuser("admin@example.com", password="x")

    assert admin.is_staff
    assert admin.is_superuser


@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_create_superuser_rejects_false_flags(flag):
    with pytest.raises(ValueError, match=flag):
        User.objects.create_superuser("admin@example.com", password="x", **{flag: False})


def test_email_is_unique_regardless_of_case():
    User.objects.create_user("dup@example.com", password="x")

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("DUP@example.com", password="x")


def test_authenticate_is_case_insensitive_on_email():
    user = UserFactory(email="login@example.com")

    assert authenticate(email="LOGIN@Example.com", password=DEFAULT_PASSWORD) == user


def test_invalid_role_is_rejected_by_database():
    user = UserFactory()

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=user.pk).update(role="superhero")


def test_is_organizer():
    assert OrganizerFactory().is_organizer
    assert not UserFactory().is_organizer


def test_profile_is_created_once_on_signup():
    user = UserFactory()
    user.first_name = "Updated"
    user.save()

    assert Profile.objects.filter(user=user).count() == 1
    assert str(user.profile) == f"Profile of {user.email}"
