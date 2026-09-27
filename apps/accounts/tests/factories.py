import factory

from apps.accounts.models import User

DEFAULT_PASSWORD = "testpass123!"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.django.Password(DEFAULT_PASSWORD)
    role = User.Role.ATTENDEE


class OrganizerFactory(UserFactory):
    role = User.Role.ORGANIZER


class StaffFactory(UserFactory):
    is_staff = True
