from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """DRF's handler, plus 409 for deletes blocked by on_delete=PROTECT."""
    if isinstance(exc, ProtectedError):
        return Response(
            {"detail": "This object is still referenced by other records and can't be deleted."},
            status=status.HTTP_409_CONFLICT,
        )
    return drf_exception_handler(exc, context)
