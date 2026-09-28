"""Project-wide API test fixtures."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import OrganizerFactory, StaffFactory, UserFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def client_for():
    """client_for(user) -> an APIClient authenticated as that user (None = anonymous)."""

    def make(user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return make


@pytest.fixture
def attendee(db):
    return UserFactory()


@pytest.fixture
def organizer(db):
    return OrganizerFactory()


@pytest.fixture
def other_organizer(db):
    return OrganizerFactory()


@pytest.fixture
def staff(db):
    return StaffFactory()
