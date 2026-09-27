from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from common.models import TimeStampedModel


class Venue(TimeStampedModel):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100, db_index=True)
    capacity = models.IntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="venues",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(capacity__gt=0),
                name="venue_capacity_positive",
                violation_error_message="Capacity must be greater than zero.",
            ),
        ]

    def __str__(self):
        return f"{self.name}, {self.city}"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class EventStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    CANCELLED = "cancelled", "Cancelled"


class Event(TimeStampedModel):
    Status = EventStatus

    # PROTECT: an event with sold tickets must never disappear with its organizer or venue.
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="organized_events"
    )
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="events")
    categories = models.ManyToManyField(Category, related_name="events", blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=EventStatus.choices, default=EventStatus.DRAFT)
    max_tickets_per_user = models.SmallIntegerField(default=10)

    class Meta:
        ordering = ["starts_at"]
        indexes = [
            # Public listing: published events ordered/filtered by start time.
            models.Index(fields=["status", "starts_at"], name="event_status_starts_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="event_ends_after_starts",
                violation_error_message="The event must end after it starts.",
            ),
            models.CheckConstraint(
                condition=Q(max_tickets_per_user__gte=1),
                name="event_max_tickets_per_user_positive",
                violation_error_message="Max tickets per user must be at least 1.",
            ),
            models.CheckConstraint(
                condition=Q(status__in=EventStatus.values), name="event_status_valid"
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def has_started(self):
        return self.starts_at <= timezone.now()


class TicketType(TimeStampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_total = models.IntegerField()
    quantity_available = models.IntegerField(
        blank=True, help_text="Defaults to the total quantity when left empty."
    )

    class Meta:
        ordering = ["event", "price"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "name"], name="unique_ticket_type_name_per_event"
            ),
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="ticket_type_price_non_negative",
                violation_error_message="Price cannot be negative.",
            ),
            # Last line of defence against overselling: the database refuses any
            # decrement that would take stock below zero, even if app-level checks race.
            # Together with available <= total this also forces total >= 0.
            models.CheckConstraint(
                condition=Q(quantity_available__gte=0),
                name="ticket_type_quantity_available_non_negative",
                violation_error_message="Available quantity cannot be negative.",
            ),
            models.CheckConstraint(
                condition=Q(quantity_available__lte=F("quantity_total")),
                name="ticket_type_available_lte_total",
                violation_error_message="Available quantity cannot exceed the total quantity.",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.event})"

    def clean(self):
        self._default_quantity_available()

    def save(self, *args, **kwargs):
        self._default_quantity_available()
        super().save(*args, **kwargs)

    @property
    def quantity_sold(self):
        return self.quantity_total - self.quantity_available

    def _default_quantity_available(self):
        if self.quantity_available is None:
            self.quantity_available = self.quantity_total
