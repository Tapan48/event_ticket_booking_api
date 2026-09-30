"""Same-origin browser sessions; the existing JWT API remains available."""

from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import BrowserLoginSerializer, BrowserSessionSerializer


@method_decorator(never_cache, name="dispatch")
@method_decorator(csrf_protect, name="dispatch")
class BrowserSessionView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=BrowserSessionSerializer)
    def get(self, request):
        return Response(
            {"csrf_token": get_token(request), "authenticated": request.user.is_authenticated}
        )

    @extend_schema(request=BrowserLoginSerializer, responses=BrowserSessionSerializer)
    def post(self, request):
        payload = BrowserLoginSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        user = authenticate(request, **payload.validated_data)
        if user is None:
            return Response({"detail": "Email or password is incorrect."}, status=401)
        login(request, user)
        # Return the rotated CSRF token; clients must use it for subsequent writes.
        return Response({"csrf_token": get_token(request), "authenticated": True})

    @extend_schema(request=None, responses=BrowserSessionSerializer)
    def delete(self, request):
        logout(request)
        return Response({"csrf_token": get_token(request), "authenticated": False})
