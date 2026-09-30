from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.events.models import Category, Event, TicketType, Venue

User = get_user_model()

DEFAULT_PASSWORD = "demo-pass-123"

USERS = [
    {"email": "organizer@demo.dev", "role": User.Role.ORGANIZER, "first_name": "Olivia"},
    {"email": "organizer2@demo.dev", "role": User.Role.ORGANIZER, "first_name": "Omar"},
    {"email": "attendee@demo.dev", "role": User.Role.ATTENDEE, "first_name": "Asha"},
    {"email": "staff@demo.dev", "role": User.Role.ATTENDEE, "first_name": "Sam", "is_staff": True},
]

CATEGORIES = ["Music", "Tech", "Comedy", "Sports", "Food & Drink"]

# (name, address, city, capacity)
VENUES = [
    ("Palace Grounds", "Jayamahal Road", "Bengaluru", 5000),
    ("NESCO Centre", "Western Express Hwy", "Mumbai", 3000),
    ("Siri Fort Auditorium", "August Kranti Marg", "Delhi", 1800),
    ("Phoenix Hall", "Viman Nagar", "Pune", 600),
]

# (title, organizer #, venue #, days from now, start hour, hours long, status, categories, tiers)
EVENTS = [
    ("Indie Rock Night", 0, 0, 14, 19, 4, "published", ["Music"],
     [("General", "999.00", 400), ("VIP", "2999.00", 50)]),
    ("PyCon Local 2026", 0, 3, 21, 9, 8, "published", ["Tech"],
     [("Student", "499.00", 100), ("Professional", "1499.00", 200)]),
    ("Stand-up Saturday", 1, 1, 6, 20, 2, "published", ["Comedy"],
     [("Front Row", "1200.00", 5), ("General", "600.00", 150)]),
    ("Street Food Festival", 1, 2, 30, 12, 9, "published", ["Food & Drink", "Music"],
     [("Day Pass", "299.00", 1000)]),
    ("City Marathon Expo", 1, 2, 45, 7, 6, "published", ["Sports"],
     [("Runner Kit", "1800.00", 300)]),
    ("Jazz by the Lake", 0, 0, -10, 18, 3, "published", ["Music"],
     [("General", "799.00", 200)]),
    ("AI Builders Meetup", 0, 3, 60, 17, 3, "draft", ["Tech"],
     [("Free RSVP", "0.00", 80)]),
    ("Monsoon Comedy Gala", 1, 1, 10, 19, 3, "cancelled", ["Comedy"],
     [("General", "700.00", 250)]),
]  # fmt: skip


class Command(BaseCommand):
    help = "Create demo users, venues, categories, events and ticket types. Safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument(
            "--public", action="store_true", help="Seed only non-staff demo accounts."
        )
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help="Password for newly created demo users (existing users are left untouched).",
        )

    @transaction.atomic
    def handle(self, *args, password, public, **options):
        if getattr(settings, "PUBLIC_DEMO_ONLY", False) and not public:
            raise CommandError(
                "Production demo seeding requires --public; create admins separately."
            )
        demo_users = [data for data in USERS if not (public and data.get("is_staff"))]
        if (
            public
            and User.objects.filter(
                email__in=[data["email"] for data in USERS], is_staff=True
            ).exists()
        ):
            raise CommandError("A privileged demo account exists; remove its public access first.")
        if (
            public
            and User.objects.filter(
                email__in=[data["email"] for data in USERS], is_superuser=True
            ).exists()
        ):
            raise CommandError("A privileged demo account exists; remove its public access first.")
        users = [self._get_or_create_user(password=password, **data) for data in demo_users]
        organizers = [u for u in users if u.is_organizer]
        categories = {
            name: Category.objects.get_or_create(slug=slugify(name), defaults={"name": name})[0]
            for name in CATEGORIES
        }
        venues = [
            Venue.objects.get_or_create(
                name=name,
                city=city,
                defaults={"address": address, "capacity": capacity, "created_by": organizers[0]},
            )[0]
            for name, address, city, capacity in VENUES
        ]

        today = timezone.now().replace(minute=0, second=0, microsecond=0)
        for title, org, venue, days, hour, hours, status, cats, tiers in EVENTS:
            starts_at = (today + timedelta(days=days)).replace(hour=hour)
            event, created = Event.objects.get_or_create(
                title=title,
                organizer=organizers[org],
                defaults={
                    "venue": venues[venue],
                    "description": f"{title} — a demo event.",
                    "starts_at": starts_at,
                    "ends_at": starts_at + timedelta(hours=hours),
                    "status": status,
                },
            )
            if created:
                event.categories.set(categories[name] for name in cats)
            for name, price, quantity in tiers:
                TicketType.objects.get_or_create(
                    event=event,
                    name=name,
                    defaults={"price": Decimal(price), "quantity_total": quantity},
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: {User.objects.count()} users, {Venue.objects.count()} venues, "
                f"{Event.objects.count()} events, {TicketType.objects.count()} ticket types."
            )
        )
        self.stdout.write(f"Demo accounts: {', '.join(u.email for u in users)}")

    def _get_or_create_user(self, email, password, **fields):
        user, created = User.objects.get_or_create(email=email, defaults=fields)
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user
