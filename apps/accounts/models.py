from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q

from common.models import TimeStampedModel

from .managers import UserManager


class Role(models.TextChoices):
    ATTENDEE = "attendee", "Attendee"
    ORGANIZER = "organizer", "Organizer"


class User(AbstractUser):
    """Logs in with email. Organizers sell tickets; attendees buy them; staff use is_staff."""

    Role = Role

    username = None
    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ATTENDEE)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(role__in=Role.values), name="user_role_valid"),
        ]

    def __str__(self):
        return self.email

    @property
    def is_organizer(self):
        return self.role == self.Role.ORGANIZER


class Profile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    phone = models.CharField(max_length=30, blank=True)
    bio = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Profile of {self.user}"
