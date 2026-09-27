from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.tests.factories import OrganizerFactory
from apps.events.models import Category, Event, TicketType, Venue


class VenueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Venue

    name = factory.Sequence(lambda n: f"Venue {n}")
    address = factory.Sequence(lambda n: f"{n} Main Street")
    city = "Bengaluru"
    capacity = 500


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-"))


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Event

    organizer = factory.SubFactory(OrganizerFactory)
    venue = factory.SubFactory(VenueFactory)
    title = factory.Sequence(lambda n: f"Event {n}")
    starts_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    ends_at = factory.LazyAttribute(lambda o: o.starts_at + timedelta(hours=3))
    status = Event.Status.PUBLISHED


class TicketTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TicketType

    event = factory.SubFactory(EventFactory)
    name = factory.Sequence(lambda n: f"Tier {n}")
    price = Decimal("50.00")
    quantity_total = 100
