FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app \
    && mkdir /app/var && chown app:app /app/var
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY --chown=app:app apps ./apps
COPY --chown=app:app common ./common
COPY --chown=app:app config ./config
COPY --chown=app:app manage.py ./

FROM base AS development
COPY requirements-dev.txt pyproject.toml conftest.py ./
RUN pip install -r requirements-dev.txt
USER app
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS production
# collectstatic does not connect to the database. These are build-only placeholders,
# never runtime credentials; secrets are injected only when containers are started.
RUN DJANGO_SETTINGS_MODULE=config.settings.prod \
    SECRET_KEY=build-only-placeholder-not-a-runtime-signing-key-0000000000 \
    DATABASE_URL=postgres://build:build@localhost/build ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
