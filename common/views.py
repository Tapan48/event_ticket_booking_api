from django.db import OperationalError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    """Liveness + DB reachability probe for container health checks."""
    try:
        connection.ensure_connection()
    except OperationalError:
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})
