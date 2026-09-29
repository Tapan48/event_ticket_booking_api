"""
Booking logic. Every function that moves stock or changes an order's status
lives here, so views and (later) Celery tasks share one locking discipline:

- lock rows with select_for_update() inside transaction.atomic();
- lock ticket types in primary-key order, so concurrent orders can't deadlock;
- change stock with F() expressions, never read-modify-write in Python;
- the ticket_type_quantity_available_non_negative constraint is the backstop.
"""

from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.fields import DateTimeField

from apps.events.models import Event, TicketType
from common.exceptions import Conflict

from .models import Order, Ticket

STOCK_CONSTRAINT = "ticket_type_quantity_available_non_negative"
ACTIVE_STATUSES = [Order.Status.PENDING, Order.Status.PAID]


class SoldOut(Conflict):
    default_detail = "Not enough tickets left."
    default_code = "sold_out"


def place_order(user, event_id, items):
    """
    Reserve tickets for `user`. `items` is an iterable of (ticket_type_id, quantity).

    Returns a pending Order that holds its stock until `expires_at`.
    """
    requested = defaultdict(int)
    for ticket_type_id, quantity in items:
        if quantity < 1:
            raise ValidationError({"items": "Quantities must be at least 1."})
        requested[ticket_type_id] += quantity
    if not requested:
        raise ValidationError({"items": "Choose at least one ticket."})

    try:
        with transaction.atomic():
            # Queue this user's concurrent bookings so the per-user limit can't be raced.
            get_user_model().objects.select_for_update().get(pk=user.pk)
            ticket_types = list(
                TicketType.objects.select_for_update(of=("self",))
                .select_related("event")
                .filter(pk__in=requested, event_id=event_id)
                .order_by("pk")  # fixed lock order -> no deadlocks between orders
            )
            if len(ticket_types) != len(requested):
                raise ValidationError({"items": "Every ticket type must belong to this event."})

            event = ticket_types[0].event
            _check_event_is_bookable(event)
            _check_per_user_limit(user, event, sum(requested.values()))
            _check_availability(ticket_types, requested)

            for ticket_type in ticket_types:
                TicketType.objects.filter(pk=ticket_type.pk).update(
                    quantity_available=F("quantity_available") - requested[ticket_type.pk]
                )
            order = Order.objects.create(
                user=user,
                total_amount=sum(tt.price * requested[tt.pk] for tt in ticket_types),
                expires_at=timezone.now() + timedelta(minutes=settings.ORDER_TTL_MINUTES),
            )
            Ticket.objects.bulk_create(
                Ticket(order=order, ticket_type=tt, price_paid=tt.price)
                for tt in ticket_types
                for _ in range(requested[tt.pk])
            )
    except IntegrityError as exc:
        # Only reachable if the checks above were bypassed: the database still says no.
        if STOCK_CONSTRAINT in str(exc):
            raise SoldOut() from exc
        raise
    return order


def release_order(order, status):
    """Cancel or expire a pending order and put its tickets back on sale. Idempotent."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.PENDING:
            return order
        counts = defaultdict(int)
        for ticket_type_id in order.tickets.values_list("ticket_type_id", flat=True):
            counts[ticket_type_id] += 1
        for ticket_type_id in sorted(counts):  # same lock order as place_order
            TicketType.objects.filter(pk=ticket_type_id).update(
                quantity_available=F("quantity_available") + counts[ticket_type_id]
            )
        order.status = status
        order.save(update_fields=["status", "updated_at"])
    return order


def cancel_order(order):
    order = release_order(order, Order.Status.CANCELLED)
    if order.status != Order.Status.CANCELLED:
        raise Conflict(f"Only pending orders can be cancelled; this one is {order.status}.")
    return order


def mark_order_paid(order):
    """The single path to `paid` (mock payment now, Stripe webhook later)."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.PENDING:
            raise Conflict(f"Only pending orders can be paid; this one is {order.status}.")
        expired = order.expires_at <= timezone.now()
        if not expired:
            order.status = Order.Status.PAID
            order.paid_at = timezone.now()
            order.save(update_fields=["status", "paid_at", "updated_at"])
    if expired:
        # Commit the release first so the stock goes back on sale, then report it.
        release_order(order, Order.Status.EXPIRED)
        raise Conflict("This order expired and its tickets were released. Please book again.")
    return order


def check_in(code, user):
    """Admit a ticket once. Only staff or the event's organizer may scan."""
    ticket = (
        Ticket.objects.select_related("order__user", "ticket_type__event").filter(code=code).first()
    )
    if ticket is None:
        raise NotFound("No ticket has this code.")
    if not (user.is_staff or ticket.ticket_type.event.organizer_id == user.pk):
        raise PermissionDenied("Only staff or this event's organizer can check tickets in.")
    # Paid is terminal (paid orders can't be cancelled), so checking it first is race-free.
    if ticket.order.status != Order.Status.PAID:
        raise ValidationError({"code": f"This ticket's order is {ticket.order.status}, not paid."})

    now = timezone.now()
    # One conditional UPDATE on the ticket's own columns. If two scanners race, the
    # second waits on the row lock, then Postgres re-checks "checked_in_at IS NULL"
    # against the committed row and updates nothing.
    admitted = Ticket.objects.filter(pk=ticket.pk, checked_in_at__isnull=True).update(
        checked_in_at=now, checked_in_by=user, updated_at=now
    )
    if not admitted:
        ticket.refresh_from_db(fields=["checked_in_at"])
        raise Conflict(
            {
                "detail": "This ticket has already been checked in.",
                "checked_in_at": DateTimeField().to_representation(ticket.checked_in_at),
            }
        )
    ticket.checked_in_at, ticket.checked_in_by = now, user
    return ticket


def _check_event_is_bookable(event):
    if event.status != Event.Status.PUBLISHED:
        raise ValidationError({"event": "This event isn't open for booking."})
    if event.has_started:
        raise ValidationError({"event": "This event has already started."})


def _check_per_user_limit(user, event, quantity):
    held = Ticket.objects.filter(
        order__user=user, order__status__in=ACTIVE_STATUSES, ticket_type__event=event
    ).count()
    if held + quantity > event.max_tickets_per_user:
        raise ValidationError(
            {
                "items": f"You can hold at most {event.max_tickets_per_user} tickets for this "
                f"event; you already have {held}."
            }
        )


def _check_availability(ticket_types, requested):
    for ticket_type in ticket_types:
        if ticket_type.quantity_available < requested[ticket_type.pk]:
            raise SoldOut(
                f"Only {ticket_type.quantity_available} '{ticket_type.name}' tickets left."
            )
