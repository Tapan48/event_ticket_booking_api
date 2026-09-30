from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Category, Event, TicketType, Venue

pytestmark = pytest.mark.django_db


def seed(**options):
    out = StringIO()
    call_command("seed_demo", stdout=out, **options)
    return out.getvalue()


def counts():
    return [m.objects.count() for m in (User, Venue, Category, Event, TicketType)]


def test_seed_demo_creates_a_usable_dataset():
    output = seed()

    assert "Demo data ready" in output
    assert counts() == [4, 4, 5, 8, 11]
    assert authenticate(email="organizer@demo.dev", password="demo-pass-123").is_organizer
    assert authenticate(email="staff@demo.dev", password="demo-pass-123").is_staff

    published = Event.objects.filter(status=Event.Status.PUBLISHED)
    assert published.filter(starts_at__gt=timezone.now()).count() == 5
    assert published.filter(starts_at__lt=timezone.now()).count() == 1
    assert Event.objects.filter(status=Event.Status.DRAFT).exists()
    assert all(tt.quantity_available == tt.quantity_total for tt in TicketType.objects.all())
    assert Event.objects.get(title="Street Food Festival").categories.count() == 2


def test_seed_demo_is_idempotent():
    seed()
    before = counts()

    seed(password="a-different-one")

    assert counts() == before
    # Existing users keep their original password.
    assert authenticate(email="attendee@demo.dev", password="demo-pass-123") is not None


def test_public_seed_has_no_privileged_accounts_or_password_output(settings):
    settings.PUBLIC_DEMO_ONLY = True
    output = seed(public=True)
    assert counts() == [3, 4, 5, 8, 11]
    assert not User.objects.filter(is_staff=True).exists()
    assert not User.objects.filter(is_superuser=True).exists()
    assert "demo-pass-123" not in output
    assert "staff@demo.dev" not in output
    assert authenticate(email="organizer@demo.dev", password="demo-pass-123").is_organizer


def test_production_seed_requires_public_flag(settings):
    settings.PUBLIC_DEMO_ONLY = True
    with pytest.raises(CommandError, match="requires --public"):
        seed()
    assert not User.objects.exists()


@pytest.mark.parametrize("privilege", ["is_staff", "is_superuser"])
def test_public_seed_refuses_existing_privileged_demo(privilege):
    User.objects.create_user("organizer@demo.dev", password="private", **{privilege: True})
    with pytest.raises(CommandError, match="privileged demo account"):
        seed(public=True)
    assert not Event.objects.exists()
