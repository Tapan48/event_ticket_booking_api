# Phase 6 — Oracle deployment, CI, and operations

Status: in progress. Implements [Phase 6 of the main plan](plan_main.md).

## Deployment decisions

- Use the existing ARM64 Oracle VM, in `/home/ubuntu/ticket-booking-api`, with Compose project `ticket-booking`.
- Public endpoint: `https://event-ticket-booking.duckdns.org:8443`; Swagger at `/api/docs/`.
- A dedicated Caddy container terminates TLS on 8443. DuckDNS DNS-01 validation obtains and renews certificates without binding host ports 80/443. Those ports, the RAG directory, its containers, networks, volumes, and configuration remain untouched.
- Separate PostgreSQL, Redis, web, worker, Beat, and proxy services. Only the proxy publishes a host port. Start with two Gunicorn workers and Celery concurrency 1; set memory/CPU limits and bounded logs.
- Runtime secrets are generated/transferred privately into a server-only `.env.prod`, never committed or included in images. Use Gmail SMTP with STARTTLS; normalize spaces in the saved App Password during private provisioning.
- Public demo seeding excludes staff users. Production refuses to seed the known staff password; administrative accounts are created separately.
- Daily PostgreSQL backups retain seven local copies. Copy a backup off the VM after deployment and document recurring offsite copying. Verify restoration into a disposable ticket-booking database, never the live or RAG database.

## Commit sequence (on main, as requested)

1. Document this sub-plan and exclude deployment secrets/artifacts.
2. Add production images, isolated Compose/TLS configuration, deployment and backup helpers, and safe public-demo seeding.
3. Add GitHub Actions for lint, formatting, PostgreSQL tests, coverage ≥90%, and secret scanning.
4. Complete deployment documentation and record verified release results.

## Validation and release

- Lint/format checks, full PostgreSQL test suite with ≥90% coverage, migration drift check, and production Django checks.
- Production Compose/image checks: no secrets copied, non-root app, private DB/broker, explicit production settings, one Beat scheduler, and only 8443 published.
- Gitleaks scan of history and staged changes before each push; review staged paths. Never log environment values or credential-bearing URLs.
- Build, migrate, seed non-staff demo users, start the isolated services, and verify HTTPS, Swagger/static files, auth, booking/payment/check-in, Gmail delivery, and real Beat expiry.
- Verify ticket-container restart recovery and database restore; retain the previous release image for rollback.
- Compare RAG container IDs/start times, health, and published ports before/after deployment. No host reboot or global Docker cleanup.
- Mark Phase 6 complete only after GitHub CI, live checks, backups, and RAG preservation are verified.
