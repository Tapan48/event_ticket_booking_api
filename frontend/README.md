# Ticket Booking frontend

Responsive React/TypeScript marketplace using Vite, Tailwind CSS, shadcn/ui primitives,
React Router, TanStack Query, React Hook Form and Zod. Fonts and category artwork
are bundled; the app does not require an external image service.

## Run locally

Start the root Docker Compose stack, migrate and seed the API (see root README).
With Node 24:

```sh
npm ci
npm run dev
```

The printed URL defaults to localhost:5173. `/api/`, `/admin/`, `/static/` and
`/health/` proxy to localhost:8000. Local emails appear in Mailpit on port 8025.

## Screens

- Public event discovery, search, filters, pagination, details and reservation.
- Registration, login and profile editing; session cookies with CSRF protection.
- Order history, hold countdown, mock payment, cancellation and ticket codes.
- Organizer-owned events/venues, draft/publish editing, tiers and ticket check-in.
- Swagger remains available at `/api/docs/` and from the footer.

Payments are a demonstration; no money is charged. Email is queued only after
successful payment. Holds last 15 minutes; the API/expiry worker remains authoritative.
Uploads, real payments/refunds and camera scanning are outside this release.

## Verify

```sh
npm run lint
npm run format:check
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests use the real local API and a Vite server on port 5174. They create
isolated test users/events and exercise booking, payment, cancellation, check-in,
session switching, mobile layout and Swagger. Use only a local/test database;
test emails use example.com and must go to Mailpit or the test email backend.
Never point these tests at production.

## Production

The root `deploy/caddy/Dockerfile` compiles the SPA in a Node build stage and copies
only its static output to Caddy. The ticket endpoint remains HTTPS port 8443.
Hashed assets are immutable; HTML is revalidated. No browser secrets or JWTs are
stored in localStorage. See `../docs/deployment.md` for release/rollback steps.
