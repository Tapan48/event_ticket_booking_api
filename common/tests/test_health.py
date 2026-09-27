from unittest import mock

import pytest
from django.db import OperationalError
from django.urls import reverse


@pytest.mark.django_db
def test_health_ok(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_database_down(client):
    with mock.patch(
        "common.views.connection.ensure_connection", side_effect=OperationalError("down")
    ):
        response = client.get(reverse("health"))

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}


def test_health_rejects_post(client):
    assert client.post(reverse("health")).status_code == 405
