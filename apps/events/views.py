from django.db.models import Min
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from common.permissions import IsOrganizerOrReadOnly, IsOwnerOrReadOnly, IsStaffOrReadOnly

from .filters import EventFilter, VenueFilter
from .models import Category, Event, TicketType, Venue
from .serializers import (
    CategorySerializer,
    EventSerializer,
    TicketTypeSerializer,
    VenueSerializer,
)


class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer
    permission_classes = [IsOrganizerOrReadOnly, IsOwnerOrReadOnly]
    owner_field = "created_by"
    filterset_class = VenueFilter
    search_fields = ["name", "address", "city"]
    ordering_fields = ["name", "city", "capacity"]
    ordering = ["name", "id"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsStaffOrReadOnly]
    lookup_field = "slug"
    search_fields = ["name"]
    ordering_fields = ["name"]
    ordering = ["name"]


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsOrganizerOrReadOnly, IsOwnerOrReadOnly]
    owner_field = "organizer"
    filterset_class = EventFilter
    search_fields = ["title", "description", "venue__name"]
    ordering_fields = ["starts_at", "created_at", "min_price"]
    ordering = ["starts_at", "id"]

    def get_queryset(self):
        return (
            Event.objects.visible_to(self.request.user)
            .select_related("venue")
            .prefetch_related("categories", "ticket_types")
            .annotate(min_price=Min("ticket_types__price"))  # for ?ordering=min_price
        )

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)


class TicketTypeViewSet(viewsets.ModelViewSet):
    serializer_class = TicketTypeSerializer
    permission_classes = [IsOrganizerOrReadOnly, IsOwnerOrReadOnly]
    owner_field = "event.organizer"
    filterset_fields = ["event"]
    ordering_fields = ["price", "name"]
    ordering = ["event_id", "price", "id"]

    def get_queryset(self):
        visible_events = Event.objects.visible_to(self.request.user)
        return TicketType.objects.filter(event__in=visible_events).select_related("event")

    def perform_create(self, serializer):
        user = self.request.user
        event = serializer.validated_data["event"]
        if not (user.is_staff or event.organizer_id == user.pk):
            raise PermissionDenied("You can only add ticket types to your own events.")
        serializer.save()
