"""Single router for every app's viewsets, mounted at /api/."""

from rest_framework.routers import DefaultRouter

from apps.events.views import CategoryViewSet, EventViewSet, TicketTypeViewSet, VenueViewSet
from apps.orders.views import OrderViewSet, TicketViewSet

router = DefaultRouter()
router.register("venues", VenueViewSet, basename="venue")
router.register("categories", CategoryViewSet, basename="category")
router.register("events", EventViewSet, basename="event")
router.register("ticket-types", TicketTypeViewSet, basename="ticket-type")
router.register("orders", OrderViewSet, basename="order")
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = router.urls
