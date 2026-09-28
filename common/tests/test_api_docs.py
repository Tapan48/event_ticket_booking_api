from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_schema_and_swagger_ui_are_public(client):
    assert client.get(reverse("schema")).status_code == 200
    assert client.get(reverse("swagger-ui")).status_code == 200


def test_schema_generates_without_warnings():
    # --fail-on-warn turns any drf-spectacular warning into a non-zero exit.
    call_command("spectacular", "--validate", "--fail-on-warn", stdout=StringIO())
