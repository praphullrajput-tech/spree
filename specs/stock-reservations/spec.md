# Feature Specification: Stock Reservations

**Feature Branch**: `main` (shipped in 5.5; 6.0 Cart/Order split integration pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: `docs/plans/6.0-stock-reservations.md`

---

## User Scenarios & Testing

### User Story 1 — Reserve Stock During Checkout (Priority: P1)

When a customer enters checkout, their line item quantities are soft-held against `StockItem.count_on_hand`. Other customers see reduced availability. If the checkout is abandoned or the reservation expires, stock is automatically released.

**Why this priority**: Prevents overselling on the last unit — the classic "two customers, one item" race condition.

**Independent Test**: Two customers have a product with `count_on_hand: 1` in their carts. Customer A enters checkout first; a reservation is created for 1 unit. Customer B then attempts checkout; they see `purchasable: false` (available = count_on_hand - active_reservations = 0). Customer A completes the order; reservation is deleted and `count_on_hand` decremented.

**Acceptance Scenarios**:

1. **Given** `count_on_hand: 1` and no active reservations, **When** customer A enters checkout, **Then** a reservation is created with `quantity: 1` and `expires_at` = now + TTL
2. **Given** an active reservation for customer A, **When** customer B queries availability, **Then** computed available stock = 0 (count_on_hand - active reservations)
3. **Given** an active reservation, **When** customer performs a checkout action (address update, shipping selection), **Then** `expires_at` is extended to now + TTL
4. **Given** an expired reservation, **When** `Spree::StockReservations::ExpireJob` runs, **Then** the reservation is deleted and stock is visible again
5. **Given** a `backorderable: true` stock item, **When** customer enters checkout, **Then** no reservation is created (backorderable items skip the hold)

---

### User Story 2 — Configure Reservation Policy (Priority: P2)

A store admin configures when reservations are created (on cart add vs on checkout entry) and the TTL (how long a reservation holds stock). Configuration is per-store via store preferences.

**Why this priority**: Merchants need to balance conversion (aggressive reservation = fewer abandoned carts lose stock) against inventory availability (lenient TTL = stock visible longer).

**Independent Test**: Admin sets `store.preferred_stock_reservation_ttl_minutes = 30` and `Spree::Config[:reserve_stock_on] = :checkout`. Customer's reservation expires after 30 minutes of inactivity, not 10 (the global default).

**Acceptance Scenarios**:

1. **Given** `Spree::Config[:reserve_stock_on] = :cart`, **When** customer adds item to cart, **Then** reservation is created immediately (more aggressive policy)
2. **Given** `store.preferred_stock_reservation_ttl_minutes = 30`, **When** reservation is created, **Then** `expires_at = now + 30 minutes`
3. **Given** `Spree::Config[:stock_reservations_enabled] = false`, **When** customer enters checkout, **Then** no reservation is created; behavior is identical to pre-5.5
4. **Given** TTL resolved from `Spree::StockReservation.ttl_for(order)`, **When** store TTL is set, **Then** store TTL overrides global default

---

### User Story 3 — Admin Visibility into In-Checkout Stock (Priority: P2)

An admin can see how much stock is currently held in active checkouts ("in checkout" = `active_reservations` per variant). This surfaces pending demand that hasn't converted to orders yet.

**Why this priority**: Merchants running flash sales need to see "47 units in checkout right now" to understand true available stock.

**Independent Test**: `GET /admin/stock_reservations?q[stock_item_variant_id_eq]=<variant_id>` returns active reservations for that variant with order context.

**Acceptance Scenarios**:

1. **Given** 5 active reservations for a variant, **When** admin lists reservations for that variant, **Then** 5 records appear with order references and `expires_at`
2. **Given** a reservation, **When** admin views it, **Then** `order_id` (prefixed), `line_item_id`, `stock_item_id`, `quantity`, `expires_at` are all present
3. **Given** a mix of active and expired reservations, **When** filtering by `active`, **Then** only non-expired records appear

---

### Edge Cases

- What if TTL expires while customer is on the payment page? → Reservation expires; checkout may fail at order completion with "out of stock" — configurable TTL should exceed expected payment processing time
- What if `count_on_hand` is manually adjusted below the sum of active reservations? → Available stock goes negative (clamped at 0 by `Quantifier`); no automatic cancellation of reservations
- What if reservation creation fails (e.g., DB unavailable)? → Checkout proceeds without reservation if creation fails gracefully (fallback: no hold)
- What if `Spree::Config[:stock_reservations_enabled] = false`? → `Quantifier` does not subtract reservations; behavior is identical to pre-5.5

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::StockReservation` holds stock via concrete FKs to `stock_item`, `line_item`, `order` — no polymorphism
- **FR-002**: `StockItem.count_on_hand` is never modified by reservations — available stock is computed at query time: `count_on_hand - active_reservations` (5.5); `count_on_hand - allocated_count - active_reservations` (6.0 with typed movements)
- **FR-003**: Non-backorderable items get reservations; backorderable items do not (`!backorderable?` gate)
- **FR-004**: Reservations extend on checkout activity via `extend!` method
- **FR-005**: `Spree::StockReservations::ExpireJob` runs periodically to delete expired records
- **FR-006**: `Spree::StockReservation.ttl_for(order)` resolves: `store.preferred_stock_reservation_ttl_minutes` → `Spree::Config[:default_stock_reservation_ttl_minutes]` (default: 10)
- **FR-007**: `Spree::Config[:reserve_stock_on]` controls trigger: `:checkout` (default) or `:cart`
- **FR-008**: `Spree::Config[:stock_reservations_enabled]` disables the feature entirely when `false`
- **FR-009**: Admin API: list/show reservations; Store API: create/extend/release via checkout flow
- **FR-010**: All reservation IDs prefixed `res_…`
- **FR-011**: _(6.0 pending)_ Cart/Order split integration — reservation moves from `Order` to `Cart` model

### Key Entities

- **StockReservation** (`Spree::StockReservation`): `stock_item_id`, `line_item_id`, `order_id`, `quantity`, `expires_at`. Scopes: `active` (expires_at > now), `expired`, `for_variant`, `for_order`. Prefix: `res_`.
- **Quantifier** (`Spree::Stock::Quantifier`): updated to subtract `active_reservations` from `count_on_hand`; `allocated_count` term added in 6.0.

---

## Backend Requirements

### Data Model

- **Table**: `spree_stock_reservations`
- **Columns**: `id`, `stock_item_id`, `line_item_id`, `order_id`, `quantity` (integer), `expires_at` (datetime)
- **Indexes**: `(line_item_id, stock_item_id)` unique; `expires_at` for sweep job; `stock_item_id`; `order_id`
- **No polymorphism**: concrete FKs only

### API Surface

#### Store API (via checkout flow)

| Method | Path | Description |
|--------|------|-------------|
| POST | _(via checkout service)_ | Create reservation when entering checkout |
| PATCH | _(via checkout service)_ | Extend reservation on checkout activity |
| DELETE | _(via checkout service)_ | Release reservation on cart abandonment |

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/stock_reservations` | List reservations (Ransack-filterable) |
| GET | `/api/v3/admin/stock_reservations/:id` | Show reservation |

### Serializer Fields

**Admin StockReservationSerializer**:
- `id` (res_…), `stock_item_id`, `line_item_id`, `order_id` (prefixed), `quantity`, `expires_at`, `created_at`, `updated_at`

### Authorization

- CanCanCan: `can :read, Spree::StockReservation` for admin (read-only — reservations are created/released by the checkout service, not directly by admin)

---

## Frontend Requirements

### SPA

- No standalone management UI — reservations are surfaced in context (order detail, variant inventory tab)
- _(6.0 pending)_ Variant Inventory tab on Product detail: shows `active_reservations` count alongside `count_on_hand`

### i18n Keys

No standalone admin page; keys may appear in order detail or inventory panels when surfacing reservation context.

---

## Success Criteria

- **SC-001**: Creating a reservation reduces computed available stock for other customers
- **SC-002**: Expired reservations are cleaned up by `ExpireJob`; stock becomes available again
- **SC-003**: `backorderable: true` items do not get reservations
- **SC-004**: Per-store TTL overrides the global default via `store.preferred_stock_reservation_ttl_minutes`
- **SC-005**: Disabling via `Spree::Config[:stock_reservations_enabled] = false` restores pre-5.5 behavior with no reservation overhead
- **SC-006**: _(6.0)_ `allocated_count` term added to `Quantifier` formula alongside `active_reservations`

---

## Assumptions

- Store API create/extend/release hooks fire from checkout service methods, not from dedicated REST endpoints
- Admin API is read-only for reservations — no admin-initiated creation or extension
- `Spree::StockReservations::ExpireJob` is scheduled via a background job framework (Sidekiq/GoodJob); the schedule interval is deployment-specific
- The `allocated_count` shim (`def allocated_count; 0; end`) on `StockItem` in 5.5 is replaced by a real column in 6.0 typed movements
