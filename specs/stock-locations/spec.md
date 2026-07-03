# Feature Specification: Stock Locations

**Feature Branch**: `main` (fully implemented)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: N/A (no dedicated plan doc; referenced in `docs/plans/6.0-fulfillment-and-delivery.md` for pickup extensions)

---

## User Scenarios & Testing

### User Story 1 — Manage Stock Locations (Priority: P1)

An admin creates and manages stock locations (warehouses, stores, fulfillment centers) that hold physical inventory. Each location has a name, address, kind, and active status. Soft-delete preserves history when a location is removed.

**Why this priority**: Stock locations are a prerequisite for all inventory operations — without them, stock items, transfers, and fulfillment cannot be configured.

**Independent Test**: Admin creates a stock location with `name: "Brooklyn Warehouse"`, `kind: "warehouse"`, `country: US`. It appears in the settings list with a prefixed ID (`sloc_…`) and `active: true`. Soft-deleting it removes it from active lists but preserves historical stock movements.

**Acceptance Scenarios**:

1. **Given** no stock locations, **When** admin creates one with `name: "Brooklyn Warehouse"` and `kind: "warehouse"`, **Then** it appears with `active: true` and a prefixed ID (`sloc_…`)
2. **Given** a stock location, **When** `propagate_all_variants: true`, **When** the location is created, **Then** `StockItem` records are auto-created for all active variants
3. **Given** a stock location, **When** admin soft-deletes it, **Then** it is excluded from `active` scope but its stock movements are preserved
4. **Given** an active location with `default: true`, **When** another location is set as default, **Then** the previous default is unset
5. **Given** a location, **When** admin sets `active: false`, **Then** it is excluded from shipping rate calculations

---

### User Story 2 — Configure Pickup Points (Priority: P2)

A stock location can be configured as a customer pickup point. The admin enables pickup, sets a `pickup_stock_policy` (local stock only vs. transferable from other locations), and specifies a `pickup_ready_in_minutes` lead time displayed to customers.

**Why this priority**: BOPIS (Buy Online, Pick Up In Store) requires location-level pickup configuration; without it, all pickup-related delivery rates are unavailable.

**Independent Test**: Admin enables `pickup_enabled: true` on a store-kind location, sets `pickup_stock_policy: "local"` and `pickup_ready_in_minutes: 60`. Delivery rate providers see the location as an eligible pickup point.

**Acceptance Scenarios**:

1. **Given** a location with `pickup_enabled: true`, **When** listing pickup-enabled locations, **Then** it appears in `StockLocation.pickup_enabled` scope
2. **Given** `pickup_stock_policy: "local"`, **When** checkout queries pickup availability, **Then** only stock physically at this location is considered available for pickup
3. **Given** `pickup_stock_policy: "any"`, **When** checkout queries pickup availability, **Then** stock from any active location can satisfy the pickup order (ship-to-store)
4. **Given** `pickup_ready_in_minutes: 60`, **When** customer selects pickup delivery, **Then** the estimated readiness time is 60 minutes from order placement

---

### User Story 3 — Monitor Stock Location Activity (Priority: P2)

An admin views per-location stock movements to understand what changed and why. The activity tab (planned in 6.0 via `6.0-inventory-operations.md`) surfaces the typed movement audit feed scoped to the location.

**Why this priority**: Warehouse reconciliation requires a scoped movement history; the global stock movements firehose is unusable for per-location auditing.

**Independent Test**: `GET /api/v3/admin/stock_locations/:id/stock_movements` returns movements scoped to that location, ordered by `created_at desc`.

**Acceptance Scenarios**:

1. **Given** a location with 10 stock movements, **When** listing its movements, **Then** all 10 appear ordered by recency
2. **Given** a movement from a transfer, **When** viewing it, **Then** `originator_type: "Spree::StockTransfer"` and `originator_id` are present
3. _(6.0 pending)_ **Given** a typed stock movement, **When** displayed in the Activity tab, **Then** `kind` (received/shipped/adjusted/etc.) and cause entity link are shown

---

### Edge Cases

- What if a stock location has active stock items when deleted? → Soft-delete marks it inactive; stock items remain for historical integrity
- What if the last active stock location is deactivated? → Fulfillment will fail at checkout; no automatic protection — merchant responsibility
- What if `pickup_ready_in_minutes` is nil? → Display falls back to "Ready when notified" or delivery method's default lead time
- What if `propagate_all_variants` is false on an existing location? → `StockItem` records must be created manually per variant; no auto-population

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::StockLocation` supports three built-in kinds: `warehouse`, `store`, `fulfillment_center` (open string — extensible by setting any value)
- **FR-002**: `propagate_all_variants` flag auto-creates `StockItem` records for all variants when a new location is created
- **FR-003**: Soft-delete via `acts_as_paranoid` — deleted locations are excluded from active scopes but stock history is preserved
- **FR-004**: `pickup_enabled` boolean controls whether the location appears as a customer pickup option
- **FR-005**: `pickup_stock_policy` determines whether pickup availability uses local stock only (`local`) or any-location stock (`any`)
- **FR-006**: `pickup_ready_in_minutes` integer provides an estimated lead time for BOPIS orders
- **FR-007**: `default` boolean marks the fallback stock location; only one should be default at a time
- **FR-008**: Admin API: full CRUD for stock locations; index of stock items per location; movements per location
- **FR-009**: All stock location IDs prefixed `sloc_…`

### Key Entities

- **StockLocation** (`Spree::StockLocation`): `name`, `kind` (warehouse/store/fulfillment_center), `active`, `default`, `pickup_enabled`, `pickup_stock_policy` (local/any), `pickup_ready_in_minutes`, `propagate_all_variants`, `address1`, `city`, `state_id`, `country_id`, `zipcode`. Prefix: `sloc_`.
- **StockItem** (`Spree::StockItem`): `variant_id`, `stock_location_id`, `count_on_hand`, `backorderable`, `deleted_at`.
- **StockMovement** (`Spree::StockMovement`): `stock_item_id`, `quantity`, `originator_type`, `originator_id`, `action`.

---

## Backend Requirements

### Data Model

- **Table**: `spree_stock_locations`
- **Soft delete**: `deleted_at` column via `acts_as_paranoid`
- **Uniqueness**: `name` uniqueness enforced via `Spree::UniqueName` concern (scoped to `spree_base_uniqueness_scope`)
- **Associations**: `has_many :stock_items`, `has_many :variants through :stock_items`, `has_many :stock_movements through :stock_items`, `has_many :shipments`, `belongs_to :state`, `belongs_to :country`

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/stock_locations` | List all locations (active + inactive) |
| POST | `/api/v3/admin/stock_locations` | Create location |
| GET | `/api/v3/admin/stock_locations/:id` | Show location |
| PATCH | `/api/v3/admin/stock_locations/:id` | Update location |
| DELETE | `/api/v3/admin/stock_locations/:id` | Soft-delete location |
| GET | `/api/v3/admin/stock_locations/:id/stock_items` | List stock items for location |
| GET | `/api/v3/admin/stock_locations/:id/stock_movements` | List stock movements for location |

### Serializer Fields

**Admin StockLocationSerializer**:
- `id` (sloc_…), `name`, `kind`, `active`, `default`, `pickup_enabled`, `pickup_stock_policy`, `pickup_ready_in_minutes`, `propagate_all_variants`, `address1`, `address2`, `city`, `state_id`, `country_id`, `zipcode`, `phone`, `created_at`, `updated_at`, `deleted_at`

### Authorization

- CanCanCan: `can :manage, Spree::StockLocation` for admin
- Ransack allowlist: `name`, `active`, `default`, `kind`, `pickup_enabled`, `country_id`, `state_id`, `created_at`, `updated_at`

### i18n (Rails)

- Keys under `spree.stock_location.*`

---

## Frontend Requirements

### SPA Route

- `packages/dashboard/src/routes/_authenticated/$storeId/settings/stock-locations.tsx` — list + CRUD sheet

### Hooks

- `packages/dashboard/src/hooks/use-stock-locations.ts` — TanStack Query wrappers for CRUD

### i18n Keys

Under `admin.stockLocations.*` in all 6 locale files: page title, column headers (name, kind, active, default, pickup_enabled), kind labels, pickup policy labels, form labels, toast messages, empty state.

---

## Success Criteria

- **SC-001**: Admin can create a warehouse-kind stock location and it auto-populates stock items when `propagate_all_variants: true`
- **SC-002**: Soft-delete removes the location from active routing but preserves its stock movement history
- **SC-003**: Pickup-enabled locations with `pickup_stock_policy: "local"` only offer items physically on-hand
- **SC-004**: `pickup_ready_in_minutes` is exposed in the Admin API for delivery rate providers to consume
- **SC-005**: All IDs prefixed `sloc_…`; Ransack filters by `name`, `kind`, `active`, `pickup_enabled`

---

## Assumptions

- `Spree::UniqueName` concern enforces `name` uniqueness scoped to `spree_base_uniqueness_scope` (multi-tenant safe)
- The `KINDS` constant (`warehouse`, `store`, `fulfillment_center`) is used only for the admin UI dropdown; arbitrary kind strings are accepted by the model
- `PICKUP_STOCK_POLICIES` constant (`local`, `any`) maps to checkout availability logic in the delivery rate provider (see `6.0-delivery-rate-provider.md`)
- Activity tab (typed movement timeline scoped to a location) is pending the `6.0-inventory-operations.md` implementation
