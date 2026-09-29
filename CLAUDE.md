# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Event Ticketing & Booking API (Django + DRF). Organizers create events and sell tickets; attendees browse, book, pay, and check in. The full phased roadmap is in `plan/plan_main.md`; each phase has a detailed sub-plan `plan/plan_<n>_<name>.md` (write one before starting a phase and add it to the index at the bottom of `plan_main.md`). Follow the phase order — finish and deploy before stretch features like Stripe.

Phases 0–5 are done (skeleton; models/admin/seed/ERD; JWT auth + CRUD; filtering/search/pagination; booking with row locking, mock payment, check-in; Celery ticket emails + order expiry). Deployment/CI (Phase 6) not yet. Items marked "(planned)" describe code that doesn't exist yet. Swagger UI: `/api/docs/`.

## Commands (Docker Compose is the dev environment)

Postgres is required for development and tests: `select_for_update()` is a no-op on SQLite, so the locking/overselling tests are meaningless without Postgres. Do not switch tests to SQLite.

```bash
cp .env.example .env                                # first time only
docker compose up                                   # web :8000, db (host port 5434), redis
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py seed_demo   # idempotent; demo users use demo-pass-123
docker compose run --rm web python manage.py makemigrations --check --dry-run   # drift check
docker compose run --rm web pytest --cov            # full suite; fails under 90% coverage (pyproject fail_under)
docker compose run --rm web pytest apps/events/tests/test_models.py::TestTicketType::test_database_blocks_overselling
docker compose run --rm web sh -c 'ruff check . && ruff format --check .'
.venv/bin/pre-commit run --all-files                # hooks are installed in .git/hooks
docker compose run --rm web pytest apps/orders/tests/test_concurrency.py --count=20   # race tests, repeated
```

- Settings are split `config/settings/{base,dev,test,prod}.py`; env comes from `.env` (see `.env.example`). `manage.py` defaults to dev, `wsgi.py`/`asgi.py` to prod.
- pytest forces `--ds=config.settings.test` via `addopts` in `pyproject.toml`, because pytest-django otherwise lets a `DJANGO_SETTINGS_MODULE` env var win. Don't add that var to `.env`.
- Compose also runs Celery `worker` + `beat` (schedule file in `/tmp`) and `mailpit` (dev inbox at http://localhost:8025; `EMAIL_URL=smtp://mailpit:1025`). The worker does **not** auto-reload: `docker compose restart worker beat` after changing task/service code.
- Email is configured by `EMAIL_URL` (django-environ `email_url`, default `consolemail://`) + `DEFAULT_FROM_EMAIL`; test settings force locmem.
- New dependencies go in `requirements.txt` (runtime) or `requirements-dev.txt` (tests/lint), pinned; rebuild with `docker compose build`.

## Architecture

- Apps live under `apps/` with short labels (`AppConfig.name = "apps.accounts"`, `label = "accounts"`), so model refs are `accounts.User`, `events.TicketType`. `common/` is a plain package (not an installed app) holding `TimeStampedModel` and test helpers. Schema diagram and the full constraint list: `docs/erd.md` — keep it in sync when models change.
  - `accounts`: `User` has no username; `email` is the login field and is always stored lowercased by `UserManager` (`get_by_natural_key` normalizes, so auth is case-insensitive). `role` is attendee/organizer; staff = `is_staff`. `Profile` is created by a `post_save` signal (`signals.py`, wired in `AccountsConfig.ready()`), which is why the admin hides the Profile inline on the add page.
  - `events`: `Venue`, `Category`, `Event`, `TicketType`. `TicketType.quantity_available` defaults to `quantity_total` on save/clean.
  - `orders`: `Order`, `Ticket` (random `code` from `generate_ticket_code`), booking services, order/ticket/check-in endpoints, Celery tasks (`tasks.py`, thin wrappers over services) and the ticket email (`emails.py` + `templates/orders/emails/`). `payments` (Stripe) is stretch only.
- Choice enums used inside `Meta.constraints` are module-level (`EventStatus`, `OrderStatus`, `Role`) and aliased on the model (`Event.Status`, `Order.Status`, `User.Role`), because a nested `Meta` can't see sibling nested classes.
- Deletion rules are deliberate: event→organizer/venue, order→user, and ticket→ticket_type are `PROTECT` (anything with sold tickets can't disappear); event→ticket types and order→tickets `CASCADE`.
- **All booking logic lives in `apps/orders/services.py`; views stay thin.** Anything that moves stock or changes an order's status must go through it and follow its locking rules (module docstring): `select_for_update()` inside `transaction.atomic()`, ticket types locked in **pk order**, stock changed only with `F()`. Services raise DRF exceptions directly (`ValidationError` 400, `common.exceptions.Conflict` 409, `SoldOut` 409, `NotFound`, `PermissionDenied`).
  - `place_order(user, event_id, [(ticket_type_id, qty), ...])` — locks the user row (serializes the per-user limit), then the tiers (`of=("self",)`), validates, decrements, creates a `pending` Order (`expires_at = now + settings.ORDER_TTL_MINUTES`) and bulk-creates Tickets. Maps an `IntegrityError` on the stock constraint to `SoldOut`.
  - `release_order(order, status)` — idempotent (no-op unless `pending`), restores stock; `cancel_order` and `expire_stale_orders` go through it.
  - `mark_order_paid(order)` — the single path to `paid` (mock `pay` endpoint now, Stripe webhook later). An overdue pending order is released as `expired` (committed) and then 409s. On success it queues `send_ticket_email` via `transaction.on_commit` (import of `tasks` is lazy there because `tasks` imports `services`).
  - `check_in(code, user)` — checks existence/permission/paid first (paid is terminal, so that's race-free), then one conditional `UPDATE ... WHERE pk = … AND checked_in_at IS NULL` on the ticket's **own columns only** (a join condition in the UPDATE wouldn't be re-checked by Postgres after a lock wait); 0 rows → 409 with the first scan's time.
- DB constraints are the last line of defence and must be kept — above all `ticket_type_quantity_available_non_negative`. They're named `IntegerField` + `CheckConstraint`s (not `PositiveIntegerField`) with `violation_error_message`s, so the admin's `full_clean()` shows them as form errors.
- Tickets are created at order time (pending) and are only valid for check-in once the order is `paid`.
  - `expire_stale_orders(limit=500)` — overdue pending ids, then re-lock each with `select_for_update(skip_locked=True)` (orders mid-payment are skipped, not waited on) and release as `expired`.
- Celery: app in `config/celery.py` (loaded by `config/__init__.py`), configured from `CELERY_*` settings; broker = `REDIS_URL`, results ignored. `CELERY_BEAT_SCHEDULE` in `base.py` runs `expire_stale_orders` every 60 s (no django-celery-beat). Tasks that talk to the outside world retry via `autoretry_for`; anything a task needs from a request must be enqueued with `transaction.on_commit`.

## API layer

- All viewsets register on the single `DefaultRouter` in `config/api_router.py` (mounted at `/api/`); auth views live in `apps/accounts/urls.py` at `/api/auth/`. Add new apps' viewsets to that router, not a per-app one.
- DRF defaults (`config/settings/base.py`): JWT-only auth, default permission `IsAuthenticated` — public endpoints must opt in (e.g. `*OrReadOnly`, or `AllowAny` + `authentication_classes = []` on register).
- `common.exceptions.exception_handler` turns `ProtectedError` into 409, so deleting PROTECT-referenced rows needs no per-view handling.
- Permissions (`common/permissions.py`): `IsOrganizerOrReadOnly`/`IsStaffOrReadOnly` gate writes by role; `IsOwnerOrReadOnly` reads `view.owner_field` (dotted paths OK, e.g. `"event.organizer"`) and compares FK ids. Owner fields are set in `perform_create` from `request.user`, never the payload. Object-level checks don't run on create, so ownership of a *parent* (ticket type → event) is checked in `perform_create` (403).
- Visibility is queryset scoping, not permissions: `Event.objects.visible_to(user)` (published for everyone, own events for organizers, all for staff) — hidden rows 404. Reuse it for anything hanging off events.
- Pagination (`common.pagination.StandardPagination`, 20/page, `?page_size` ≤ 100) and the filter backends (django-filter, `SearchFilter`, `OrderingFilter`) are global. Every list view must declare `ordering_fields` (otherwise any serializer field is orderable) and a default `ordering` ending in `id` so pages are stable. List responses are `{count, next, previous, results}`.
- FilterSets live in `apps/<app>/filters.py`. Filters over multi-valued relations that need several conditions on the *same* related row use an `Exists()` subquery (see `EventFilter.filter_queryset` price bounds), not chained filters — chaining can match different rows and duplicates results.
- `EventViewSet` annotates `min_price` for ordering; the response's `min_price` field is computed from prefetched ticket types instead, so it also works on create/update responses (no annotation there).
- DB constraints get mirrored as serializer validation (min values, date order) so clients get 400s, not 500s.
- `TicketType.quantity_available` is read-only in the API; editing `quantity_total` locks the row and preserves the sold count (`TicketTypeSerializer.update`).
- drf-spectacular schema must stay warning-free — `common/tests/test_api_docs.py` runs `spectacular --validate --fail-on-warn`.
- Orders/tickets are scoped to `request.user` in `get_queryset` (others → 404; staff list all orders but only the buyer may pay/cancel → 403). Querysets that depend on `request.user` must return `.none()` when `swagger_fake_view` is set, or schema generation fails the warning-free test.
- Ticket codes are hidden (`null`) in order responses until the order is paid; `CanCheckIn` gates the check-in view by role, and `check_in` checks the specific event's organizer.

## Testing conventions

- pytest + pytest-django + factory-boy. Tests live per app in `apps/<app>/tests/`; factories in `apps/<app>/tests/factories.py` (`UserFactory`/`OrganizerFactory`/`StaffFactory`, `EventFactory` (published, 7 days out), `TicketTypeFactory`, `OrderFactory`, `TicketFactory`; factory users' password is `DEFAULT_PASSWORD`). Admin smoke tests use pytest-django's `admin_client`. Root `conftest.py` provides `api_client`, `client_for(user)` (force-authenticated `APIClient`; `None` = anonymous) and `attendee`/`organizer`/`other_organizer`/`staff` fixtures; permission matrices parametrize fixture names and resolve them with `request.getfixturevalue`. Auth-flow tests use real JWTs via the login endpoint.
- To test a DB constraint, use `common.tests.helpers.assert_violates("<constraint_name>", lambda: ...)` — it wraps the statement in `transaction.atomic()` and asserts that specific constraint fired.
- Celery runs eagerly in tests (`CELERY_TASK_ALWAYS_EAGER` + propagate). Code that enqueues via `on_commit` only fires inside pytest-django's `django_capture_on_commit_callbacks(execute=True)` (or in `transaction=True` tests). Emails land in `django.core.mail.outbox`.
- Concurrency tests (`apps/orders/tests/test_concurrency.py`) use `@pytest.mark.django_db(transaction=True)` and `common.tests.helpers.run_concurrently(func, args)` (threads released by a `threading.Barrier`, each closing its DB connection; returns results or exceptions). Create all fixtures *before* the threads start — each thread has its own connection and sees only committed rows. Keep the negative-control test: it proves the harness really races.
- (planned) CI (GitHub Actions) runs ruff and `pytest --cov` (90% floor from pyproject) against Postgres and Redis service containers.
