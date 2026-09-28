from django.db.models import ProtectedError
from rest_framework.exceptions import NotFound

from common.exceptions import exception_handler


def test_protected_error_becomes_409():
    response = exception_handler(ProtectedError("blocked", set()), context={})

    assert response.status_code == 409
    assert "can't be deleted" in response.data["detail"]


def test_other_errors_use_drf_handling():
    assert exception_handler(NotFound(), context={}).status_code == 404
