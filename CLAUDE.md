# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Event Ticketing & Booking API (Django + DRF). Organizers create events and sell tickets; attendees browse, book, pay, and check in. The full phased roadmap is in `plan/plan_main.md`; each phase has a detailed sub-plan `plan/plan_<n>_<name>.md` (write one before starting a phase and add it to the index at the bottom of `plan_main.md`). Follow the phase order — finish and deploy before stretch features like Stripe.

Phase 0 (project skeleton) is done. Sections below marked "(planned)" describe code that doesn't exist yet.

**Until Phase 1 sets `AUTH_USER_MODEL = "accounts.User"`, never run `migrate` against the dev DB** — Django can't switch to a custom user model after the default auth migrations are applied. If it happens, reset with `docker compose down -v`.

## Commands (Docker Compose is the dev environment)

Postgres is required for development and tests: `select_for_update()` is a no-op on SQLite, so the locking/overselling tests are meaningless without Postgres. Do not switch tests to SQLite.

```bash
cp .env.example .env                                # first time only
docker compose up                                   # web :8000, db (host port 5434), redis
docker compose run --rm web pytest --cov            # full suite
docker compose run --rm web pytest common/tests/test_health.py::test_health_ok   # single test
docker compose run --rm web sh -c 'ruff check . && ruff format --check .'
.venv/bin/pre-commit run --all-files                # hooks are installed in .git/hooks
# (planned) manage.py migrate / seed_demo, pytest -k oversell --count=20 (pytest-repeat)
```

- Settings are split `config/settings/{base,dev,test,prod}.py`; env comes from `.env` (see `.env.example`). `manage.py` defaults to dev, `wsgi.py`/`asgi.py` to prod.
- pytest forces `--ds=config.settings.test` via `addopts` in `pyproject.toml`, because pytest-django otherwise lets a `DJANGO_SETTINGS_MODULE` env var win. Don't add that var to `.env`.
- `worker`/`beat` Compose services are behind the `celery` profile and are placeholders until Phase 5.
- New dependencies go in `requirements.txt` (runtime) or `requirements-dev.txt` (tests/lint), pinned; rebuild with `docker compose build`.

## Architecture (planned, from Phase 1 on)

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
