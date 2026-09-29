from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.accounts.tests.factories import OrganizerFactory, StaffFactory, UserFactory
from common.permissions import (
    CanCheckIn,
    IsOrganizerOrReadOnly,
    IsOwnerOrReadOnly,
    IsStaffOrReadOnly,
)

pytestmark = pytest.mark.django_db

ANON = "anon"


def make_user(kind):
    return {
        ANON: AnonymousUser,
        "attendee": UserFactory.build,
        "organizer": OrganizerFactory.build,
        "staff": StaffFactory.build,
    }[kind]()


def request(method, user):
    return SimpleNamespace(method=method, user=user)


@pytest.mark.parametrize(
    ("permission", "kind", "allowed"),
    [
        (IsOrganizerOrReadOnly, ANON, False),
        (IsOrganizerOrReadOnly, "attendee", False),
        (IsOrganizerOrReadOnly, "organizer", True),
        (IsOrganizerOrReadOnly, "staff", True),
        (IsStaffOrReadOnly, ANON, False),
        (IsStaffOrReadOnly, "organizer", False),
        (IsStaffOrReadOnly, "staff", True),
    ],
)
def test_role_permissions(permission, kind, allowed):
    user = make_user(kind)

    assert permission().has_permission(request("GET", user), view=None)
    assert permission().has_permission(request("POST", user), view=None) is allowed


@pytest.mark.parametrize(
    ("kind", "allowed"), [(ANON, False), ("attendee", False), ("organizer", True), ("staff", True)]
)
def test_can_check_in(kind, allowed):
    user = make_user(kind)

    assert CanCheckIn().has_permission(request("POST", user), view=None) is allowed


class TestIsOwnerOrReadOnly:
    def setup_method(self):
        self.owner = SimpleNamespace(pk=1)
        # Mimics a ticket type whose owner is reached via event.organizer.
        self.obj = SimpleNamespace(event=SimpleNamespace(organizer_id=1))
        self.view = SimpleNamespace(owner_field="event.organizer")

    def check(self, method, user):
        return IsOwnerOrReadOnly().has_object_permission(request(method, user), self.view, self.obj)

    def test_anyone_can_read(self):
        assert self.check("GET", AnonymousUser())

    def test_owner_can_write_via_dotted_path(self):
        user = SimpleNamespace(pk=1, is_authenticated=True, is_staff=False)

        assert self.check("PATCH", user)

    def test_non_owner_cannot_write(self):
        user = SimpleNamespace(pk=2, is_authenticated=True, is_staff=False)

        assert not self.check("DELETE", user)

    def test_staff_can_write(self):
        user = SimpleNamespace(pk=99, is_authenticated=True, is_staff=True)

        assert self.check("PUT", user)

    def test_anonymous_cannot_write(self):
        assert not self.check("PATCH", AnonymousUser())
