from datetime import timedelta

import factory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.events.tests.factories import TicketTypeFactory
from apps.orders.models import Order, Ticket


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    user = factory.SubFactory(UserFactory)
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=15))


class TicketFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Ticket

    order = factory.SubFactory(OrderFactory)
    ticket_type = factory.SubFactory(TicketTypeFactory)
    price_paid = factory.LazyAttribute(lambda o: o.ticket_type.price)
