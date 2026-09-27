# Phase 1: Models, Migrations, Admin, ERD

> **Status: in progress**

## Context
This is Phase 1 of [plan_main.md](plan_main.md). It builds the whole data model, with the database constraints that later phases rely on, before any API code exists. Phase 4's overselling protection depends on the `quantity_available >= 0` CheckConstraint defined here. The custom User model has to land **before the first `migrate`**, and Phase 0 left the dev database unmigrated for this reason.

## Design decisions
- **`common.TimeStampedModel`**: an abstract model with `created_at`/`updated_at`. `common` stays a plain package; abstract models don't need an installed app.
- **Apps** live under `apps/` with labels `accounts`, `events`, `orders` (e.g. `AppConfig.name = "apps.accounts"`), so `AUTH_USER_MODEL = "accounts.User"`.
- **User**:
  - `AbstractUser` with `username` removed; `email` is unique and is `USERNAME_FIELD`.
  - A custom `UserManager` lowercases emails.
  - `role` is `attendee | organizer` (default attendee), and staff use `is_staff`. `is_organizer` is a property.
- **Profile** is OneToOne with a `profile` related name, holding phone, bio and city. A `post_save` signal wired in `AccountsConfig.ready()` creates it.
- **Constraints use `IntegerField` + named `CheckConstraint`s** rather than `PositiveIntegerField`. The names show up in errors and interviews, and `Model.full_clean()` (and so the admin) reports them as form errors with a `violation_error_message`.
- **TicketType**: `quantity_available` defaults to `quantity_total` on first save. Constraints:
  - `available >= 0` (anti-oversell)
  - `available <= total`
  - `total >= 0`, `price >= 0`
  - unique `(event, name)`
- **Event**:
  - `ends_at > starts_at`, `max_tickets_per_user >= 1`
  - Index on `(status, starts_at)` for the "published upcoming events" listing
  - `organizer` and `venue` use `PROTECT`, so sold events can't vanish with a user or venue
- **Order**:
  - `user` uses `PROTECT`; `status` is `pending | paid | cancelled | expired`.
  - Constraints: `total_amount >= 0`, and `status = paid` requires `paid_at` to be set.
  - Index on `(status, expires_at)` for the Phase 5 expiry sweep.
  - `stripe_session_id` waits for Phase 7 (YAGNI), with its own migration.
- **Ticket**:
  - `code = secrets.token_urlsafe(12)` (16 chars, 96 bits), not editable.
  - `UniqueConstraint(code)`, `price_paid >= 0`.
  - `ticket_type` uses `PROTECT`, `checked_in_by` uses `SET_NULL`.
- **ERD** is a Mermaid diagram in `docs/erd.md` instead of a PNG from `graph_models`. GitHub renders Mermaid natively, and this avoids adding graphviz/pydot to the image.
- **Tests** live per app (`apps/<app>/tests/`), with factory-boy factories in `apps/<app>/tests/factories.py`. Tests that expect an `IntegrityError` wrap the failing statement in `transaction.atomic()`.

## Steps and commits (local only; you push)
1. `docs: add Phase 1 sub-plan`
2. `feat(accounts): add email-based custom User with roles and Profile`: `common/models.py`, the accounts app, `AUTH_USER_MODEL`, the migration, admin, factories and tests.
3. `feat(events): add venues, categories, events and ticket types`: models + constraints, the migration, admin with a TicketType inline, and constraint tests.
4. `feat(orders): add orders and tickets with unique ticket codes`: models + constraints, the migration, admin with a Ticket inline, and tests.
5. `feat: add seed_demo management command`: idempotent (`get_or_create`) demo organizers, attendee, venues, categories, and past/upcoming/draft events with ticket types.
6. `docs: add ERD and mark Phase 1 done`: `docs/erd.md`, README link, CLAUDE.md update, plan status.

## Verification
- `docker compose run --rm web python manage.py makemigrations --check --dry-run` reports no changes.
- `migrate` on the dev DB succeeds, and `createsuperuser` works with email only.
- `seed_demo` run twice gives no duplicates.
- `pytest --cov`: all tests green, including every constraint test and a simulated oversell (`update(quantity_available=F(...) - n)` raises `IntegrityError`).
- `ruff check` and the pre-commit hooks pass on each commit.
- The admin pages load at `/admin/` (checked with curl after logging in).
