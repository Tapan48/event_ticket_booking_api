# Event Ticketing & Booking API

A Django REST API where organizers create events and sell tickets, and attendees browse, book, pay, and check in — built so that **two people can never buy the last ticket** (row locking with `select_for_update()`, atomic transactions, `F()` expressions, and database constraints).

> **Status:** Phase 0 (project setup) of the [roadmap](plan/plan_main.md) is complete. Features land phase by phase; see [`plan/`](plan/).

## Stack
Django 5.2 · Django REST Framework · PostgreSQL 16 · Redis 7 · Docker Compose · pytest · ruff

## Quickstart

```bash
cp .env.example .env
docker compose up --build        # web on :8000, Postgres on host port 5434, Redis
curl localhost:8000/health/      # {"status": "ok", "database": "ok"}
```

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
