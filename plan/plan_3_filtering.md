# Phase 3: Filtering, Search, Pagination

> **Status: in progress**

## Context
This is Phase 3 of [plan_main.md](plan_main.md). It makes the Phase 2 list endpoints usable for browsing: attendees filter events by city, date range, category and price, search by title, and page through results. It also picks up the `?event=` ticket-type filter deferred from Phase 2.

## Design decisions
- **Dependency:** `django-filter`.
- **Global DRF defaults:**
  - `DjangoFilterBackend`, `SearchFilter` and `OrderingFilter` as filter backends.
  - `common.pagination.StandardPagination`: page size 20, and `?page_size=` up to 100.
  - Each view declares explicit `ordering_fields` and a deterministic default ordering with an `id` tiebreak, so pages never overlap.
- **`EventFilter`** (`apps/events/filters.py`):
  - `city`: `venue__city__iexact`
  - `category`: category slug
  - `status`: lets organizers list their drafts
  - `upcoming=true`: `starts_at > now`
  - `starts_after` (`>=`) and `starts_before` (`<`): ISO date or datetime, index-friendly bounds on `starts_at`
  - `min_price` / `max_price`: an `Exists()` subquery over ticket types, so **both bounds apply to the same ticket type**. Chaining two filters on a multi-valued relation could match different tiers, and the subquery also avoids a `.distinct()` join.
- **Event search and ordering:**
  - Search covers `title`, `description` and `venue__name`.
  - Ordering covers `starts_at`, `created_at` and `min_price`, which is annotated as `Min(ticket_types__price)`.
- **`min_price` in event responses** ("tickets from ₹X") is computed from the already-prefetched ticket types, so it costs no extra query and also works on create/update responses, which have no annotation.
- **Other lists:**
  - Venues filter by `city` and search name, address and city.
  - Categories search by name.
  - Ticket types filter by `event` and order by price.
- **Coverage floor:** `fail_under = 90` in `pyproject.toml`, so `pytest --cov` (and CI later) fails if coverage drops.

## Commits (local only; you push)
1. `docs: add Phase 3 sub-plan`
2. `feat(api): add global pagination and filter backends`: plus pagination tests, and the existing list tests updated to the paginated shape
3. `feat(events): filter, search and order events`: plus the `min_price` field and filter/search/order tests
4. `feat(events): filter and search venues, categories and ticket types`
5. `chore: enforce a 90% coverage floor`
6. `docs: mark Phase 3 done`

## Verification
- `pytest --cov` passes; the schema is still warning-free; ruff and pre-commit pass.
- A curl run against the seeded dev DB: `?city=`, `?category=`, a date range, a price range, `?search=`, `?ordering=-min_price`, and `?page=2&page_size=2`.
