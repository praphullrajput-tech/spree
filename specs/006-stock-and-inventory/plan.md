# Implementation Plan: Stock & Inventory

**Branch**: `006-stock-and-inventory` | **Date**: 2026-08-25 | **Spec**: `specs/006-stock-and-inventory/spec.md`

**Input**: Feature specification from `specs/006-stock-and-inventory/spec.md`

**Note**: This plan is reverse-engineered from an already-shipped implementation
(brownfield migration). It documents the actual architecture rather than
proposing one.

## Summary

Stock & Inventory tracks physical stock per (variant, stock location),
packs an order's requested units into shippable `Spree::Stock::Package`s
(splitting by stock location, digital/physical, backorder state, and
weight), estimates shipping rates per package, and holds time-limited
`Spree::StockReservation`s during checkout so concurrent buyers can't
oversell scarce stock. A parallel oversell path (backorderable stock items,
pre-orderable variants) is bounded by a per-variant `backorder_limit`. All
of this is exposed read/write to the back office via the Admin API v3
(`stock_items`, `stock_locations`, `stock_reservations`, `stock_transfers`)
and surfaced in the admin SPA's stock-locations settings page and product
inventory section.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`)
and TypeScript (React SPA, `packages/dashboard`) for the admin-facing
surface only.

**Primary Dependencies**: Backend — `state_machines-activerecord`
(`Spree::InventoryUnit` state machine), CanCanCan + Ransack (Admin API
scoping/filtering), Alba serializers, `Spree::ServiceModule::Base`
(`StockReservations::Reserve`/`Extend`), ActiveJob (`ExpireJob`). Frontend —
TanStack Query hooks (`useStockLocations`), React Hook Form + Zod
(`schemas/stock-location.ts`).

**Storage**: PostgreSQL/MySQL/SQLite via ActiveRecord. `spree_stock_items`
(`count_on_hand`, `backorderable`), `spree_stock_locations`, `spree_inventory_units`
(`state`, `quantity`), `spree_stock_reservations` (`quantity`, `expires_at`).
No foreign key constraints, per migration conventions.

**Testing**: RSpec + Factory Bot — `spree/core/spec/models/spree/stock/prioritizer_spec.rb`,
`spree/core/spec/models/spree/product_preorder_spec.rb` (integration-style,
covers `Quantifier`/`StockLocation#fill_status`/`Variant#preorder?` together).
No Vitest/Playwright coverage identified for stock internals — the SPA
surface (`stock-locations.tsx`, `inventory-section.tsx`) is a thin CRUD/view
layer over the Admin API.

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`) consumed
by a Spree host app; admin SPA served standalone.

**Project Type**: Monorepo — `spree/core` (models/services/jobs),
`spree/api` (Admin API v3 controllers/serializers), `packages/dashboard`
(settings + product inventory UI), `packages/admin-sdk` (generated types,
consumed not hand-written here).

**Performance Goals**: Not explicitly benchmarked in source; the
`Reserve#call` pessimistic lock is scoped to only the stock items touched by
one order's line items to minimize lock contention across unrelated orders.

**Constraints**: Reservation checks must never go negative-available
(`[available, 0].max` in error messaging); `ExpireJob` deletes in batches of
1,000 to avoid long-running transactions on large backlogs.

**Scale/Scope**: Core commerce primitive — touched by every checkout and
every admin stock adjustment; no scale ceiling assumptions found in code.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (models/services/jobs),
  `spree/api` (Admin API v3), and `packages/dashboard` (settings +
  product inventory UI, consuming `packages/admin-sdk` generated types).
  The SPA never reaches into Rails models — it goes through
  `Spree::Api::V3::Admin::StockItemsController` /
  `StockLocationsController` exclusively. PASS.
- **II. Admin API Is the Only Frontend Data Source**: Confirmed —
  `use-stock-locations.ts` and the product inventory section consume
  `@spree/admin-sdk`, backed by the existing `stock_locations`/`stock_items`
  Admin API endpoints. PASS.
- **III. Read/Write Field Symmetry**: `StockItemsController#permitted_params`
  (`:count_on_hand, :backorderable, metadata: {}`) exactly matches the
  serializer's writable attributes (`allocated_count`/`available_count`/
  timestamps are read-only computed/audit fields, correctly excluded from
  `permitted_params`). PASS.
- **IV. Test-Backed**: RSpec covers `Prioritizer` (packing/merge logic) and
  the pre-order integration (`Quantifier`, `StockLocation#fill_status`,
  `Variant#preorder?`). Gaps: no test file found in this migration's scope
  for `Splitter::Weight`, `StockReservations::Extend`, or the SPA
  stock-locations flow (Vitest/Playwright). Flagged in spec.md Migration
  Notes — PARTIAL, not a blocking violation since this is documenting
  existing work, but a real gap for follow-up.
- **V. Translations and Prefixed IDs**: All models use `has_prefix_id`
  (`si_`, `sloc_`, `fi_`, `res_`); SPA copy is assumed to route through
  i18next per existing dashboard conventions (not independently verified
  file-by-file in this migration). PASS (prefixed IDs); ASSUMED (i18n).
- **VI. `docs/plans/` for Architectural Changes**: This feature is already
  governed by `docs/plans/6.0-stock-reservations.md` (reservations, shipped
  with pending Cart/Order-split + `allocated_count` follow-up) and
  `docs/plans/6.0-typed-stock-movements.md` (will replace the
  `StockItem#allocated_count` stub). No new plan entry created by this
  migration — it references the existing ones. PASS.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/006-stock-and-inventory/
├── spec.md               # Reverse-engineered feature spec
└── plan.md               # This file
```

(No `research.md`/`data-model.md`/`contracts/`/`tasks.md` phase artifacts
beyond `tasks.md`, generated separately — this is a migration, not a fresh
`/speckit-plan` run.)

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/app/models/spree/stock/package.rb
spree/core/app/models/spree/stock/content_item.rb
spree/core/app/models/spree/stock/coordinator.rb
spree/core/app/models/spree/stock/estimator.rb
spree/core/app/models/spree/stock/quantifier.rb
spree/core/app/models/spree/stock/packer.rb
spree/core/app/models/spree/stock/prioritizer.rb
spree/core/app/models/spree/stock/inventory_unit_builder.rb
spree/core/app/models/spree/stock/adjuster.rb
spree/core/app/models/spree/stock/splitter/base.rb
spree/core/app/models/spree/stock/splitter/digital.rb
spree/core/app/models/spree/stock/splitter/backordered.rb
spree/core/app/models/spree/stock/splitter/weight.rb
spree/core/app/models/spree/stock_item.rb
spree/core/app/models/spree/stock_item/webhooks.rb
spree/core/app/models/spree/inventory_unit.rb
spree/core/app/models/spree/stock_location.rb
spree/core/app/models/spree/stock_reservation.rb
spree/core/app/models/spree/stock_reservations/insufficient_stock_error.rb
spree/core/app/services/spree/stock_reservations/reserve.rb
spree/core/app/services/spree/stock_reservations/extend.rb
spree/core/app/jobs/spree/stock_reservations/expire_job.rb
spree/core/spec/models/spree/stock/prioritizer_spec.rb
spree/core/spec/models/spree/product_preorder_spec.rb

# spree/api — Admin REST API v3
spree/api/app/controllers/spree/api/v3/admin/stock_items_controller.rb
spree/api/app/controllers/spree/api/v3/admin/stock_locations_controller.rb
spree/api/app/controllers/spree/api/v3/admin/stock_reservations_controller.rb
spree/api/app/controllers/spree/api/v3/admin/stock_transfers_controller.rb
spree/api/app/serializers/spree/api/v3/stock_item_serializer.rb
spree/api/app/serializers/spree/api/v3/stock_location_serializer.rb
spree/api/app/serializers/spree/api/v3/stock_reservation_serializer.rb
spree/api/app/serializers/spree/api/v3/stock_movement_serializer.rb
spree/api/app/serializers/spree/api/v3/stock_transfer_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/stock_item_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/stock_location_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/stock_reservation_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/stock_transfer_serializer.rb

# packages/dashboard — admin SPA
packages/dashboard/src/routes/_authenticated/$storeId/settings/stock-locations.tsx
packages/dashboard/src/hooks/use-stock-locations.ts
packages/dashboard/src/schemas/stock-location.ts
packages/dashboard/src/components/spree/products/inventory-section.tsx

# packages/admin-sdk — generated types (regenerated, not hand-edited)
packages/admin-sdk/src/types/generated/StockItem.ts
packages/admin-sdk/src/types/generated/StockLocation.ts
packages/admin-sdk/src/types/generated/StockReservation.ts
packages/admin-sdk/src/types/generated/StockTransfer.ts
```

**Structure Decision**: Full-stack feature already implemented across all
three module tiers per the Module Impact table in spec.md: `spree/core`
owns the packing/reservation/backorder domain logic, `spree/api` exposes it
read/write to the back office, `packages/dashboard` (+ generated
`admin-sdk` types) renders the settings and product-inventory UI on top.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
