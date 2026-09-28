# Phase 2: Auth + CRUD + Permissions

> **Status: ✅ done.** Deviations and notes:
> - **`CanCheckIn` moves to Phase 4**, where check-in is built. `IsEventOrganizer` was replaced by `IsOwnerOrReadOnly` with a dotted `owner_field`.
> - **Waiting for Phase 3:** the `?event=` filter on ticket types and list pagination, both done with django-filter and the global paginator. Lists are unpaginated until then.
> - **Cancelled events are hidden from the public**, like drafts, and stay visible to their organizer and staff.
> - **Dev `SECRET_KEY` lengthened** in `.env.example`. At 22 bytes it triggered PyJWT's insecure HS256 key warning; the minimum is 32. **Update your local `.env` the same way.**
> - Result: 128 tests with 100% coverage, and a warning-free OpenAPI schema. The curl run (register → login → venue/event/ticket type → 403/404 checks → refresh rotation) passed against the dev server.

## Context
This is Phase 2 of [plan_main.md](plan_main.md). It exposes the Phase 1 models through a JWT-secured REST API with role- and ownership-based permissions. Filtering, search and pagination are Phase 3, and booking is Phase 4.

## Design decisions
- **Dependencies:** `djangorestframework-simplejwt` (with the `token_blacklist` app) and `drf-spectacular`.
- **DRF defaults:**
  - JWT authentication only.
  - Default permission `IsAuthenticated` (secure by default); each view opts into public reads.
  - JSON as the test request format.
  - A custom exception handler turns `ProtectedError` into **409 Conflict**. Examples: deleting a venue that has events, or an event with sold tickets.
- **Auth** (`/api/auth/`):
  - `register/` validates the password with Django's validators and lets the user pick attendee or organizer; `is_staff` can never be set this way. Email uniqueness is checked *after* lowercasing, since DRF's `UniqueValidator` would miss `JANE@x.com` vs `jane@x.com`.
  - `login/` and `refresh/` are simplejwt views with rotation and blacklist-after-rotation.
  - `logout/` is simplejwt's `TokenBlacklistView`.
  - `me/` supports GET and PATCH, with a nested writable profile. Email, role and staff flag are read-only.
- **One central router** in `config/api_router.py`, so later apps (orders) register there without clashing API-root views.
- **Permissions** (`common/permissions.py`):
  - `IsOrganizerOrReadOnly`: writes need an organizer or staff account.
  - `IsStaffOrReadOnly`: for categories.
  - `IsOwnerOrReadOnly`: object writes go to staff or the owner named by `view.owner_field`, which may be dotted (e.g. `"event.organizer"`). This replaces a separate `IsEventOrganizer`.
  - `CanCheckIn` moves to Phase 4, where it's used.
- **Visibility:** the public sees published events (and their ticket types). Organizers also see their own drafts and cancelled events; staff see everything. Hidden objects return 404.
- **Events:**
  - `organizer` always comes from `request.user`.
  - Venue is written as `venue_id` and read as a nested object; categories are written and read as slugs.
  - Ticket types are nested read-only.
  - Validation: `ends_at > starts_at`, new events can't start in the past, and `max_tickets_per_user >= 1`. These return 400s before the DB constraints could 500.
  - Lists use `select_related`/`prefetch_related`, and a test proves the query count stays constant.
- **Ticket types:**
  - Only the event's organizer (or staff) can create one, otherwise 403. `event` can't change after creation.
  - `quantity_available` is **read-only**: stock changes only through bookings.
  - Editing `quantity_total` locks the row (`select_for_update`), keeps the sold count, and rejects a total below the number sold. This follows the same locking pattern Phase 4 uses.
- **Docs:** `/api/schema/` and `/api/docs/` (Swagger UI) are generated with no warnings (`spectacular --validate --fail-on-warn`).

## Commits (local only; you push)
1. `docs: add Phase 2 sub-plan`
2. `feat(api): configure DRF, JWT auth and OpenAPI docs`: requirements, settings, schema/docs URLs, the 409 exception handler
3. `feat(accounts): add register, login, refresh, logout and me endpoints`: plus the root `conftest.py` fixtures and API tests
4. `feat(common): add role and ownership permissions`: plus unit tests
5. `feat(events): add venue, category, event and ticket type endpoints`: plus the permission-matrix, validation and query-count tests
6. `docs: mark Phase 2 done`: README, CLAUDE.md, plan status

## Verification
- `pytest --cov` passes with 100% coverage, and ruff and pre-commit pass.
- `manage.py spectacular --validate --fail-on-warn` is clean.
- Manual curl run: register → login → create venue/event/ticket type as an organizer, then attendee writes get 403, another organizer's edit gets 403, refresh rotation works, and logout blacklists the refresh token.
