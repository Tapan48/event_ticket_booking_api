# Phase 5: Celery + Redis (Emails and Order Expiry)

> **Status: in progress**

## Context
This is Phase 5 of [plan_main.md](plan_main.md). Phase 4 left two gaps:
- paid orders don't email their tickets;
- an unpaid order only expires if someone tries to pay it late, so abandoned orders hold stock forever.

This phase closes both with Celery workers on a Redis broker.

## Design decisions
- **Dependency:** `celery[redis]`.
- **Celery app:**
  - The app lives in `config/celery.py` and is loaded from `config/__init__.py`, so `@shared_task` binds to it.
  - Settings use the `CELERY_` namespace. The broker is `REDIS_URL`; no result backend is needed because nothing reads task results.
  - The test settings run tasks eagerly (`CELERY_TASK_ALWAYS_EAGER`, with propagation on).
- **`send_ticket_email(order_id)`:**
  - Sends an HTML + plain-text email (Django templates) listing each ticket's code, tier and the event details.
  - Retries up to 5 times with exponential backoff and jitter on `OSError`, which covers `SMTPException` and connection errors.
  - Does nothing unless the order is paid.
  - `mark_order_paid` queues it with `transaction.on_commit`, so a rolled-back payment never emails and the worker never reads uncommitted rows.
- **`expire_stale_orders()`:** runs from beat every 60s (the schedule lives in settings).
  - The service looks up overdue `pending` order ids, then re-locks each one with `select_for_update(skip_locked=True)`. An order that's locked by a payment in progress is skipped, and the next sweep (or the payment itself) handles it.
  - Each expiry reuses the idempotent `release_order`, so racing a payment can't restore stock twice.
- **Email config:**
  - `EMAIL_URL` (django-environ) and `DEFAULT_FROM_EMAIL` come from env.
  - Dev sends to **Mailpit**, a Compose service with a web inbox at http://localhost:8025. Tests use locmem.
- **Compose:**
  - `worker` (`celery -A config worker`) and `beat` (`celery -A config beat`, schedule file in `/tmp`) come out of the `celery` profile, so a plain `docker compose up` starts them.
  - A `mailpit` service is added.

## Commits (local only; you push)
1. `docs: add Phase 5 sub-plan`
2. `feat: add Celery app with Redis broker`
3. `feat(orders): email tickets after payment`: templates, task with retries, `on_commit` hook, Mailpit, tests
4. `feat(orders): expire unpaid orders automatically`: service, task, beat schedule, tests including a pay-vs-expire race
5. `docs: mark Phase 5 done`

## Verification
- `pytest --cov` passes; the concurrency tests pass `--count=20`; the schema is warning-free; ruff and pre-commit pass.
- Live in Compose:
  - pay an order, and the email shows up in Mailpit (its API at `localhost:8025/api/v1/messages`);
  - backdate a pending order's `expires_at`, and within 60s the worker log shows it expired and its stock is restored.
