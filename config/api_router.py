"""Single router for every app's viewsets, mounted at /api/."""

from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = router.urls
