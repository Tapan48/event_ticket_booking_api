# Entity-Relationship Diagram

```mermaid
erDiagram
    USER ||--|| PROFILE : has
    USER |o--o{ VENUE : "created"
    USER ||--o{ EVENT : organizes
    VENUE ||--o{ EVENT : hosts
    EVENT }o--o{ CATEGORY : "tagged with"
    EVENT ||--o{ TICKET_TYPE : offers
    USER ||--o{ ORDER : places
    ORDER ||--o{ TICKET : contains
    TICKET_TYPE ||--o{ TICKET : "sold as"
    USER |o--o{ TICKET : "checked in"

    USER {
        bigint id PK
        string email UK "lowercased, login field"
        string role "attendee | organizer"
        bool is_staff "staff can check people in"
    }
    PROFILE {
        bigint id PK
        bigint user_id FK,UK
        string phone
        text bio
        string city
    }
    VENUE {
        bigint id PK
        string name
        string address
        string city "indexed"
        int capacity "> 0"
        bigint created_by_id FK "nullable"
    }
    CATEGORY {
        bigint id PK
        string name UK
        string slug UK
    }
    EVENT {
        bigint id PK
        bigint organizer_id FK "PROTECT"
        bigint venue_id FK "PROTECT"
        string title
        datetime starts_at "indexed"
        datetime ends_at "> starts_at"
        string status "draft | published | cancelled"
        smallint max_tickets_per_user ">= 1"
    }
    TICKET_TYPE {
        bigint id PK
        bigint event_id FK "CASCADE"
        string name "unique per event"
        decimal price ">= 0"
        int quantity_total
        int quantity_available "0 <= available <= total"
    }
    ORDER {
        bigint id PK
        bigint user_id FK "PROTECT"
        string status "pending | paid | cancelled | expired"
        decimal total_amount ">= 0"
        datetime expires_at
        datetime paid_at "required when paid"
    }
    TICKET {
        bigint id PK
        bigint order_id FK "CASCADE"
        bigint ticket_type_id FK "PROTECT"
        string code UK "16-char random token"
        decimal price_paid ">= 0"
        datetime checked_in_at "nullable"
        bigint checked_in_by_id FK "nullable"
    }
```

Every model except `Category` also has `created_at` / `updated_at` from `common.models.TimeStampedModel`. The event ↔ category link is a Django many-to-many join table (`events_event_categories`).

## Database constraints

These are enforced by PostgreSQL. They hold even if application code has a bug or two requests race each other.

| Constraint | Table | Guarantees |
|---|---|---|
| `ticket_type_quantity_available_non_negative` | ticket type | **Stock can never go below zero, so no overselling.** This is the backstop behind the Phase 4 row locking. |
| `ticket_type_available_lte_total` | ticket type | Stock never exceeds what was issued. Combined with the constraint above, the total is ≥ 0 too. |
| `unique_ticket_type_name_per_event` | ticket type | One "VIP" tier per event. |
| `ticket_type_price_non_negative` | ticket type | No negative prices. |
| `unique_ticket_code` | ticket | Every scannable ticket code is unique. |
| `ticket_price_paid_non_negative` | ticket | No negative ticket prices. |
| `ticket_checked_in_by_requires_time` | ticket | A check-in always records when it happened. |
| `order_paid_requires_paid_at` | order | A paid order always records when it was paid. |
| `order_total_non_negative`, `order_status_valid` | order | Valid totals and statuses. |
| `event_ends_after_starts` | event | Events end after they start. |
| `event_max_tickets_per_user_positive`, `event_status_valid` | event | Sane per-user limit and valid status. |
| `venue_capacity_positive` | venue | Venues hold at least one person. |
| `user_role_valid` | user | Role is attendee or organizer. |

## Indexes worth knowing

- `event_status_starts_idx (status, starts_at)` serves the public "published upcoming events" listing.
- `order_status_expires_idx (status, expires_at)` serves the Celery sweep that expires unpaid orders after 15 minutes.
