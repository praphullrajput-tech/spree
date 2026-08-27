# Feature Specification: Stock & Inventory

**Feature Branch**: `006-stock-and-inventory`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration). Source: `spree/core/app/models/spree/stock/*`, `spree/core/app/models/spree/{stock_item,inventory_unit,stock_location,stock_reservation}.rb`, `spree/core/app/services/spree/stock_reservations/*`, `spree/core/app/jobs/spree/stock_reservations/expire_job.rb`, `spree/api/**/*stock*`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Shipping estimate splits an order into fulfillable packages (Priority: P1)

At checkout, the system must determine which stock location(s) can supply the
items in a cart, split them into shippable packages (grouping on-hand vs.
backordered units, digital vs. physical, and weight-limited parcels), and
attach shipping-rate options to each package.

**Why this priority**: Without this, no order can be quoted a shipping cost
or turned into shipments — it's the core of checkout and fulfillment.

**Independent Test**: Build an order with line items spanning multiple stock
locations/backorder states, run `Spree::Stock::Coordinator#packages`, and
verify the resulting `Spree::Stock::Package` objects group units correctly
and each has non-empty `shipping_rates` when a valid shipping method exists.

**Acceptance Scenarios**:

1. **Given** an order with a variant on hand at one stock location, **When**
   `Coordinator#packages` runs, **Then** a single package is produced holding
   all `on_hand` inventory units, with rates estimated via `Estimator`.
2. **Given** a variant with insufficient on-hand quantity but
   `backorderable: true`, **When** packages are built, **Then** the shortfall
   is placed in a `:backordered` content item (`StockLocation#fill_status`),
   and the `Backordered` splitter separates on-hand/backordered units into
   distinct packages.
3. **Given** an order mixing digital and physical variants, **When**
   `Digital` splitter runs, **Then** digital and physical items are split
   into separate packages.
4. **Given** package contents whose combined weight exceeds the `Weight`
   splitter's `threshold` (default 150), **When** splitting runs, **Then**
   contents are worst-fit packed across multiple generated packages, each at
   or under the threshold where splittable.

---

### User Story 2 - Stock levels track quantity, backorders, and pre-orders per location (Priority: P1)

Each variant's stock is tracked per `Spree::StockLocation` via
`Spree::StockItem#count_on_hand`. Admins/back-office code can adjust stock
(`adjust_count_on_hand`, `set_count_on_hand`), and when stock increases,
previously backordered inventory units are automatically filled
(`process_backorders`). A variant may also be flagged as pre-orderable
(`preorderable` + `preorder_ships_at`), which oversells past zero exactly
like a backorder, capped by `variant.backorder_limit`.

**Why this priority**: Correct stock accounting is the foundation every
other inventory feature (checkout availability, reservations, backorder
fulfillment) depends on.

**Independent Test**: Adjust a `StockItem`'s count_on_hand up from a negative
value while backordered inventory units exist; verify the correct number of
units transition from `backordered` to `on_hand` via
`InventoryUnit#fill_backorder`.

**Acceptance Scenarios**:

1. **Given** a stock item with `count_on_hand: -5` (5 backordered units) and
   backordered inventory units queued oldest-first, **When**
   `adjust_count_on_hand(3)` runs, **Then** the 3 oldest backordered
   inventory units (or a split portion) transition to `on_hand` and the
   order is asked to `fulfill!`.
2. **Given** `variant.preorderable? == true` with no `backorder_limit`,
   **When** `Stock::Quantifier#can_supply?` is checked for any quantity,
   **Then** it returns `true` (unlimited oversell).
3. **Given** a pre-order variant with `backorder_limit: 5` and
   `count_on_hand: 2`, **When** `can_supply?(7)` is checked, **Then** it
   returns `true`, and `can_supply?(8)` returns `false`.
4. **Given** a product whose `status` is not `active`, **When** a variant on
   that product is checked via `variant.preorder?`, **Then** it returns
   `false` even if `preorderable: true` — pre-order relaxes only the publish
   gate, not the product status gate.

---

### User Story 3 - Checkout reserves stock so concurrent buyers can't oversell (Priority: P2)

While a customer is in checkout, `Spree::StockReservations::Reserve` places
a time-limited `Spree::StockReservation` per (stock_item, line_item),
excluding backorderable/pre-order variants (which oversell by design).
`Spree::Stock::Quantifier` subtracts active reservations (other than the
customer's own order, via `excluded_order`) from `available_stock` so a
second customer can't check out the same physical unit. Reservations expire
and are pruned by `Spree::StockReservations::ExpireJob`; `Extend` refreshes
the TTL as checkout progresses.

**Why this priority**: Prevents overselling scarce physical stock across
concurrent checkouts — a correctness/trust issue, but the storefront
degrades gracefully (via `Spree::Config[:stock_reservations_enabled]`)
without it, unlike core packing/shipping (P1).

**Independent Test**: Reserve stock for order A (using up all on-hand
units), then attempt to reserve the same variant for order B and verify
`Reserve#call` returns a `failure` with an `InsufficientStockError` message.

**Acceptance Scenarios**:

1. **Given** `Spree::Config[:stock_reservations_enabled]` is `false`,
   **When** `Reserve#call(order:)` runs, **Then** it short-circuits to
   `success(order)` without creating reservations.
2. **Given** two concurrent orders competing for the last unit of a
   non-backorderable variant, **When** both call `Reserve#call`
   concurrently, **Then** the pessimistic row lock on `Spree::StockItem`
   serializes the checks and only one order succeeds; the other receives
   `InsufficientStockError`.
3. **Given** an active reservation whose `expires_at` has passed, **When**
   `ExpireJob#perform` runs, **Then** the expired reservation rows are
   deleted in batches of 1,000.
4. **Given** an order re-visits the checkout shipping step, **When**
   `Extend#call(order:)` runs, **Then** all of that order's reservations get
   a refreshed `expires_at` per `StockReservation.ttl_for(order)` (per-Store
   preference, else global config, else a 10-minute default).

---

### Edge Cases

- What happens when a variant doesn't track inventory
  (`should_track_inventory?` false)? `Quantifier#total_on_hand` returns
  `BigDecimal::INFINITY` and the packer adds the unit directly without
  checking a stock location.
- How does the system handle a stock location with no stock item for a
  requested variant? `StockLocation#fill_status` creates one on demand via
  `stock_item_or_create`.
- What happens if the same variant is oversold via both a backorder and a
  reduction in `count_on_hand` at the same time? `process_backorders` is
  lock-guarded (`with_lock` in `adjust_count_on_hand`) and only fills
  forward (positive deltas), never retroactively un-fills on a decrease.
- What happens when a stock location becomes inactive? `Quantifier` only
  considers `stock_items.with_active_stock_location` when no location is
  explicitly given.
- What happens to a reservation when its line item's order is abandoned
  (never completes checkout)? It simply expires per TTL and is later
  swept by `ExpireJob` — no explicit cancellation path exists.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST track physical stock per (variant, stock location)
  pair via `Spree::StockItem#count_on_hand`.
- **FR-002**: System MUST split an order's requested inventory units into
  one or more `Spree::Stock::Package`s per stock location that can supply
  them (`Coordinator#build_packages`), with pluggable further splitting via
  `Spree.stock_splitters` (`Base`, `Digital`, `Backordered`, `Weight`).
- **FR-003**: System MUST estimate and attach shipping rates to each package
  via `Spree::Stock::Estimator`, respecting shipping-method availability,
  currency, and tax-zone-aware pricing.
- **FR-004**: System MUST allow a stock item to oversell via `backorderable`
  (unconditional) or via a pre-orderable variant (`preorderable` +
  `preorder_ships_at`), and MUST cap both by `variant.backorder_limit` when
  present.
- **FR-005**: System MUST automatically transition previously backordered
  `Spree::InventoryUnit`s to `on_hand` (oldest-first, FIFO by order
  `completed_at`) when stock increases enough to cover them
  (`StockItem#process_backorders`).
- **FR-006**: System MUST compute purchasable quantity via
  `Spree::Stock::Quantifier#total_on_hand`/`#can_supply?`, accounting for
  on-hand stock, active reservations, and the oversell/backorder-limit
  rules.
- **FR-007**: System MUST reserve stock for line items during checkout
  (`Spree::StockReservations::Reserve`) when
  `Spree::Config[:stock_reservations_enabled]` is true, using a per-store or
  global TTL (`StockReservation.ttl_for`), and MUST exclude
  backorderable/pre-order variants from reservation (they oversell by
  design and are bounded elsewhere).
- **FR-008**: System MUST expire stock reservations past their `expires_at`
  via a recurring background job (`StockReservations::ExpireJob`), deleted
  in batches.
- **FR-009**: System MUST expose Stock Items, Stock Locations, Stock
  Reservations, Stock Movements, and Stock Transfers via the Admin API v3
  with prefixed IDs, Ransack-allowlisted filtering, and store-scoped
  queries.
- **FR-010**: System MUST prevent negative `count_on_hand` except when the
  stock item is backorderable, the variant is a pre-order, or the change
  itself is a further decrease of existing negative stock
  (`StockItem#verify_count_on_hand?`).

### Key Entities

- **Spree::StockLocation**: A warehouse/store/fulfillment-center location
  that can hold stock. Has `kind`, `pickup_stock_policy`,
  `pickup_ready_in_minutes`, one `default` flag, country/state, and
  `backorderable_default`.
- **Spree::StockItem**: Per (variant, stock_location) inventory record —
  `count_on_hand`, `backorderable`, `allocated_count` (currently a Ruby
  stub returning 0, see Migration Notes), `available_count`.
- **Spree::InventoryUnit**: A unit of a variant tied to a line item/order,
  state-machined through `on_hand → shipped` or `backordered → on_hand →
  shipped → returned`.
- **Spree::Stock::Package / ContentItem**: Transient (non-persisted)
  grouping of inventory units bound for one stock location, converted to a
  `Spree::Shipment` via `Package#to_shipment`.
- **Spree::StockReservation**: Time-limited hold (`expires_at`) on a
  (stock_item, line_item) pair belonging to an order, preventing other
  orders from counting that quantity as available.
- **Spree::Stock::Quantifier**: Non-persisted calculator of purchasable
  quantity for a variant (optionally scoped to a stock location, optionally
  excluding one order's own reservations).

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Stock::{Package,Coordinator,Estimator,Quantifier,Packer,Prioritizer,InventoryUnitBuilder,Splitter::{Base,Digital,Backordered,Weight}}`, `Spree::{StockItem,StockLocation,InventoryUnit,StockReservation}`, `Spree::StockReservations::{Reserve,Extend,InsufficientStockError}`, `Spree::StockReservations::ExpireJob` |
| `spree/api` (Store/Admin API v3) | Yes | Admin controllers/serializers for `stock_items`, `stock_locations`, `stock_reservations`, `stock_transfers`; Store/Admin `StockMovementSerializer` |
| `packages/dashboard` (admin SPA) | Yes | `settings/stock-locations.tsx` route, `use-stock-locations.ts` hook, `schemas/stock-location.ts`, product `inventory-section.tsx` |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated types (`StockItem`, `StockLocation`, `StockReservation`, `StockTransfer`, `Fulfillment`) — regenerated from serializers, not hand-written |
| `docs/plans/` | Yes | Governed by `docs/plans/6.0-stock-reservations.md` (reservations shipped; Cart/Order split integration + `allocated_count` term pending) and `docs/plans/6.0-typed-stock-movements.md` (will replace the `allocated_count` stub with a real column) |

### API Contract *(include if feature touches spree/api)*

- **Endpoints**: `GET/PATCH /api/v3/admin/stock_items` (no `create` — stock
  items are auto-created when a variant lands at a location),
  `GET/POST/PATCH/DELETE /api/v3/admin/stock_locations`, `GET
  /api/v3/admin/stock_reservations` (read-only), `GET/POST/PATCH
  /api/v3/admin/stock_transfers`.
- **Serializer fields (read)**: `StockItem` — `count_on_hand`,
  `backorderable`, `metadata`, `allocated_count`, `available_count`,
  `created_at`/`updated_at` (admin only) — matched 1:1 by
  `permitted_params: :count_on_hand, :backorderable, metadata: {}`.
  `StockLocation` — `name`, `kind`, `active`, `default`, `pickup_enabled`,
  address fields. `StockReservation` — `stock_item_id`, `line_item_id`,
  `order_id`, `quantity`, `expires_at` (read-only, no write endpoint).
- **Auth**: Admin API — secret key + scopes or Admin JWT + CanCanCan, both
  converging on `Spree::Api::V3::Admin::ResourceController`. No Store API
  surface for stock internals (customers never see raw stock counts, only
  derived `in_stock`/`purchasable` on products/variants).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given an order spanning N stock locations, `Coordinator#packages`
  returns exactly the packages needed to fulfill it (no variant lost, no
  duplicate content items across packages) in a single pass.
- **SC-002**: Two concurrent checkouts for the last unit of a
  non-backorderable variant never both succeed — the pessimistic lock in
  `Reserve#call` guarantees at most one reservation holds the unit.
- **SC-003**: A stock replenishment that covers N backordered units fills
  exactly the oldest N units (FIFO by order completion), never over- or
  under-filling.
- **SC-004**: Expired reservations are removed within one `ExpireJob` run
  after their `expires_at` passes (job is idempotent — reruns are no-ops
  once rows are deleted).

## Assumptions

- Stock reservations are a checkout-time hold, not a persistent allocation
  record — the 6.0 Typed Stock Movements plan will introduce a durable
  `allocated_count` distinct from reservations.
- `Spree.stock_splitters` is treated as a fixed, ordered pipeline
  (`Base → Digital → Backordered → Weight` by default); this spec does not
  cover extensions that reorder or add custom splitters.
- Multi-currency/tax behavior in `Estimator` (VAT price calculation, tax
  zone lookups) is assumed to be correctly delegated to
  `Spree::VatPriceCalculation` and `Spree::TaxRate` — not re-verified here.
- The Store API intentionally has no stock-item/location CRUD surface;
  customers only see derived availability, not raw counts.

## Migration Notes

- **Pre-order support looks like a newer, partially-landed feature.**
  `spec/models/spree/product_preorder_spec.rb` and the `preorderable` /
  `preorder_ships_at` / `backorder_limit` variant attributes are exercised
  thoroughly in specs and referenced inline in `StockLocation#fill_status`
  and `Stock::Quantifier#can_supply?`, but:
  - There is no dedicated `Spree::Stock::Splitter` or dashboard UI for
    pre-orders found alongside the four splitters covered here — pre-order
    handling piggybacks entirely on the existing backorder code path
    (`fill_status`, `process_backorders`) rather than being a first-class
    concept in `Spree::Stock::Package`/`ContentItem`.
  - No `docs/plans/*.md` entry documents the pre-order feature's scope,
    unlike every other area touched in this migration (which map cleanly to
    `6.0-stock-reservations.md` / `6.0-typed-stock-movements.md`). This
    spec does not attempt to backfill that plan — flagging it as a gap for
    a follow-up `/speckit.specify` or a `docs/plans/` entry.
  - `StockItem#allocated_count` is a hardcoded stub (`0`) with a comment
    pointing at `6.0-typed-stock-movements.md` for the real column — any
    consumer relying on non-zero `allocated_count` today is reading
    aspirational data.
- `Spree::Stock::Prioritizer#sort_packages` is a documented no-op (comment:
  "order packages by preferred stock_locations") — priority ordering by
  stock location preference is not actually implemented, only package
  deduplication/merging and pruning are.
- No RSpec coverage was found for `Spree::Stock::Splitter::Weight` or
  `Spree::StockReservations::Extend` in the files reviewed for this
  migration (only `Prioritizer` and the pre-order integration spec were
  in scope) — worth confirming coverage exists elsewhere before treating
  this spec as fully test-backed per constitution Principle IV.
