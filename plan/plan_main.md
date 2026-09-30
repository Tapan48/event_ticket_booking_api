# Event Ticketing & Booking API — Build Plan

## Context
A portfolio/resume project: a Django REST API where organizers create events and sell tickets, and attendees browse, book, pay, and check in. The main talking point is **overselling protection**: two people must never get the last ticket. We solve it with `transaction.atomic()`, `select_for_update()`, `F()` expressions and a DB `CheckConstraint`, and a concurrency test proves it works.

The project directory is empty (only `hi.txt`) and is not yet a git repo. Local tools: Python 3.14, Docker, Postgres and Redis (Homebrew).

**Decisions made:**
- Local dev runs on Docker Compose from day 1, with Postgres and Redis. SQLite can't do `select_for_update`, so the locking test needs real Postgres.
- Stripe is an **optional stretch phase after deployment**. v1 uses a mock `pay` endpoint that calls the same `mark_order_paid()` service the Stripe webhook will call later.
- Deploy target is the **existing Oracle Cloud ARM instance**, alongside the RAG app, using a separate `ticket-booking` Compose project and `docker-compose.prod.yml`.
- Mode: after you approve the plan, I build **Phase 0 + Phase 1** with you. We then go phase by phase.

Goal: **finish and deploy first**, with a live link, a clean README and ≥90% test coverage (matching the repository's coverage configuration). Extras come after that.

---

## Tech stack
| Concern | Choice |
|---|---|
| Framework | Django 5.2 LTS + Django REST Framework |
| Auth | djangorestframework-simplejwt (access + refresh, rotation + blacklist) |
| Filtering | django-filter, DRF SearchFilter/OrderingFilter |
| Docs | drf-spectacular (Swagger UI at `/api/docs/`) |
| DB / cache / broker | PostgreSQL 16, Redis 7 |
| Async | Celery 5 + celery beat (schedule set in settings, so django-celery-beat isn't needed) |
| Config | django-environ (`.env`), split settings: `base / dev / test / prod` |
| Serving | gunicorn + whitenoise |
| Tests | pytest, pytest-django, factory-boy, pytest-cov |
| Quality | ruff (lint + format), pre-commit |
| Container | `python:3.13-slim` image (safest wheel support for Celery/psycopg) |

## Project layout
```
ticket_booking_api/
├── config/              settings/{base,dev,test,prod}.py, urls.py, celery.py, wsgi.py
├── apps/
│   ├── accounts/        User, Profile, register/me views, signals
│   ├── events/          Venue, Category, Event, TicketType, filters, permissions
│   ├── orders/          Order, Ticket, services.py (booking logic), tasks.py, check-in
│   └── payments/        (stretch) Stripe checkout + webhook
├── common/              shared permissions, pagination, base model (created_at/updated_at)
├── tests/               or per-app tests/ folders; factories.py, conftest.py
├── plan/plan_main.md    this build plan (roadmap, kept in the repo)
├── docs/erd.png
├── Dockerfile, docker-compose.yml, docker-compose.prod.yml, .env.example
├── .github/workflows/ci.yml
├── requirements.txt, requirements-dev.txt, pyproject.toml (ruff + pytest config)
└── README.md
```

## Data model (final shape)
- **User** (`AbstractUser`): email is unique and is the login field (`USERNAME_FIELD`). `role` is `attendee | organizer`. Staff use `is_staff`.
- **Profile** (OneToOne → User): phone, bio, city. Auto-created by a `post_save` signal.
- **Venue**: name, address, `city` (indexed), capacity, `created_by` FK → User.
- **Category**: name, `slug` (unique).
- **Event**: `organizer` FK → User, `venue` FK → Venue (`PROTECT`, related_name `events`), `categories` M2M → Category, title, description, `starts_at` (indexed), `ends_at`, `status` (`draft | published | cancelled`), `max_tickets_per_user` (default 10).
  - `CheckConstraint(ends_at > starts_at)`
- **TicketType** (FK → Event, related_name `ticket_types`): name, `price` (Decimal), `quantity_total`, `quantity_available`.
  - `CheckConstraint(quantity_available >= 0)` is the last line of defence against overselling.
  - `CheckConstraint(quantity_available <= quantity_total)`, `CheckConstraint(price >= 0)`
  - `UniqueConstraint(event, name)`
- **Order** (FK → User): `status` (`pending | paid | cancelled | expired`), `total_amount`, `expires_at`, `paid_at`, `stripe_session_id` (nullable, for later). Index on `(status, expires_at)` for the expiry sweep.
- **Ticket**: FK → Order, FK → TicketType, `code` (random URL-safe token), `price_paid` (snapshot), `checked_in_at` (nullable), `checked_in_by` (nullable FK → User).
  - `UniqueConstraint(code)`

Tickets are created when the order is placed (status `pending`). A ticket is only valid for check-in when its order is `paid`. When an order expires or is cancelled, its quantity goes back to `TicketType.quantity_available`.

## API surface
| Method & path | Who |
|---|---|
| `POST /api/auth/register/`, `POST /api/auth/login/`, `POST /api/auth/refresh/`, `POST /api/auth/logout/` | public / authed |
| `GET/PATCH /api/auth/me/` (user + profile) | authed |
| `/api/venues/` CRUD | read: anyone; write: organizers; edit/delete: creator or staff |
| `/api/categories/` | read: anyone; write: staff |
| `/api/events/` CRUD (+ `?city=&starts_after=&starts_before=&category=&min_price=&max_price=&search=&ordering=`) | read: published events for everyone, drafts for the owner; write: organizer owner or staff |
| `/api/ticket-types/` CRUD (`?event=`) | write: the event's organizer only |
| `POST /api/orders/` `{event, items:[{ticket_type, quantity}]}` | attendee (authed) |
| `GET /api/orders/`, `GET /api/orders/{id}/` | owner only; staff see all |
| `POST /api/orders/{id}/pay/` (mock in v1), `POST /api/orders/{id}/cancel/` | owner |
| `GET /api/tickets/` (my tickets) | owner |
| `POST /api/checkin/` `{code}` | staff or that event's organizer |
| `GET /api/docs/`, `GET /api/schema/`, `GET /health/` | public |

---

## Phases

### Phase 0 — Project setup (Day 1–2)
1. Run `git init` and create `.gitignore`. Create the GitHub repo only when you choose to.
2. Write `requirements.txt` / `requirements-dev.txt` and `pyproject.toml` (ruff, pytest, coverage config).
3. Scaffold the Django project into `config/` with split settings. `DATABASE_URL`, `REDIS_URL` and `SECRET_KEY` come from `.env`, plus a `.env.example`.
4. Add a `Dockerfile` and a `docker-compose.yml` with `web` (runserver), `db` (postgres:16), `redis`, `worker` and `beat`. The last two are placeholders until Phase 5.
5. Add a `/health/` endpoint and pre-commit with ruff.

**Done when:** `docker compose up` serves `/health/` and `docker compose run web pytest` runs (0 tests).

### Phase 1 — Models, migrations, admin, ERD (Week 1)
1. Create a `common.TimeStampedModel` abstract base.
2. Add the `accounts` app: custom `User` (set `AUTH_USER_MODEL` **before the first migration**), a `Profile` with a signal, and a manager for email login.
3. Add the `events` app: Venue, Category, Event, TicketType with all the constraints above.
4. Add the `orders` app: Order and Ticket, the ticket code generator (`secrets.token_urlsafe`), and the constraints.
5. Register everything in Django admin, with inlines for TicketType on Event and Ticket on Order, plus `list_filter` and `search_fields`.
6. Add a `seed_demo` management command that creates venues, categories, organizers, events and ticket types (useful for demos and the live site).
7. Generate the ERD with `django-extensions graph_models` (or draw it in dbdiagram.io) and save it to `docs/erd.png`.
8. Write model tests: constraints raise `IntegrityError` (negative quantity, duplicate code, `ends_at` before `starts_at`) and a profile is auto-created.

**Done when:** migrations apply on Postgres, admin works, constraint tests pass and the ERD is committed.

### Phase 2 — Auth + CRUD + permissions (Week 1–2)
1. Set up simplejwt: register serializer (validates password, sets role), login (token obtain), refresh, and logout (blacklist the refresh token). Add the `me` endpoint.
2. Write `common/permissions.py`:
   - `IsOrganizer`: role is organizer, or staff.
   - `IsOwnerOrReadOnly`: configurable owner field (`organizer`, `created_by`).
   - `IsEventOrganizer`: for TicketType, where the owner is found via `obj.event.organizer`.
   - `CanCheckIn`: staff or the event's organizer.
3. Build ModelViewSets with a `DefaultRouter` for venues, categories, events and ticket-types. `perform_create` sets the organizer from `request.user`, never from the payload.
4. Scope querysets: the public sees only published events, organizers also see their own drafts, and ticket-type create checks that `event.organizer == request.user`.
5. Use `select_related` / `prefetch_related` on list views to avoid N+1 queries. Check with `django-debug-toolbar` or `assertNumQueries`.
6. Add drf-spectacular now so docs grow alongside the code.

**Done when:** permission tests pass. An attendee can't create events, organizer A can't edit organizer B's event (403), and unauthenticated users can read but not write.

### Phase 3 — Filtering, search, pagination + test suite (Week 2)
1. Write `EventFilter` (django-filter):
   - `city`: `venue__city__iexact`
   - `starts_after` / `starts_before`: date range
   - `category`: slug
   - `min_price` / `max_price`: `ticket_types__price`, with `.distinct()`
2. Use `SearchFilter` on title/description and `OrderingFilter` on `starts_at`, `created_at` and price.
3. Set a global `PageNumberPagination` (page_size 20, `?page_size=` up to 100).
4. Add factory-boy factories for every model and a `conftest.py` with `api_client`, `attendee`, `organizer` and `staff` fixtures plus an authenticated-client helper.
5. Write tests for each filter, search, pagination shape and the permission matrix, and add coverage reporting.

**Done when:** the filter/search/pagination tests pass and coverage is ≥80%.

### Phase 4 — Booking flow with locking (Week 3) ★ main talking point
`apps/orders/services.py` holds all the business logic. Views stay thin.
```python
def place_order(user, event_id, items) -> Order:
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)       # serializes this user's concurrent bookings (per-user limit)
        types = (TicketType.objects.select_for_update()
                 .filter(pk__in=ids, event_id=event_id)
                 .select_related("event").order_by("pk"))       # fixed lock order -> no deadlocks
        # validate: event published, not started, qty > 0, availability, per-user limit
        #   (count of user's tickets in pending/paid orders for this event + requested <= max_tickets_per_user)
        for tt, qty in ...:
            TicketType.objects.filter(pk=tt.pk).update(quantity_available=F("quantity_available") - qty)
        order = Order.objects.create(user=user, status=PENDING, total_amount=..., expires_at=now()+15min)
        Ticket.objects.bulk_create([...])
    return order
```
- `release_order(order, new_status)`: runs in a transaction and locks the order. It only acts on `pending` orders, so it is idempotent. It adds quantities back with `F()` and is used by both cancel and expiry.
- `mark_order_paid(order)`: locks the order and rejects it if it isn't pending or is past `expires_at`. It sets `paid`/`paid_at`, then `transaction.on_commit(send_ticket_email.delay)`, which is a no-op until Phase 5.
- **Check-in** is one atomic conditional update: `Ticket.objects.filter(code=code, checked_in_at__isnull=True, order__status=PAID).update(checked_in_at=now(), checked_in_by=user)`. If 0 rows change, look up why and return 404 (unknown), 409 (already checked in, with the time) or 400 (unpaid). The caller must be staff or that event's organizer.
- Validation errors return clean 400s with field messages. A caught `IntegrityError` from the CheckConstraint becomes a 409 "sold out".
- **Tests:**
  - past event is rejected
  - quantity above availability is rejected
  - the per-user limit holds across multiple orders
  - an attendee can't see another user's order (404)
  - cancel restores stock
  - paying an expired order fails
  - double check-in returns 409
  - **Overselling test:** `@pytest.mark.django_db(transaction=True)`, a ticket type with quantity 1, and 10–20 threads started together with a `threading.Barrier`, each calling `place_order` and closing its DB connection. Assert exactly 1 success, `quantity_available == 0` and exactly 1 ticket.
  - A second test checks the per-user limit under concurrency.
  - (Demo tip: temporarily remove `select_for_update` and watch the test fail. That makes a great README/interview story.)

**Done when:** the whole booking lifecycle works via Swagger and the concurrency tests pass reliably, running 20 times in a loop.

### Phase 5 — Celery + Redis (Week 3–4)
1. Add `config/celery.py`, autodiscover tasks, and enable the Compose `worker` and `beat` services.
2. `send_ticket_email(order_id)`: sends an HTML + text email listing ticket codes (a QR code image is optional). It retries with exponential backoff. Dev uses Django's console backend (or Mailpit in Compose). Prod uses SMTP (e.g. Brevo or Mailtrap free tier).
3. `expire_stale_orders()`: runs from beat every 60s. It picks pending orders with `expires_at < now()` using `select_for_update(skip_locked=True)` and calls `release_order(..., EXPIRED)` for each. It is idempotent, so running twice doesn't matter.
4. **Tests:** call the tasks directly (and use `CELERY_TASK_ALWAYS_EAGER` in the test settings). Check that expiry restores stock, paid orders are untouched and the email lands in `mail.outbox`.

**Done when:** in Compose, a paid order sends an email and an unpaid order expires after 15 minutes. Use a short env override such as `ORDER_TTL_MINUTES=1` for the demo.

### Phase 6 — Docker, CI, Oracle deployment, README (Week 4)
Deploy on the existing Oracle instance alongside the RAG app. Read-only inspection confirmed 2 ARM cores, approximately 12 GiB RAM with 10 GiB available, 42 GB free disk, and five healthy RAG containers. These are capacity snapshots, not peak-load guarantees; recheck before deployment. Reuse the current instance without resizing it or provisioning paid services.

1. Make the Dockerfile production-ready: ARM64-compatible runtime dependencies, non-root user, production requirements, `collectstatic`, and a Gunicorn entrypoint. Keep local development in `docker-compose.yml`.
2. `.github/workflows/ci.yml` runs on push/PR:
   - service containers for postgres:16 and redis:7
   - `ruff check .` and `ruff format --check .`
   - `pytest --cov --cov-fail-under=90` (matching `pyproject.toml`)
   - a CI badge in the README
3. Add a standalone `docker-compose.prod.yml`, deployed from a separate directory with project name `ticket-booking`:
   - Gunicorn web service, PostgreSQL 16, Redis 7, Celery worker, and one separate Beat service; omit development bind mounts and Mailpit.
   - Dedicated credentials, Compose network, and persistent database volume; do not reuse the RAG app's database, Redis, or volumes. Do not publish database or Redis ports.
   - Health checks, restart policies, bounded logs, and resource limits. Start with two Gunicorn workers and Celery concurrency 1 to leave CPU capacity for the existing app.
4. Use a separate public port, leaving the RAG frontend's ports 80/443 and configuration unchanged. Recheck port availability before deployment. Configure trusted HTTPS for the new endpoint before publishing credentials, and allow only the chosen public port in OCI network rules and the host firewall. A different port alone does not provide TLS.
5. Set `DJANGO_SETTINGS_MODULE=config.settings.prod` explicitly in the production Compose configuration for web, worker, Beat, and management commands. Configure `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` (including the public port), secure cookies, trusted proxy headers, WhiteNoise, logging, and production SMTP via `EMAIL_URL`. Keep secrets in a server-only environment file outside version control.
6. Document the deployment sequence: back up the ticket-booking database on updates, build the ARM64 image, start and verify database/Redis health, run migrations as a one-off production command, then start web/worker/Beat and verify health. Use project-scoped commands so the RAG stack is not restarted or recreated. Retain the prior image and document rollback, including database restore when migrations are incompatible.
7. Document scheduled PostgreSQL backups with a copy off the instance and a verified restore procedure. Seed the live DB with `seed_demo` and publish only demo organizer/attendee credentials in the README; keep administrative credentials private.
8. **README** covers:
   - a one-line pitch and the live URL + Swagger link
   - the ERD image
   - an architecture diagram (API ↔ Postgres ↔ Redis ↔ Celery)
   - a "How overselling is prevented" section with a code snippet and the test
   - local setup (`docker compose up`)
   - Oracle production setup, the separate public port and HTTPS configuration, deployment/update commands, logs, and backup/restore instructions
   - the endpoint table and the test/coverage badge

**Done when:** the live HTTPS URL works end-to-end, paid orders send email, unpaid orders expire and restore stock, containers recover after restart, database restore is verified, CI passes with ≥90% coverage, and the README is complete. Confirm the existing RAG app remains healthy and reachable after deployment. **Stop here and ship.**

### Phase 7 — Event marketplace frontend

See [the approved frontend plan](plan_7_frontend.md). Build a responsive light React
marketplace for attendees and organizers: browse/filter, register/login, reserve,
demo pay, order history/tickets, organizer event/venue/tier editing and check-in.
Keep Swagger and JWT for development/testing. Serve the frontend on the existing
Oracle ticket endpoint using cookie/CSRF authentication; preserve the RAG stack.
Validate browser workflows, security, mobile layout, production images and CI
before deploying. Status: implementation and release verification in progress.

### Phase 8 — Stretch (only after frontend deploy)
1. **Stripe (test mode):**
   - `POST /orders/{id}/checkout/` creates a Checkout Session with `expires_at` matching the order TTL.
   - `POST /api/payments/webhook/` verifies the signature and handles `checkout.session.completed`, which calls `mark_order_paid()`.
   - Store processed event IDs so replayed webhooks are ignored.
   - Test with the Stripe CLI (`stripe listen`).
2. Nice-to-haves:
   - QR code in the email
   - an organizer sales-stats endpoint (aggregations)
   - rate limiting (DRF throttling) on booking
   - soft-cancel of an event that refunds or cancels its orders

---

## Resume talking points (build towards these)
1. Overselling prevention: row locks + atomic transactions + `F()` + a DB CheckConstraint, proven by a concurrent-threads test on Postgres.
2. Deadlock avoidance through consistent lock ordering. `skip_locked` lets the expiry worker run without blocking checkout.
3. An idempotent, race-free check-in using one conditional UPDATE.
4. Background jobs: email with retries, and a periodic expiry that returns inventory.
5. Production: Docker, CI on Postgres, OpenAPI docs, live deployment.

## Verification (per phase and final)
- Every phase runs `docker compose run --rm web pytest` and `ruff check .`.
- Phase 1: `python manage.py migrate` on a fresh DB, log in to admin, run `seed_demo`.
- Phase 4: run `pytest -k oversell --count=20` (pytest-repeat). Manual Swagger run: register → login → book → pay → check-in → check-in again returns 409.
- Phase 5: watch `docker compose logs worker beat` and check that the order flips to `expired` and stock is restored.
- Phase 6: CI is green on GitHub with ≥90% coverage. Run the full lifecycle against the live Oracle-hosted HTTPS URL with curl/Swagger, verify email delivery and order expiry, check restart recovery and database restore, and confirm the existing RAG app remains healthy and reachable.

## What I'll build right after approval
0. **First step:** save this full plan into the project as `plan/plan_main.md`, creating the `plan/` folder in the project root. It becomes the in-repo roadmap and gets committed with Phase 0.
1. Phase 0 (scaffold, Compose, settings, health check, git init) and Phase 1 (all models with constraints, migrations, admin, `seed_demo`, constraint tests, ERD). Then we review together before Phase 2.

---

## Sub-plans
Each phase gets a detailed sub-plan in this folder, named `plan_<n>_<name>.md`.

| Phase | Sub-plan | Status |
|---|---|---|
| 0 — Project setup | [plan_0_project_setup.md](plan_0_project_setup.md) | ✅ done |
| 1 — Models, migrations, admin, ERD | [plan_1_models.md](plan_1_models.md) | ✅ done |
| 2 — Auth, CRUD, permissions | [plan_2_auth_crud.md](plan_2_auth_crud.md) | ✅ done |
| 3 — Filtering, search, pagination | [plan_3_filtering.md](plan_3_filtering.md) | ✅ done |
| 4 — Booking with locking | [plan_4_booking.md](plan_4_booking.md) | ✅ done |
| 5 — Celery: emails, order expiry | [plan_5_celery.md](plan_5_celery.md) | ✅ done |
| 6 — Oracle deployment, CI, operations | [plan_6_deployment.md](plan_6_deployment.md) | ✅ done |

| 7 — Event marketplace frontend | [plan_7_frontend.md](plan_7_frontend.md) | In progress |
