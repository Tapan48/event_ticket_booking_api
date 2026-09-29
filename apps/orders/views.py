import django_filters as filters
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .models import Order, Ticket
from .serializers import OrderSerializer, PlaceOrderSerializer, TicketSerializer
from .services import cancel_order, mark_order_paid, place_order


def orders_with_tickets():
    return Order.objects.prefetch_related("tickets__ticket_type__event")


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Your orders (staff see everyone's). Other users' orders are 404."""

    serializer_class = OrderSerializer
    filterset_fields = ["status"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation has no real user
            return Order.objects.none()
        user = self.request.user
        orders = orders_with_tickets()
        return orders if user.is_staff else orders.filter(user=user)

    @extend_schema(request=PlaceOrderSerializer, responses={201: OrderSerializer})
    def create(self, request):
        """Reserve tickets. The order holds them for ORDER_TTL_MINUTES until paid."""
        payload = PlaceOrderSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = place_order(
            request.user,
            payload.validated_data["event"],
            [(item["ticket_type"], item["quantity"]) for item in payload.validated_data["items"]],
        )
        return Response(self._render(order), status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=OrderSerializer)
    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        """Mock payment: marks a pending, unexpired order as paid."""
        return Response(self._render(mark_order_paid(self._own_order())))

    @extend_schema(request=None, responses=OrderSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a pending order and put its tickets back on sale."""
        return Response(self._render(cancel_order(self._own_order())))

    def _own_order(self):
        order = self.get_object()
        if order.user_id != self.request.user.pk:
            raise PermissionDenied("Only the buyer can pay for or cancel an order.")
        return order

    def _render(self, order):
        return OrderSerializer(orders_with_tickets().get(pk=order.pk)).data


class TicketFilter(filters.FilterSet):
    event = filters.NumberFilter(field_name="ticket_type__event", help_text="Event id.")

    class Meta:
        model = Ticket
        fields = ["event"]


class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    """Your valid tickets: those from paid orders."""

    serializer_class = TicketSerializer
    filterset_class = TicketFilter
    ordering_fields = ["created_at"]
    ordering = ["ticket_type__event__starts_at", "id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Ticket.objects.none()
        return Ticket.objects.filter(
            order__user=self.request.user, order__status=Order.Status.PAID
        ).select_related("ticket_type__event")
