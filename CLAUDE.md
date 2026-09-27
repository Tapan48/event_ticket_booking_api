# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Event Ticketing & Booking API (Django + DRF). Organizers create events and sell tickets; attendees browse, book, pay, and check in. The full phased roadmap is in `plan/plan_main.md` — read it before starting work and follow its phase order (finish and deploy before adding stretch features like Stripe).

As of this writing the repo contains only the plan; no code has been scaffolded yet. Update this file (commands, layout) once Phase 0 lands and they become real.

## Commands (planned — Docker Compose is the dev environment)

Postgres is required for development and tests: `select_for_update()` is a no-op on SQLite, so the locking/overselling tests are meaningless without Postgres. Do not switch tests to SQLite.

```bash
docker compose up                                   # web, db (postgres:16), redis, worker, beat
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py seed_demo
docker compose run --rm web pytest                  # full suite
docker compose run --rm web pytest apps/orders/tests/test_booking.py::test_name   # single test
docker compose run --rm web pytest -k oversell --count=20   # concurrency tests, repeated (pytest-repeat)
ruff check . && ruff format .
```

Settings are split `config/settings/{base,dev,test,prod}.py`; env comes from `.env` (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ORDER_TTL_MINUTES`).

## Architecture

- Apps live under `apps/`: `accounts` (custom `User` with email login + `role` attendee/organizer, `Profile` via post_save signal), `events` (Venue, Category, Event, TicketType), `orders` (Order, Ticket, booking services, Celery tasks, check-in), `payments` (Stripe, stretch only). Shared permissions/pagination/base model in `common/`.
- `AUTH_USER_MODEL` must be set before the first migration.
- **Business logic lives in `apps/orders/services.py`; views stay thin.** Key functions:
  - `place_order` — inside `transaction.atomic()`: lock the user row (serializes the per-user ticket limit), lock ticket types with `select_for_update().order_by("pk")` (consistent lock order prevents deadlocks), validate, decrement `quantity_available` with `F()`, create a `pending` Order with `expires_at` and its Tickets.
  - `release_order(order, status)` — used by both cancel and expiry; only acts on `pending` orders (idempotent) and restores stock with `F()`.
  - `mark_order_paid(order)` — the single path to `paid`, used by the mock `pay` endpoint now and the Stripe webhook later; sends the ticket email via `transaction.on_commit`.
  - Check-in is one conditional `UPDATE ... WHERE checked_in_at IS NULL AND order paid`; zero rows updated → diagnose as 404/409/400.
- DB constraints are the last line of defence and must be kept: `CheckConstraint` `quantity_available >= 0` (and `<= quantity_total`, `price >= 0`), `ends_at > starts_at`, `UniqueConstraint` on ticket `code` and `(event, name)` for ticket types. An `IntegrityError` from the quantity constraint maps to a 409 "sold out".
- Tickets are created at order time (pending) and are only valid for check-in once the order is `paid`.
- Celery beat runs `expire_stale_orders` every 60s, selecting with `select_for_update(skip_locked=True)`; the beat schedule is in settings (no django-celery-beat).
- Permissions: organizers edit only their own events/ticket types (ownership via `obj.event.organizer` for ticket types); attendees see only their own orders (other users' orders → 404 via queryset scoping, not 403); check-in is staff or that event's organizer. Owner fields are set from `request.user` in `perform_create`, never from the payload.

## Testing conventions

- pytest + pytest-django + factory-boy; fixtures (`api_client`, `attendee`, `organizer`, `staff`) in `conftest.py`.
- Concurrency tests use `@pytest.mark.django_db(transaction=True)`, threads synchronized with `threading.Barrier`, and must close each thread's DB connection.
- CI (GitHub Actions) runs ruff and `pytest --cov --cov-fail-under=85` against Postgres and Redis service containers.
