# Phase 4: Booking Flow with Locking ★

> **Status: ✅ done.** Notes:
> - **Negative control confirmed:** the naive unlocked version oversells under the same harness, so the concurrency tests aren't vacuous. All 7 race tests pass 20/20 repeated runs.
> - **Extra race tests:** multi-seat orders never split the last seats, and orders naming tiers in opposite order don't deadlock.
> - **Swagger fix:** drf-spectacular calls `get_queryset()` with no real user, so the user-scoped order and ticket views return `.none()` under `swagger_fake_view`. The warning-free schema test caught this.
> - **Extras:** the 409 check-in response uses DRF's datetime format; order and ticket list query counts are tested constant; check-in responses include the attendee's email.
> - Result: 215 tests with 100% coverage. The curl run on the dev server passed: book → codes hidden → pay → attendee scan 403 → organizer scan 200 → rescan 409; 6 of 5 Front Row → 409; book 3 then cancel → stock back to 5.

## Context
This is Phase 4 of [plan_main.md](plan_main.md) and the project's main talking point: **two people can never buy the last ticket**. Attendees place orders, which reserve stock for 15 minutes, then pay (mocked) or cancel. Organizers and staff check tickets in by code, and a used ticket is rejected. Celery expiry and email arrive in Phase 5.

## Design decisions
- **`apps/orders/services.py` holds all booking logic; views stay thin.**
  - **`place_order(user, event_id, items)`** runs in one `transaction.atomic()`:
    1. `select_for_update()` on the user row, so one user's concurrent bookings queue up and the per-user limit can't be raced.
    2. `select_for_update(of=("self",))` on the requested ticket types, **ordered by pk**. A fixed lock order means two orders for overlapping tiers can't deadlock.
    3. Validate:
       - the event is published and hasn't started;
       - every tier belongs to the event (duplicate items are merged);
       - the user's pending + paid tickets for the event plus this request stay within `max_tickets_per_user`;
       - enough stock is left (**409 Sold out**).
    4. Decrement with `F("quantity_available") - n`, create a `pending` Order (`expires_at = now + ORDER_TTL_MINUTES`), and `bulk_create` the Tickets with a price snapshot.
    - An `IntegrityError` from `ticket_type_quantity_available_non_negative` (the Phase 1 backstop) is also mapped to 409.
  - **`release_order(order, status)`** locks the order and only acts on `pending` orders, so it's idempotent. It restores stock with `F()`. Cancel uses it now; Phase 5 expiry reuses it.
  - **`mark_order_paid(order)`** locks the order. A non-pending order gets 409. A pending order past `expires_at` is released as `expired` (committed) and then gets 409. Otherwise it becomes `paid` with `paid_at`. This is the single path to "paid", which the Stripe webhook will reuse; Phase 5 adds the ticket email here via `on_commit`.
  - **`check_in(code, user)`**:
    - unknown code → 404; the caller isn't staff or that event's organizer → 403; order not paid → 400;
    - then **one conditional `UPDATE ... WHERE id = … AND checked_in_at IS NULL`**, using only the ticket's own columns so Postgres re-checks the condition after a row-lock wait;
    - 0 rows updated means someone already checked it in → 409 with `checked_in_at`.
- **Errors:** `common.exceptions.Conflict` (409) for sold out and state conflicts; `ValidationError` (400) for bad input.
- **Endpoints:**
  - `POST /api/orders/` with `{event, items: [{ticket_type, quantity}]}`
  - `GET /api/orders/` and `GET /api/orders/{id}/`: your own orders, or all for staff; anyone else's order is 404.
  - `POST /api/orders/{id}/pay/` (mock) and `POST /api/orders/{id}/cancel/`: owner only.
  - `GET /api/tickets/`: your tickets from paid orders.
  - `POST /api/checkin/` with `{code}`: staff or the event's organizer (`CanCheckIn`).
  - Ticket codes are hidden (`null`) in order responses until the order is paid.
- **Tests:**
  - service unit tests, and API tests for every status code;
  - **concurrency tests** (`transaction=True`, threads released together by a `threading.Barrier`, each closing its DB connection):
    - 20 buyers for 1 ticket → exactly 1 sale;
    - 30 buyers for 10 → exactly 10;
    - one user racing the per-user limit;
    - 10 simultaneous scans of one ticket → exactly 1 check-in;
    - **a negative control**: a naive read-check-write booking *without* locks oversells under the same harness, proving the harness really produces races.
  - `pytest-repeat` added so the suite can be run with `--count=20`.

## Commits (local only; you push)
1. `docs: add Phase 4 sub-plan`
2. `feat(orders): add booking services with row locking`: `place_order`, `release_order`, `mark_order_paid`, `Conflict`, `ORDER_TTL_MINUTES`, plus service tests
3. `test(orders): prove bookings can't oversell under concurrency`: `pytest-repeat` plus the concurrency tests and the negative control
4. `feat(orders): add order, payment and ticket endpoints`
5. `feat(orders): add race-free ticket check-in`: service, `CanCheckIn`, endpoint, tests including the double-scan race
6. `docs: explain overselling protection and mark Phase 4 done`

## Verification
- `pytest --cov` passes (floor 90%); `pytest apps/orders/tests/test_concurrency.py --count=20` passes 20/20.
- The schema is warning-free; ruff and pre-commit pass.
- A curl run on the dev server: book → pay → check in → check in again (409); sell out a 5-ticket tier (409); cancel restores stock.
