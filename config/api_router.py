"""Single router for every app's viewsets, mounted at /api/."""

from rest_framework.routers import DefaultRouter

from apps.events.views import CategoryViewSet, EventViewSet, TicketTypeViewSet, VenueViewSet

router = DefaultRouter()
router.register("venues", VenueViewSet, basename="venue")
router.register("categories", CategoryViewSet, basename="category")
router.register("events", EventViewSet, basename="event")
router.register("ticket-types", TicketTypeViewSet, basename="ticket-type")

urlpatterns = router.urls
