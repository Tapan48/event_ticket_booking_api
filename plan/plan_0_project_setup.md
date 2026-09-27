# Phase 0: Project Setup (Ticket Booking API)

> **Status: ✅ done.** Deviations from the plan below, found during implementation:
> - The Postgres host port is `${POSTGRES_HOST_PORT:-5434}`, not 5433, because 5433 was already taken by another local Compose project.
> - `DJANGO_SETTINGS_MODULE` was removed from `.env.example`. pytest-django lets that env var override the ini setting, which made the tests run with *dev* settings. pytest now forces `--ds=config.settings.test` in `addopts`.
> - `WHITENOISE_AUTOREFRESH = True` in the test settings, so whitenoise doesn't warn about the missing `staticfiles/` (collectstatic never runs in tests).
> - `config/settings/*` is excluded from coverage because it loads before measurement starts.
> - There are 3 health tests, not 2 (added: POST returns 405). The pre-commit git hook is installed from a local `.venv`.

## Context
The full roadmap is in `plan/plan_main.md`. This plan covers **only Phase 0**: a runnable, tested and linted Django skeleton on Docker Compose (Postgres + Redis). Phase 1 (models) builds on it. No models and no custom User are created yet. You asked for proper local commits; you will push them yourself, so I won't add a remote and won't push.

Current state:
- The repo holds only `CLAUDE.md` and `plan/plan_main.md`, and it isn't a git repo yet.
- Git identity is set globally (Tapan48). No default branch is configured, so I'll use `git init -b main`.
- Docker 24 / Compose v2 are available.
- Postgres and Redis are also installed via Homebrew, so the Compose ports are chosen to avoid clashing with them.

## Critical constraint
**Do not run `migrate` against the dev database in Phase 0.** Phase 1 swaps in a custom `AUTH_USER_MODEL`, and Django can't switch to one after the default `auth_user` migrations have been applied. The health check doesn't need any tables. pytest creates a throwaway test DB, so tests are fine. If the dev database gets migrated by accident, reset it with `docker compose down -v`.

## Files to create

**Step 0: sub-plan file (first action after approval)**
- Save this Phase 0 plan as `plan/plan_0_project_setup.md`, next to the roadmap `plan/plan_main.md`.
- Add a short "Sub-plans" index to `plan/plan_main.md` that links to it.
- Later phases follow the same `plan/plan_<n>_<name>.md` pattern (e.g. `plan_1_models.md`).

**Dependencies and tooling**
- `requirements.txt` contains only what Phase 0 uses; later phases add their own packages in their own commits:
  - `Django>=5.2,<5.3`
  - `djangorestframework`
  - `django-environ`
  - `psycopg[binary]`
  - `gunicorn`
  - `whitenoise`
  - Versions are pinned to the current releases at install time.
- `requirements-dev.txt`: `-r requirements.txt`, plus pytest, pytest-django, pytest-cov, factory-boy, ruff and pre-commit.
- `pyproject.toml`:
  - ruff: target py313, line-length 100, rules `E,F,I,B,UP,DJ`, excluding migrations.
  - pytest: `DJANGO_SETTINGS_MODULE=config.settings.test`, `--reuse-db` off by default.
  - coverage: source `apps`, `common`, `config`; omit migrations.
- `.pre-commit-config.yaml`:
  - ruff (check `--fix` + format)
  - pre-commit-hooks: trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files
  - `rev`s pinned to the latest tags
- `.gitignore`: Python, `.venv`, `.env`, `staticfiles/`, coverage and IDE files.
- `.dockerignore`: `.git`, `.venv`, `__pycache__`, `.env`, coverage.

**Django project**
- `manage.py`: defaults to `config.settings.dev`.
- `config/settings/base.py`:
  - django-environ reads `.env`.
  - `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` and `DATABASE_URL` come from env, with `CONN_MAX_AGE=60` and a `REDIS_URL` placeholder for Phase 5.
  - `INSTALLED_APPS` holds Django's defaults plus `rest_framework`. `common` is a plain package, not an app, for now.
  - Middleware includes whitenoise.
  - UTC with `USE_TZ=True`, `STATIC_ROOT=staticfiles/` and `DEFAULT_AUTO_FIELD=BigAutoField`.
  - A marked comment reminds us to set `AUTH_USER_MODEL` in Phase 1.
- `config/settings/dev.py`: `DEBUG=True` and the console email backend.
- `config/settings/test.py`: MD5 password hasher (faster tests) and the locmem email backend.
- `config/settings/prod.py`:
  - `DEBUG=False` and `CSRF_TRUSTED_ORIGINS` from env
  - `SECURE_PROXY_SSL_HEADER`, secure cookies, HSTS and the whitenoise compressed manifest storage
  - Render-specific work waits for Phase 6.
- `config/urls.py`: `admin/` and `health/`. `config/wsgi.py` and `config/asgi.py` point at the prod settings by default. `config/__init__.py` is a placeholder for the Celery import in Phase 5.
- `apps/__init__.py`: empty package for the Phase 1 apps.
- `common/__init__.py` and `common/views.py`:
  - `health_check` returns `{"status": "ok", "database": "ok"}` with 200.
  - It checks the DB with `connection.ensure_connection()` and returns 503 with `"database": "unavailable"` on `OperationalError`.
  - GET only (`require_GET`), with no auth.
- `common/tests/test_health.py`: covers 200 with a working DB, and 503 when `ensure_connection` is patched to raise.

**Docker**
- `Dockerfile`:
  - `python:3.13-slim` with `PYTHONDONTWRITEBYTECODE` and `PYTHONUNBUFFERED`.
  - `ARG REQUIREMENTS=requirements-dev.txt`, and dependencies install before the source is copied so the layer cache works.
  - Workdir `/app`, `EXPOSE 8000`, and a default `gunicorn config.wsgi` command. Compose overrides it for dev.
  - The non-root user and collectstatic wait for Phase 6.
- `docker-compose.yml`:
  - `db`: `postgres:16-alpine`, a named volume, a `pg_isready` healthcheck and host port **5433** (avoids Homebrew's 5432).
  - `redis`: `redis:7-alpine` with a `redis-cli ping` healthcheck and no host port.
  - `web`: builds, `env_file: .env`, runs `python manage.py runserver 0.0.0.0:8000`, bind-mounts `.:/app`, maps port 8000, and waits for db and redis to be healthy.
  - `worker` and `beat`: same image, `profiles: ["celery"]` so plain `docker compose up` skips them until Phase 5, with a TODO for their commands.
- `.env.example`:
  - `DJANGO_SETTINGS_MODULE=config.settings.dev`, `SECRET_KEY`, `DEBUG=1`, `ALLOWED_HOSTS`
  - `POSTGRES_DB/USER/PASSWORD`, `DATABASE_URL=postgres://ticketing:ticketing@db:5432/ticketing`, `REDIS_URL=redis://redis:6379/0`
  - A local `.env` is copied from it and is gitignored.

**Docs**
- `README.md`: a short stub with the one-line pitch, a status note ("Phase 0 of plan/plan_main.md") and a quickstart (`cp .env.example .env`, `docker compose up`, `curl localhost:8000/health/`, run the tests). The full README comes in Phase 6.
- `CLAUDE.md`: switch the commands from "planned" to real and note the don't-migrate-before-Phase-1 rule.
- `plan/plan_main.md` and `plan/plan_0_project_setup.md`: mark Phase 0 as done.

## Commits (local only, conventional style, each ending with the Co-Authored-By line)
1. `docs: add project roadmap, Phase 0 sub-plan and CLAUDE.md`: `plan/plan_main.md`, `plan/plan_0_project_setup.md`, `CLAUDE.md`
2. `chore: add dependencies, lint and test tooling`: requirements, `pyproject.toml`, `.pre-commit-config.yaml`, `.gitignore`
3. `feat: scaffold Django project with split settings`: `manage.py`, `config/`, `apps/`, `common/__init__.py`, `.env.example`
4. `feat: add health check endpoint with tests`: `common/views.py`, `common/tests/`, the URL
5. `build: add Dockerfile and Docker Compose stack`: `Dockerfile`, `.dockerignore`, `docker-compose.yml`
6. `docs: add README quickstart and mark Phase 0 done`: `README.md`, `CLAUDE.md`, `plan/plan_main.md`, `plan/plan_0_project_setup.md`

No remote and no push.

## Verification
1. `cp .env.example .env && docker compose build && docker compose up -d`
2. `curl -i localhost:8000/health/` returns `200 {"status":"ok","database":"ok"}`. With `docker compose stop db` it returns 503; start the db again afterwards.
3. `docker compose run --rm web pytest -v`: the 2 health tests pass.
4. `docker compose run --rm web ruff check . && docker compose run --rm web ruff format --check .`
5. `docker compose run --rm web python manage.py check --deploy --settings=config.settings.prod` (with dummy env) reports no critical errors.
6. Local `pre-commit run --all-files`: tried in a local `.venv` if pre-commit installs cleanly on Python 3.14, otherwise skipped with a note.
7. `docker compose ps` shows db and redis healthy, and worker and beat not started.
8. `git log --oneline` shows the 6 commits and `git status` is clean.
