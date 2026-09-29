from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.events.models import Event, TicketType

from .models import Order, Ticket


class OrderItemSerializer(serializers.Serializer):
    ticket_type = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=100)


class PlaceOrderSerializer(serializers.Serializer):
    event = serializers.IntegerField(min_value=1)
    items = OrderItemSerializer(many=True, allow_empty=False)


class EventSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "title", "starts_at"]


class TicketTypeSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = ["id", "name"]


class OrderTicketSerializer(serializers.ModelSerializer):
    ticket_type = TicketTypeSummarySerializer(read_only=True)
    code = serializers.SerializerMethodField(help_text="Shown once the order is paid.")

    class Meta:
        model = Ticket
        fields = ["id", "code", "ticket_type", "price_paid", "checked_in_at"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_code(self, ticket):
        # The code is the check-in credential; don't hand it out before payment.
        return ticket.code if ticket.order.status == Order.Status.PAID else None


class OrderSerializer(serializers.ModelSerializer):
    event = serializers.SerializerMethodField()
    tickets = OrderTicketSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "event",
            "total_amount",
            "expires_at",
            "paid_at",
            "created_at",
            "tickets",
        ]
        read_only_fields = fields

    @extend_schema_field(EventSummarySerializer(allow_null=True))
    def get_event(self, order):
        # Every ticket in an order belongs to the same event (place_order enforces it).
        first = next(iter(order.tickets.all()), None)
        return EventSummarySerializer(first.ticket_type.event).data if first else None


class TicketSerializer(serializers.ModelSerializer):
    event = EventSummarySerializer(source="ticket_type.event", read_only=True)
    ticket_type = TicketTypeSummarySerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = ["id", "code", "event", "ticket_type", "order", "price_paid", "checked_in_at"]
        read_only_fields = fields


class CheckInSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)


class CheckedInTicketSerializer(TicketSerializer):
    attendee = serializers.EmailField(source="order.user.email", read_only=True)

    class Meta(TicketSerializer.Meta):
        fields = [*TicketSerializer.Meta.fields, "attendee"]
        read_only_fields = fields
