# Phase 7 — Event marketplace frontend

Status: complete (2026-10-01, Asia/Kolkata). Approved scope: attendee and organizer UI, light marketplace
with colorful event cards, mobile support, and Swagger retained for development.

## Implementation

- React/TypeScript/Vite in `frontend/`, Tailwind and shadcn/ui primitives,
  React Router, TanStack Query, React Hook Form/Zod, Vitest and Playwright.
- Browse/search/filter upcoming events, event details and ticket quantities;
  register/login/profile; reserve, demo pay, cancel pending orders, order history,
  paid tickets and server-driven expiry countdown.
- Organizer-owned events/venues, draft/publish/edit forms, ticket tier management,
  and code-based check-in. Category artwork is bundled; uploads, Stripe, camera
  scanning, analytics and refunds are outside this release.
- Same-origin Django session auth with HttpOnly/Secure/SameSite cookies and CSRF
  protection (including login). Existing JWT endpoints remain compatible.
  Add authenticated `mine=true` filters for events and venues.
- Caddy serves the compiled SPA at `/` on the existing ticket host:8443, routing
  `/api/`, `/admin/`, `/static/` and `/health/` to Django. No RAG changes or new
  public ports. Existing TLS state and database volumes persist.

## Commits and acceptance

1. Browser authentication, ownership filters and backend regression tests.
2. Responsive attendee/organizer frontend and frontend tests.
3. Production packaging, CI, documentation and deployment verification.

Work directly on main as requested. Run backend tests (coverage >=90%), frontend
lint/typecheck/unit/browser tests, and secret scans before push. Verify frontend
deep links, Swagger/JWT compatibility, CSRF protections, two-organizer isolation,
booking/payment/email/cancellation/expiry/check-in, mobile layout and logout.
Build immutable ARM64 images locally, back up the ticket DB, deploy only the ticket
stack, verify CI and live behavior, and compare RAG container IDs/start times/ports.
Record actual release evidence before marking complete.

## Verified release

- Release images: `5db208f137c86265b51440473c4a01cda83ac6f1`; frontend and
  browser-auth commits are `98ab34c` and `6fd5c7f`. Pushed directly to main.
- [GitHub CI](https://github.com/Tapan48/event_ticket_booking_api/actions/runs/36786715059)
  passed: 247 backend tests, 100% measured backend coverage, 10 frontend unit tests,
  four real-API Playwright workflows, lint/format/typecheck, production builds and
  full-history Gitleaks. Staged/outgoing secret scans also passed.
- Independent review findings around account switching, stale responses, dialogs,
  sold-out quantities and date filters were fixed and re-reviewed. Browser tests
  cover complete booking/check-in, cross-tab logout, failed account hydration,
  mobile filter bounds and Swagger.
- Public HTTPS frontend and deep links, hashed assets, CSP, CSRF rejection,
  Secure/HttpOnly/SameSite session cookies, existing JWT API and Swagger verified.
- Live UI: organizer creates/publishes a tiered event; attendee logs in, reserves,
  demo-pays, views tickets, cancels a second hold; organizer checks in and receives
  duplicate rejection. No browser page errors during the complete flow.
- Matching HTML/text email delivered to owner's Gmail; owner confirmed receipt.
  Beat expired the controlled test order and restored inventory; the frontend
  showed expired status and no payment button. Only that test deadline was advanced;
  normal holds remain 15 minutes.
- Pre-release backup `ticketing-20260930T224215Z.dump` restored into a disposable
  database (33 migrations, nine events), copied offsite privately, SHA-256 matched.
  Daily backup timer remains active; no schema migrations were required.
- All ticket services running; five RAG container IDs/start times/health and host
  80/443 bindings unchanged, public RAG HTTPS returned 200. Ticket-only port 8443.

Live frontend: https://event-ticket-booking.duckdns.org:8443/
Developer Swagger: https://event-ticket-booking.duckdns.org:8443/api/docs/

## Follow-up: clean public URL (2026-10-08)

Use the existing RAG Caddy on public 443 to route the ticket domain through a
private proxy-only network. Preserve original RAG routes and keep 8443 as a
compatibility endpoint. Update trusted origins and deployment documentation;
verify both domains, certificates, redirects, login/CSRF, and RAG backend continuity.
