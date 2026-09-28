from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Category, Event, TicketType, Venue


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "address", "city", "capacity", "created_by", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]
        extra_kwargs = {"capacity": {"min_value": 1}}


class VenueSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "city"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class TicketTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = ["id", "event", "name", "price", "quantity_total", "quantity_available"]
        # Stock only moves through bookings (Phase 4) or total-quantity edits below.
        read_only_fields = ["id", "quantity_available"]
        extra_kwargs = {
            "price": {"min_value": Decimal("0")},
            "quantity_total": {"min_value": 1},
        }

    def validate_event(self, event):
        if self.instance is not None and event != self.instance.event:
            raise serializers.ValidationError("A ticket type can't be moved to another event.")
        return event

    def update(self, instance, validated_data):
        new_total = validated_data.get("quantity_total")
        if new_total is None or new_total == instance.quantity_total:
            return super().update(instance, validated_data)

        # Lock the row so a concurrent booking can't change the sold count mid-edit.
        with transaction.atomic():
            locked = TicketType.objects.select_for_update().get(pk=instance.pk)
            sold = locked.quantity_sold
            if new_total < sold:
                raise serializers.ValidationError(
                    {"quantity_total": f"{sold} tickets are already sold; it can't go below that."}
                )
            validated_data["quantity_available"] = new_total - sold
            return super().update(locked, validated_data)


class EventTicketTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = ["id", "name", "price", "quantity_total", "quantity_available"]


class EventSerializer(serializers.ModelSerializer):
    organizer = serializers.PrimaryKeyRelatedField(read_only=True)
    venue = VenueSummarySerializer(read_only=True)
    venue_id = serializers.PrimaryKeyRelatedField(
        source="venue", queryset=Venue.objects.all(), write_only=True
    )
    categories = serializers.SlugRelatedField(
        many=True, slug_field="slug", queryset=Category.objects.all(), required=False
    )
    ticket_types = EventTicketTypeSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "organizer",
            "venue",
            "venue_id",
            "categories",
            "starts_at",
            "ends_at",
            "status",
            "max_tickets_per_user",
            "ticket_types",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"max_tickets_per_user": {"min_value": 1}}

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "The event must end after it starts."})
        if self.instance is None and starts_at <= timezone.now():
            raise serializers.ValidationError({"starts_at": "New events must start in the future."})
        return attrs
