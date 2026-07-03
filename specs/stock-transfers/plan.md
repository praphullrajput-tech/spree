# Implementation Plan: Stock Transfers

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Basic one-shot transfer shipped; 6.0 lifecycle + line items pending

---

## Summary

`Spree::StockTransfer` currently performs a one-shot atomic transfer: source decrements and destination increments in the same transaction, creating `StockMovement` records for both. The transfer has a generated number (T-prefix) and no status column. The `docs/plans/6.0-inventory-operations.md` plan upgrades this significantly: a `draft → ready_to_ship → in_transit → partially_received → received → cancelled` state machine, first-class `StockTransferItem` line items enabling partial receive, and a two-phase stock movement model (source decrements on `mark_in_transit`; destination increments on `receive`). The Admin SPA has a create-transfer sheet on the Products → Transfers page.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Number generation** | `Spree::Core::NumberGenerator` with prefix `T`; `Spree::NumberIdentifier` |
| **6.0 state machine** | `state_machines-activerecord`; column `status` per `6.0-normalize-state-to-status.md` |
| **6.0 typed movements** | Consumes `6.0-typed-stock-movements.md` primitives (`kind: received/shipped`) |
| **Scope** | Backend + SPA shipped (basic); 6.0 lifecycle pending |

---

## Key Decisions

1. **One-shot atomic today.** Source decrements and destination increments in the same DB transaction. Both `StockMovement` records reference the transfer as `originator`. No status column exists today.

2. **6.0: Two-phase stock movement.** Source decrements on `mark_in_transit` (units physically leave). Destination increments on `receive` (units physically arrive). Between events, units are in-flight — gone from source, not yet at destination. This is the only correct model for multi-day inter-warehouse transfers.

3. **6.0: `StockTransferItem` is a first-class join table.** Current model: per-variant `StockMovement` rows are the implicit line items. 6.0: explicit `spree_stock_transfer_items` table with `quantity_shipped`, `quantity_received`, `discrepancy_reason`. This enables partial receive and discrepancy tracking.

4. **`PurchaseOrder` replaces the `source_location_id: nil` hack.** A transfer with nil source is semantically a vendor receive. 6.0 introduces `Spree::PurchaseOrder` (separate model, separate table) for vendor receives. The `StockTransfer` model will require both source and destination in 6.0.

5. **Cancellation of an in_transit transfer requires a merchant decision.** No silent reversal. Merchant chooses: reverse source (treat as never shipped) or write off as shrinkage. This is a deliberate UX requirement — silent reversals mask inventory errors.

6. **`Receivable` concern shared by `StockTransfer` and `PurchaseOrder`.** The receive-flow (partial receive, status transitions, stock movement writes) is extracted into a shared concern so the two models don't duplicate logic.

7. **No `type` STI usage.** The `type` column exists in the schema but is unused. Do not use it for PurchaseOrder — separate model is the correct decision (different domain vocabulary: vendor/cost vs warehouse/internal).

---

## Constitution Check

- [x] **API-First**: Admin API before SPA consumed it
- [x] **Read/Write Symmetry**: `source_location_id`, `destination_location_id`, `reference` serialized and accepted
- [x] **Prefixed IDs**: `st_…` for transfers; association IDs (location IDs) returned as `sloc_…`
- [x] **Serializer Hierarchy**: `Admin::StockTransferSerializer` (admin-only — no Store serializer)
- [x] **Type Pipeline**: Typelizer + Zod regen after serializer changes
- [x] **Security**: CanCanCan `can :manage, Spree::StockTransfer`
- [x] **Namespace**: `Spree::StockTransfer` — `Spree.base_class` subclass
- [x] **Plan Conflicts**: Reviewed `6.0-inventory-operations.md` — this spec covers current state + documents 6.0 pending; no conflict. Reviewed `6.0-typed-stock-movements.md` — 6.0 lifecycle writes typed movements with `stock_transfer_id`; this plan is a consumer of that plan

---

## Project Structure

```text
# Backend — models
spree/core/app/models/spree/stock_transfer.rb                   ← number generator, one-shot today
spree/core/app/models/spree/stock_movement.rb                   ← originator FK references transfer

# 6.0 additions
spree/core/app/models/spree/stock_transfer_item.rb              ← PENDING
spree/core/app/models/concerns/spree/receivable.rb              ← PENDING (shared with PurchaseOrder)
spree/core/app/models/spree/purchase_order.rb                   ← PENDING
spree/core/app/models/spree/vendor.rb                           ← PENDING

# Backend — serializers
spree/api/app/serializers/spree/api/v3/admin/stock_transfer_serializer.rb

# Backend — controllers
spree/api/app/controllers/spree/api/v3/admin/stock_transfers_controller.rb

# Frontend
packages/dashboard/src/routes/_authenticated/$storeId/products/transfers.tsx
packages/dashboard/src/hooks/use-stock-transfers.ts
packages/dashboard/e2e/stock-transfers.spec.ts
```

---

## Phase 1: One-Shot Transfer (✅ Complete)

- `Spree::StockTransfer` model with number generator (T-prefix)
- Atomic source decrement + destination increment + `StockMovement` records
- Admin API: full CRUD
- SPA: Products → Transfers page with create-transfer sheet
- Hook and E2E tests shipped

---

## Phase 2: 6.0 — Lifecycle + Line Items (PENDING)

Depends on `6.0-typed-stock-movements.md` primitives landing first.

- Add `status` column (string) + `state_machines-activerecord` state machine
- Add `spree_stock_transfer_items` table: `stock_transfer_id`, `variant_id`, `quantity_shipped`, `quantity_received`, `discrepancy_reason`, `condition`
- `mark_in_transit` action: source decrements via typed `shipped` movements with `stock_transfer_id`
- `receive` action: destination increments via typed `received` movements; partial receive supported
- Cancellation: merchant-choice reversal vs shrinkage write-off
- New `Spree::PurchaseOrder` + `Spree::Vendor` models (parallel receive flow)
- `Receivable` shared concern
- SPA: lifecycle screens per status (draft/edit → ready_to_ship → receive form → read-only summary)
- SPA: Purchase Orders list page under Products nav

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Two-phase stock movement (6.0) | Accurate availability during transit — source shows reduced stock before destination shows increased | One-shot keeps `count_on_hand` accurate at both ends simultaneously, but incorrectly inflates destination availability before units physically arrive |
| Separate `PurchaseOrder` model (6.0) | Vendor receives have domain-specific attributes (unit_cost, vendor, expected_at) that don't belong on `StockTransfer` | STI on `StockTransfer` would force one table to carry both vocabularies; vocabulary mismatch signals wrong abstraction |
