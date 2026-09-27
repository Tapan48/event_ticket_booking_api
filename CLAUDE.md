# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Event Ticketing & Booking API (Django + DRF). Organizers create events and sell tickets; attendees browse, book, pay, and check in. The full phased roadmap is in `plan/plan_main.md`; each phase has a detailed sub-plan `plan/plan_<n>_<name>.md` (write one before starting a phase and add it to the index at the bottom of `plan_main.md`). Follow the phase order — finish and deploy before stretch features like Stripe.

Phases 0 (skeleton) and 1 (models, admin, seed data, ERD) are done; there are no API endpoints yet. Items marked "(planned)" describe code that doesn't exist yet.

## Commands (Docker Compose is the dev environment)

Postgres is required for development and tests: `select_for_update()` is a no-op on SQLite, so the locking/overselling tests are meaningless without Postgres. Do not switch tests to SQLite.

```bash
cp .env.example .env                                # first time only
docker compose up                                   # web :8000, db (host port 5434), redis
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py seed_demo   # idempotent; demo users use demo-pass-123
docker compose run --rm web python manage.py makemigrations --check --dry-run   # drift check
docker compose run --rm web pytest --cov            # full suite
docker compose run --rm web pytest apps/events/tests/test_models.py::TestTicketType::test_database_blocks_overselling
docker compose run --rm web sh -c 'ruff check . && ruff format --check .'
.venv/bin/pre-commit run --all-files                # hooks are installed in .git/hooks
# (planned) pytest -k oversell --count=20 (pytest-repeat)
```

- Settings are split `config/settings/{base,dev,test,prod}.py`; env comes from `.env` (see `.env.example`). `manage.py` defaults to dev, `wsgi.py`/`asgi.py` to prod.
- pytest forces `--ds=config.settings.test` via `addopts` in `pyproject.toml`, because pytest-django otherwise lets a `DJANGO_SETTINGS_MODULE` env var win. Don't add that var to `.env`.
- `worker`/`beat` Compose services are behind the `celery` profile and are placeholders until Phase 5.
- New dependencies go in `requirements.txt` (runtime) or `requirements-dev.txt` (tests/lint), pinned; rebuild with `docker compose build`.

## Architecture

- Apps live under `apps/` with short labels (`AppConfig.name = "apps.accounts"`, `label = "accounts"`), so model refs are `accounts.User`, `events.TicketType`. `common/` is a plain package (not an installed app) holding `TimeStampedModel` and test helpers. Schema diagram and the full constraint list: `docs/erd.md` — keep it in sync when models change.
  - `accounts`: `User` has no username; `email` is the login field and is always stored lowercased by `UserManager` (`get_by_natural_key` normalizes, so auth is case-insensitive). `role` is attendee/organizer; staff = `is_staff`. `Profile` is created by a `post_save` signal (`signals.py`, wired in `AccountsConfig.ready()`), which is why the admin hides the Profile inline on the add page.
  - `events`: `Venue`, `Category`, `Event`, `TicketType`. `TicketType.quantity_available` defaults to `quantity_total` on save/clean.
  - `orders`: `Order`, `Ticket` (random `code` from `generate_ticket_code`). (planned) booking services, Celery tasks, check-in. `payments` (Stripe) is stretch only.
- Choice enums used inside `Meta.constraints` are module-level (`EventStatus`, `OrderStatus`, `Role`) and aliased on the model (`Event.Status`, `Order.Status`, `User.Role`), because a nested `Meta` can't see sibling nested classes.
- Deletion rules are deliberate: event→organizer/venue, order→user, and ticket→ticket_type are `PROTECT` (anything with sold tickets can't disappear); event→ticket types and order→tickets `CASCADE`.
- (planned) **Business logic lives in `apps/orders/services.py`; views stay thin.** Key functions:
  - `place_order` — inside `transaction.atomic()`: lock the user row (serializes the per-user ticket limit), lock ticket types with `select_for_update().order_by("pk")` (consistent lock order prevents deadlocks), validate, decrement `quantity_available` with `F()`, create a `pending` Order with `expires_at` and its Tickets.
  - `release_order(order, status)` — used by both cancel and expiry; only acts on `pending` orders (idempotent) and restores stock with `F()`.
  - `mark_order_paid(order)` — the single path to `paid`, used by the mock `pay` endpoint now and the Stripe webhook later; sends the ticket email via `transaction.on_commit`.
  - Check-in is one conditional `UPDATE ... WHERE checked_in_at IS NULL AND order paid`; zero rows updated → diagnose as 404/409/400.
- DB constraints are the last line of defence and must be kept — above all `ticket_type_quantity_available_non_negative`. They're named `IntegerField` + `CheckConstraint`s (not `PositiveIntegerField`) with `violation_error_message`s, so the admin's `full_clean()` shows them as form errors. (planned) An `IntegrityError` from the quantity constraint maps to a 409 "sold out".
- Tickets are created at order time (pending) and are only valid for check-in once the order is `paid`.
- (planned) Celery beat runs `expire_stale_orders` every 60s, selecting with `select_for_update(skip_locked=True)`; the beat schedule is in settings (no django-celery-beat).
- (planned) Permissions: organizers edit only their own events/ticket types (ownership via `obj.event.organizer` for ticket types); attendees see only their own orders (other users' orders → 404 via queryset scoping, not 403); check-in is staff or that event's organizer. Owner fields are set from `request.user` in `perform_create`, never from the payload.

## Testing conventions

- pytest + pytest-django + factory-boy. Tests live per app in `apps/<app>/tests/`; factories in `apps/<app>/tests/factories.py` (`UserFactory`/`OrganizerFactory`/`StaffFactory`, `EventFactory` (published, 7 days out), `TicketTypeFactory`, `OrderFactory`, `TicketFactory`; factory users' password is `DEFAULT_PASSWORD`). Admin smoke tests use pytest-django's `admin_client`. (planned) API fixtures (`api_client`, `attendee`, `organizer`, `staff`) in a root `conftest.py`.
- To test a DB constraint, use `common.tests.helpers.assert_violates("<constraint_name>", lambda: ...)` — it wraps the statement in `transaction.atomic()` and asserts that specific constraint fired.
- (planned) Concurrency tests use `@pytest.mark.django_db(transaction=True)`, threads synchronized with `threading.Barrier`, and must close each thread's DB connection.
- (planned) CI (GitHub Actions) runs ruff and `pytest --cov --cov-fail-under=85` against Postgres and Redis service containers.
