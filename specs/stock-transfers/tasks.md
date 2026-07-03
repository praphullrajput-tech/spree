---

description: "Task list for Stock Transfers — basic one-shot transfer shipped; 6.0 lifecycle + line items pending"
---

# Tasks: Stock Transfers

**Status**: Basic one-shot transfer shipped; 6.0 lifecycle + PurchaseOrder pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/products/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: One-Shot Transfer ✅

### Models

- [x] T001 `spree/core/app/models/spree/stock_transfer.rb` — `has_prefix_id :st`; `include Spree::Core::NumberGenerator.new(prefix: 'T')`; `include Spree::NumberIdentifier`; `belongs_to :source_location` (optional, class_name `Spree::StockLocation`); `belongs_to :destination_location` (class_name `Spree::StockLocation`); `has_many :stock_movements`; validate source ≠ destination; `transfer!` class method (atomic one-shot)
- [x] T002 Factory `spree/core/lib/spree/testing_support/factories/stock_transfer_factory.rb`

### Serializer

- [x] T003 Admin serializer `spree/api/app/serializers/spree/api/v3/admin/stock_transfer_serializer.rb` — `id` (st_…), `number`, `source_location_id` (sloc_…), `destination_location_id` (sloc_…), `reference`, `created_at`, `updated_at`

### Controller

- [x] T004 `spree/api/app/controllers/spree/api/v3/admin/stock_transfers_controller.rb` — full CRUD; `permitted_params`: `source_location_id`, `destination_location_id`, `reference`, `variants` (with quantities)

### Specs

- [x] T005 `spree/core/spec/models/spree/stock_transfer_spec.rb` — `transfer!` creates movements at source and destination; source ≠ destination validation; number format
- [x] T006 `spree/api/spec/integration/spree/api/v3/admin/stock_transfers_spec.rb` — CRUD; source/destination location filter; number search

### Type Pipeline

- [x] T007 `bundle exec rake typelizer:generate` — `AdminStockTransfer` type generated
- [x] T008 `cd packages/sdk && pnpm generate:zod`
- [x] T009 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T010 [US1] `packages/dashboard/src/routes/_authenticated/$storeId/products/transfers.tsx` — `<ResourceTable>`; create-transfer `<Sheet>` with source/destination location selects, variant+qty inputs
- [x] T011 [US1] `packages/dashboard/src/hooks/use-stock-transfers.ts` — TanStack Query wrappers for CRUD
- [x] T012 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.stockTransfers.*`
- [x] T013 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [x] T014 `packages/dashboard/e2e/stock-transfers.spec.ts` — create transfer between two locations → verify stock movements → verify list entry
- [x] T015 Run `pnpm test:e2e` ✅

**Checkpoint**: creating a transfer decrements source and increments destination atomically ✅

---

## Phase 2: 6.0 — Lifecycle + Line Items (PENDING)

Blocked on `6.0-typed-stock-movements.md` typed movement primitives.

### Models

- [ ] T016 Migration: add `status` string column to `spree_stock_transfers`; add `expected_at` datetime
- [ ] T017 Migration: create `spree_stock_transfer_items` — `stock_transfer_id`, `variant_id` (ref), `quantity_shipped integer null: false`, `quantity_received integer default 0`, `discrepancy_reason string`, `condition string`; index `(stock_transfer_id, variant_id)`
- [ ] T018 Add `state_machines-activerecord` state machine on `status`: `draft → ready_to_ship → in_transit → partially_received → received → cancelled`
- [ ] T019 Create `spree/core/app/models/spree/stock_transfer_item.rb`
- [ ] T020 Require non-nil `source_location_id` in 6.0 (remove `optional:` from association)
- [ ] T021 Create `spree/core/app/models/concerns/spree/receivable.rb` — shared receive-flow logic with `PurchaseOrder`

### Purchase Order (6.0)

- [ ] T022 Create `spree/core/app/models/spree/vendor.rb` — `name`, `contact_name`, `email`, `phone`, `notes`, `metadata`; `belongs_to :store`; `has_many :purchase_orders`
- [ ] T023 Create `spree/core/app/models/spree/purchase_order.rb` — `include Spree::Receivable`; `belongs_to :vendor`; `PurchaseOrderItem` with `unit_cost`, `quantity_ordered`, `quantity_received`
- [ ] T024 Admin API: full CRUD for `PurchaseOrder` + `Vendor`
- [ ] T025 SPA: Products → Purchase Orders list page + detail page

### SPA Lifecycle UI (6.0)

- [ ] T026 Transfer detail page: mode per status (draft/edit → ready_to_ship → receive form → read-only)
- [ ] T027 "Mark in transit" action — writes source `shipped` typed movements
- [ ] T028 Receive form — per-item `quantity_received` input with `discrepancy_reason` select
- [ ] T029 Cancellation dialog — merchant choice: reverse stock vs. write off as shrinkage

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| `source_location_id` is currently nullable (legacy vendor receive hack) | Medium | Blocked on 6.0 `PurchaseOrder` model; until then, the nullable source remains a documented limitation |
| No lifecycle states on current transfer model | High | 6.0 phase (T016–T021) above — depends on `6.0-typed-stock-movements.md` |
| No partial receive support | High | 6.0 phase above — requires `StockTransferItem` line items |
