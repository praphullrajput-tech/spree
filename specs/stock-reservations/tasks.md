---

description: "Task list for Stock Reservations — 5.5 fully shipped; 6.0 Cart/Order split + allocated_count pending"
---

# Tasks: Stock Reservations

**Status**: 5.5 fully shipped (PR #13978); 6.0 refinements pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Core concerns | `spree/core/app/models/spree/stock/` |
| Migrations | `spree/core/db/migrate/` |
| Background jobs | `spree/core/app/jobs/spree/stock_reservations/` |
| Services | `spree/core/app/services/spree/stock_reservations/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |

---

## Phase 1: 5.5 Core ✅ (PR #13978)

### Models & Core

- [x] T001 `spree/core/app/models/spree/stock_reservation.rb` — `has_prefix_id :res`; `belongs_to :stock_item` (class_name `Spree::StockItem`); `belongs_to :line_item` (class_name `Spree::LineItem`); `belongs_to :order` (class_name `Spree::Order`); `validates :quantity, numericality: { greater_than: 0, only_integer: true }`; validates `line_item_id` uniqueness scoped to `stock_item_id`; scopes: `active` (expires_at > now), `expired`, `for_variant`, `for_order`; `extend!` method; `release!` method
- [x] T002 `spree/core/app/models/spree/stock_item.rb` — add `def allocated_count; 0; end` shim (returns 0 until 6.0 typed movements land); update `count_on_hand` queries to exclude active reservations where relevant
- [x] T003 `spree/core/app/models/spree/stock/quantifier.rb` — patch `total_on_hand` formula: `[available_stock - reserved_quantity, 0].max`; add `reserved_quantity` helper: `StockReservation.active.for_variant(variant).sum(:quantity)`
- [x] T004 Migration: create `spree_stock_reservations` — `id`, `stock_item_id`, `line_item_id`, `order_id`, `quantity integer null: false`, `expires_at datetime null: false`, timestamps; indexes: `(line_item_id, stock_item_id)` unique, `expires_at`, `stock_item_id`, `order_id`
- [x] T005 Factory `spree/core/lib/spree/testing_support/factories/stock_reservation_factory.rb` — `active` (expires in future) and `expired` traits

### Services

- [x] T006 `spree/core/app/services/spree/stock_reservations/reserve.rb` — `call(order:, stock_item:, line_item:, quantity:)` → creates reservation with TTL; skips if `backorderable?` or `stock_reservations_enabled == false`
- [x] T007 `spree/core/app/services/spree/stock_reservations/extend.rb` — `call(reservation:)` → calls `reservation.extend!`
- [x] T008 `spree/core/app/services/spree/stock_reservations/release.rb` — `call(order:)` → destroys all active reservations for the order

### Background Job

- [x] T009 `spree/core/app/jobs/spree/stock_reservations/expire_job.rb` — `DELETE WHERE expires_at < NOW()`; idempotent; no side-effects beyond the delete

### Configuration

- [x] T010 `Spree::Config[:reserve_stock_on]` — `:checkout` (default) or `:cart`
- [x] T011 `Spree::Config[:default_stock_reservation_ttl_minutes]` — integer, default: 10
- [x] T012 `Spree::Config[:stock_reservations_enabled]` — boolean, default: true
- [x] T013 `Spree::Store` preference: `preferred_stock_reservation_ttl_minutes` — overrides global default per store
- [x] T014 `Spree::StockReservation.ttl_for(order)` — resolves store preference → global config

### Serializer

- [x] T015 Admin serializer `spree/api/app/serializers/spree/api/v3/admin/stock_reservation_serializer.rb` — `id` (res_…), `stock_item_id`, `line_item_id`, `order_id` (prefixed), `quantity`, `expires_at`, `created_at`, `updated_at`

### Controller

- [x] T016 `spree/api/app/controllers/spree/api/v3/admin/stock_reservations_controller.rb` — `index` + `show` only (read-only admin surface); `scope` filtered to `active` by default; Ransack on `stock_item_id`, `order_id`, `expires_at`

### Specs

- [x] T017 `spree/core/spec/models/spree/stock_reservation_spec.rb` — `extend!` updates `expires_at`; `active` scope excludes expired; `backorderable?` items skip reserve; `total_on_hand` formula; TTL resolution (store → global)
- [x] T018 `spree/core/spec/jobs/spree/stock_reservations/expire_job_spec.rb` — expired records deleted; active records untouched
- [x] T019 `spree/api/spec/integration/spree/api/v3/admin/stock_reservations_spec.rb` — list with `active` filter; show with order context

### Type Pipeline

- [x] T020 `bundle exec rake typelizer:generate` — `AdminStockReservation` type generated
- [x] T021 `cd packages/sdk && pnpm generate:zod`
- [x] T022 `bundle exec rake rswag:specs:swaggerize`

**Checkpoint**: reservations created on checkout entry; `total_on_hand` subtracts active reservations; expired reservations cleaned up by job ✅

---

## Phase 2: 6.0 — Cart/Order Split + Typed Movements (PENDING)

Blocked on `6.0-cart-order-split.md` and `6.0-typed-stock-movements.md`.

- [ ] T023 Migration: rename `order_id` → `cart_id` on `spree_stock_reservations` (after Cart model split)
- [ ] T024 Update `Spree::StockReservation` associations: `belongs_to :cart` (was `belongs_to :order`)
- [ ] T025 Replace `allocated_count` shim with real column (from `6.0-typed-stock-movements.md`)
- [ ] T026 Update `Quantifier`: `count_on_hand - allocated_count - active_reservations` (was `count_on_hand - active_reservations`)
- [ ] T027 Add Variant Inventory tab on Product detail: surface `active_reservations` count per stock item alongside `count_on_hand`

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No standalone SPA management page for reservations | Low | Intentional — reservations are managed by the checkout service, not directly by admins; admin visibility is read-only via the index endpoint |
| No E2E test for reservation flow | Medium | Add an E2E spec for the checkout reservation cycle: add to cart → enter checkout → verify reservation created → abandon → verify released by ExpireJob |
| `allocated_count` shim returns 0 until 6.0 | Low | Documented behavior; shim is forward-compatible with the 6.0 typed movements column |
| `order_id` FK will become `cart_id` in 6.0 | Low | Migration tracked in T023; current API serializer exposes `order_id` — update when Cart split lands |
