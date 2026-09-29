from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class Conflict(APIException):
    """409: the request is valid but clashes with the resource's current state."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state of the resource."
    default_code = "conflict"


def exception_handler(exc, context):
    """DRF's handler, plus 409 for deletes blocked by on_delete=PROTECT."""
    if isinstance(exc, ProtectedError):
        return Response(
            {"detail": "This object is still referenced by other records and can't be deleted."},
            status=status.HTTP_409_CONFLICT,
        )
    return drf_exception_handler(exc, context)
