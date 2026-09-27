import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q

from common.models import TimeStampedModel


def generate_ticket_code():
    # 12 random bytes -> 16 URL-safe characters (96 bits): unguessable and QR-friendly.
    return secrets.token_urlsafe(12)


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"
    EXPIRED = "expired", "Expired"


class Order(TimeStampedModel):
    Status = OrderStatus

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    expires_at = models.DateTimeField(help_text="Unpaid orders are released after this time.")
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Expiry sweep: WHERE status = 'pending' AND expires_at < now().
            models.Index(fields=["status", "expires_at"], name="order_status_expires_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=OrderStatus.values), name="order_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gte=0),
                name="order_total_non_negative",
                violation_error_message="Order total cannot be negative.",
            ),
            models.CheckConstraint(
                condition=~Q(status=OrderStatus.PAID) | Q(paid_at__isnull=False),
                name="order_paid_requires_paid_at",
                violation_error_message="A paid order must record when it was paid.",
            ),
        ]

    def __str__(self):
        return f"Order #{self.pk} ({self.status})"


class Ticket(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tickets")
    # PROTECT: sold tickets keep their ticket type (and so their event) from being deleted.
    ticket_type = models.ForeignKey(
        "events.TicketType", on_delete=models.PROTECT, related_name="tickets"
    )
    code = models.CharField(max_length=32, default=generate_ticket_code, editable=False)
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checked_in_tickets",
    )

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["code"], name="unique_ticket_code"),
            models.CheckConstraint(
                condition=Q(price_paid__gte=0),
                name="ticket_price_paid_non_negative",
                violation_error_message="Price paid cannot be negative.",
            ),
            models.CheckConstraint(
                condition=Q(checked_in_by__isnull=True) | Q(checked_in_at__isnull=False),
                name="ticket_checked_in_by_requires_time",
                violation_error_message="A check-in must record when it happened.",
            ),
        ]

    def __str__(self):
        return self.code

    @property
    def is_checked_in(self):
        return self.checked_in_at is not None
