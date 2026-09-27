# Event Ticketing & Booking API

A Django REST API where organizers create events and sell tickets, and attendees browse, book, pay, and check in — built so that **two people can never buy the last ticket** (row locking with `select_for_update()`, atomic transactions, `F()` expressions, and database constraints).

> **Status:** Phases 0–1 of the [roadmap](plan/plan_main.md) are complete: the project skeleton, the data model with its database constraints, the admin, and demo data. The REST API comes next. Features land phase by phase; see [`plan/`](plan/).

## Stack
Django 5.2 · Django REST Framework · PostgreSQL 16 · Redis 7 · Docker Compose · pytest · ruff

## Data model

Users (attendees and organizers) · Venues · Events (with categories) · Ticket types · Orders · Tickets.
See the **[ER diagram and constraint list](docs/erd.md)**.

The overselling backstop is a PostgreSQL `CHECK (quantity_available >= 0)` on ticket types. Even a decrement that slips past every application check is rejected by the database. This is proven in `apps/events/tests/test_models.py::TestTicketType::test_database_blocks_overselling`.

## Quickstart

```bash
cp .env.example .env
docker compose up --build                                   # web on :8000, Postgres on host port 5434, Redis
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py seed_demo      # demo users, venues, events, ticket types
docker compose run --rm web python manage.py createsuperuser
curl localhost:8000/health/                                 # {"status": "ok", "database": "ok"}
```

Admin is at http://localhost:8000/admin/; log in with the superuser you created. The demo users (`organizer@demo.dev`, `organizer2@demo.dev`, `attendee@demo.dev`, `staff@demo.dev`) share the password `demo-pass-123` and are for the API, which arrives in later phases.

## Development

```bash
docker compose run --rm web pytest --cov                # tests (always against Postgres)
docker compose run --rm web ruff check .                # lint
docker compose run --rm web ruff format .               # format
```

Git hooks (ruff + basic checks) run via [pre-commit](https://pre-commit.com):

```bash
python3 -m venv .venv && .venv/bin/pip install pre-commit && .venv/bin/pre-commit install
```

Celery `worker` / `beat` services are placeholders until Phase 5 (`docker compose --profile celery up`).
