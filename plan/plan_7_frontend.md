# Phase 7 — Event marketplace frontend

Status: in progress. Approved scope: attendee and organizer UI, light marketplace
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
