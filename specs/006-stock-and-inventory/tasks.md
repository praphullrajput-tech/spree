---

description: "Task list for Stock & Inventory (reverse-engineered, brownfield migration)"

---

# Tasks: Stock & Inventory

**Input**: Design documents from `specs/006-stock-and-inventory/` (`spec.md`, `plan.md`)

**Tests**: Included where actual RSpec coverage exists in the codebase.

**Organization**: Tasks are grouped by actual component (packing pipeline,
stock/backorder accounting, reservations, Admin API, admin SPA) rather than
by user story phases, since this migration documents what was already built
rather than proposing new priority-ordered stories. All tasks are marked
complete — this reflects shipped code, not a forward plan.

## Format: `[ID] [P?] [Component] Description`

- **[P]**: Independent files, could have been built in parallel
- All tasks below are `[x]` — completed, already in `main`

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core` gem builds/tests: `cd spree/core && bundle exec rspec`
- [x] T002 [P] Confirm `spree/api` gem builds/tests: `cd spree/api && bundle exec rspec`
- [x] T003 [P] Confirm frontend workspace builds: `pnpm typecheck && pnpm lint` at workspace root

---

## Phase 2: Foundational (Core Domain Models)

- [x] T004 [spree/core] `Spree::StockLocation` model (`spree/core/app/models/spree/stock_location.rb`) — `KINDS`, `PICKUP_STOCK_POLICIES`, `has_prefix_id :sloc`, default-location enforcement (`ensure_one_default`), country/state normalization
- [x] T005 [spree/core] `Spree::StockItem` model (`spree/core/app/models/spree/stock_item.rb`) — `has_prefix_id :si`, `count_on_hand` validation, `Spree::Metafields`/`Spree::Metadata`, `for_store` scope, `allocated_count`/`available_count` (stub pending 6.0 typed stock movements)
- [x] T006 [spree/core] `Spree::StockItem::Webhooks` concern stub (`spree/core/app/models/spree/stock_item/webhooks.rb`)
- [x] T007 [spree/core] `Spree::InventoryUnit` model + state machine (`spree/core/app/models/spree/inventory_unit.rb`) — `on_hand → backordered/shipped → returned`, `split`/`split_inventory!`, `has_prefix_id :fi`
- [x] T008 [spree/core] `Spree::StockReservation` model (`spree/core/app/models/spree/stock_reservation.rb`) — `has_prefix_id :res`, `active`/`expired`/`for_order`/`for_store` scopes, `ttl_for` (per-store → global config → 10min default)
- [x] T009 [spree/core] Ransack allowlists on `StockItem`, `StockLocation`, `StockReservation` (`whitelisted_ransackable_attributes`/`_associations`)

**Checkpoint**: Core stock/inventory models in place.

---

## Component: Packing Pipeline

- [x] T010 [P] `Spree::Stock::Package`/`ContentItem` — transient grouping of inventory units per stock location (`spree/core/app/models/spree/stock/package.rb`), `to_shipment` conversion
- [x] T011 [P] `Spree::Stock::InventoryUnitBuilder` — builds pending `InventoryUnit`s from order line items (`spree/core/app/models/spree/stock/inventory_unit_builder.rb`)
- [x] T012 [Packer] `Spree::Stock::Packer` — builds the default package per stock location, applying `StockLocation#fill_status` to split on-hand/backordered quantities (`spree/core/app/models/spree/stock/packer.rb`), depends on T004/T010/T011
- [x] T013 [P] [Splitter] `Splitter::Base` — chain-of-responsibility base for package splitting (`spree/core/app/models/spree/stock/splitter/base.rb`)
- [x] T014 [P] [Splitter] `Splitter::Digital` — splits digital vs. physical variants into separate packages (`spree/core/app/models/spree/stock/splitter/digital.rb`)
- [x] T015 [P] [Splitter] `Splitter::Backordered` — splits on-hand vs. backordered content into separate packages (`spree/core/app/models/spree/stock/splitter/backordered.rb`)
- [x] T016 [P] [Splitter] `Splitter::Weight` — worst-fit bin-packs contents over a weight `threshold` (default 150) into multiple packages (`spree/core/app/models/spree/stock/splitter/weight.rb`)
- [x] T017 [Prioritizer] `Spree::Stock::Prioritizer` — merges duplicate packages, prunes empty ones (`spree/core/app/models/spree/stock/prioritizer.rb`); `sort_packages` is a documented no-op (see spec.md Migration Notes)
- [x] T018 [Estimator] `Spree::Stock::Estimator` — computes/sorts shipping rates per package, VAT-aware (`spree/core/app/models/spree/stock/estimator.rb`), depends on T010
- [x] T019 [Coordinator] `Spree::Stock::Coordinator` — orchestrates build → prioritize → estimate → `shipments` (`spree/core/app/models/spree/stock/coordinator.rb`), depends on T012/T017/T018
- [x] T020 [P] RSpec: `spree/core/spec/models/spree/stock/prioritizer_spec.rb` — merge/prune/split-across-packages coverage for T017

**Checkpoint**: An order's line items can be packed into shippable, rate-estimated packages.

---

## Component: Stock & Backorder Accounting

- [x] T021 [StockItem] `adjust_count_on_hand`/`set_count_on_hand` with lock-guarded `process_backorders` (FIFO fill of oldest backordered `InventoryUnit`s) — `spree/core/app/models/spree/stock_item.rb`, depends on T005/T007
- [x] T022 [StockLocation] `fill_status(variant, quantity)` — splits requested quantity into on-hand vs. backordered (including pre-order oversell), `move`/`restock`/`unstock`/`restock_backordered` stock-movement helpers — `spree/core/app/models/spree/stock_location.rb`
- [x] T023 [Quantifier] `Spree::Stock::Quantifier` — `total_on_hand`, `available_stock`, `reserved_quantity`, `can_supply?`, `backorderable?` (`spree/core/app/models/spree/stock/quantifier.rb`), depends on T005/T008
- [x] T024 [P] Pre-order support: `Variant#preorder?`/`#preorder_ships_at`, `backorder_limit` oversell cap threaded through `Quantifier#can_supply?` and `StockLocation#fill_status` (variant model outside this migration's read set — see spec.md Migration Notes on scope/plan gap)
- [x] T025 [P] RSpec: `spree/core/spec/models/spree/product_preorder_spec.rb` — pre-order flag/date logic, backorder_limit capping, fulfillment interaction, scheduled-launch interaction — covers T022/T023/T024

**Checkpoint**: Stock counts, backorders, and pre-order oversell are correctly accounted for.

---

## Component: Stock Reservations (Checkout Holds)

- [x] T026 [Reserve] `Spree::StockReservations::Reserve` — pessimistic-locked reservation upsert per (stock_item, line_item), excludes backorderable/pre-order variants, raises `InsufficientStockError` (`spree/core/app/services/spree/stock_reservations/reserve.rb`), depends on T008/T023
- [x] T027 [P] `Spree::StockReservations::InsufficientStockError` (`spree/core/app/models/spree/stock_reservations/insufficient_stock_error.rb`)
- [x] T028 [Extend] `Spree::StockReservations::Extend` — refreshes `expires_at` for all of an order's reservations (`spree/core/app/services/spree/stock_reservations/extend.rb`), depends on T008
- [x] T029 [ExpireJob] `Spree::StockReservations::ExpireJob` — batched deletion of expired reservations (`spree/core/app/jobs/spree/stock_reservations/expire_job.rb`), depends on T008
- [x] T030 Gate all reservation behavior behind `Spree::Config[:stock_reservations_enabled]` (T026/T028 both short-circuit to success when disabled)

**Checkpoint**: Checkout-time stock holds prevent concurrent oversell; expired holds are reclaimed automatically.

---

## Component: Admin API v3

- [x] T031 [P] `Spree::Api::V3::Admin::StockItemsController` — index/show/update only (no create — auto-provisioned), `permitted_params: :count_on_hand, :backorderable, metadata: {}` (`spree/api/app/controllers/spree/api/v3/admin/stock_items_controller.rb`)
- [x] T032 [P] `Spree::Api::V3::Admin::StockLocationsController` (`spree/api/app/controllers/spree/api/v3/admin/stock_locations_controller.rb`)
- [x] T033 [P] `Spree::Api::V3::Admin::StockReservationsController` — read-only, store-scoped via `StockReservation.for_store` (`spree/api/app/controllers/spree/api/v3/admin/stock_reservations_controller.rb`)
- [x] T034 [P] `Spree::Api::V3::Admin::StockTransfersController` (`spree/api/app/controllers/spree/api/v3/admin/stock_transfers_controller.rb`)
- [x] T035 [P] Store + Admin serializers: `StockItemSerializer`, `StockLocationSerializer`, `StockReservationSerializer`, `StockMovementSerializer`, `StockTransferSerializer` and their `Admin::` subclasses — read/write field symmetry verified for `StockItem` (constitution Principle III)
- [x] T036 Type-generation pipeline run for the above serializers: `bundle exec rake typelizer:generate` → `pnpm generate:zod` → integration specs → `rake rswag:specs:swaggerize`

**Checkpoint**: Back-office API surface for stock items/locations/reservations/transfers is live.

---

## Component: Admin SPA

- [x] T037 [P] `packages/dashboard/src/routes/_authenticated/$storeId/settings/stock-locations.tsx` — stock location settings table/form
- [x] T038 [P] `packages/dashboard/src/hooks/use-stock-locations.ts` — wraps `@spree/admin-sdk` stock-location calls
- [x] T039 [P] `packages/dashboard/src/schemas/stock-location.ts` — Zod schema, `formValuesToParams`, country/state ISO mapping
- [x] T040 [P] `packages/dashboard/src/components/spree/products/inventory-section.tsx` — per-variant stock display/edit on the product page

**Checkpoint**: Admins can manage stock locations and view/edit per-product stock from the SPA.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational models (Phase 2)** → the three
  domain components (Packing Pipeline, Stock & Backorder Accounting, Stock
  Reservations) can proceed in parallel once models exist → **Admin API v3**
  depends on the domain components it exposes → **Admin SPA** depends on
  the Admin API endpoints.
- Within Packing Pipeline: `Package`/`InventoryUnitBuilder` (T010/T011) →
  `Packer` (T012) → `Splitter::*` (T013-T016, parallelizable) →
  `Prioritizer` (T017) → `Estimator` (T018) → `Coordinator` (T019).
- Within Stock Reservations: `StockReservation` model (T008) →
  `Reserve`/`Extend`/`ExpireJob` (T026/T028/T029, parallelizable once T008
  exists).

## Notes

- This is a completed-feature migration: all tasks are marked `[x]` and
  reflect code already on `main`, not forward work.
- Gaps identified during migration (tracked in spec.md → Migration Notes,
  not re-litigated here): no dedicated Weight-splitter or Extend-service
  RSpec coverage found; `Prioritizer#sort_packages` is a no-op; pre-order
  has no `docs/plans/` entry despite being a materially newer feature than
  the rest of this area.
