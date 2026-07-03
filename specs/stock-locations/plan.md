# Implementation Plan: Stock Locations

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped

---

## Summary

`Spree::StockLocation` represents a physical location (warehouse, retail store, fulfillment center) that holds inventory. It is the root anchor for `StockItem`, `StockMovement`, and `Shipment`. Key properties: `kind` (open string from `KINDS = %w[warehouse store fulfillment_center]`), `active`/`default` flags, soft-delete (`acts_as_paranoid`), pickup configuration (`pickup_enabled`, `pickup_stock_policy`, `pickup_ready_in_minutes`), and `propagate_all_variants` to auto-create `StockItem` records. The feature is fully shipped with Admin API, SPA settings route, hook, and E2E tests.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Soft delete** | `acts_as_paranoid` — `deleted_at` column |
| **Name uniqueness** | `Spree::UniqueName` concern (scoped to `spree_base_uniqueness_scope`) |
| **Pickup extension** | `pickup_enabled`, `pickup_stock_policy`, `pickup_ready_in_minutes` for BOPIS |
| **Scope** | Full-stack; fully shipped |

---

## Key Decisions

1. **`KINDS` is a UI allowlist, not an enum.** `KINDS = %w[warehouse store fulfillment_center]` drives the admin dropdown. Merchants can set any arbitrary string for `kind` — the model does not validate inclusion. This is intentional extensibility.

2. **`PICKUP_STOCK_POLICIES` is a strict enum on the model.** `pickup_stock_policy` has a `validates :pickup_stock_policy, inclusion: { in: PICKUP_STOCK_POLICIES }` — only `local` or `any` are valid. This is a behavioral distinction (determines checkout availability logic), not just a display label.

3. **Soft-delete preserves history.** Deleting a stock location marks `deleted_at` — it is excluded from `active` scope and routing but its `StockItem` and `StockMovement` records remain for audit purposes. This is critical for financial reconciliation.

4. **`propagate_all_variants` auto-seeds stock items on create.** When `true`, an `after_create` callback creates a `StockItem` for every active variant. This is the "automatic" mode; when `false`, merchants must manually create stock items per-variant.

5. **`default` flag determines fallback routing.** The default location is used by `Spree::OrderRouting::Strategy::Rules` (via the `DefaultLocation` rule) when other rules produce a tie. No uniqueness enforcement at the model level — multiple defaults are technically possible but functionally wrong; merchant responsibility.

6. **No `store_id` FK.** Stock locations are not single-store scoped — they can be shared across stores in a multi-store setup. This distinguishes them from `Spree::Promotion` and `Spree::Product` (which are single-store in 5.5/5.6+).

7. **Pickup configuration feeds delivery rate providers.** `pickup_enabled`, `pickup_stock_policy`, and `pickup_ready_in_minutes` are consumed by `Spree::DeliveryRateProvider` implementations (see `6.0-delivery-rate-provider.md`) to determine BOPIS rate eligibility and lead times.

---

## Constitution Check

- [x] **API-First**: Admin API before SPA consumed it
- [x] **Read/Write Symmetry**: `name`, `kind`, `active`, `default`, `pickup_enabled`, `pickup_stock_policy`, `pickup_ready_in_minutes` serialized and accepted
- [x] **Prefixed IDs**: `sloc_…` on all stock location IDs
- [x] **Serializer Hierarchy**: `Admin::StockLocationSerializer` (no Store serializer — admin-only resource)
- [x] **Type Pipeline**: Typelizer + Zod regen after serializer changes
- [x] **Security**: CanCanCan `can :manage, Spree::StockLocation`; no store scoping (shared resource)
- [x] **Namespace**: `Spree::StockLocation` — `Spree.base_class` subclass with `Spree::UniqueName`
- [x] **Plan Conflicts**: Reviewed `6.0-fulfillment-and-delivery.md` — pickup properties exist and are consumed by delivery/fulfillment; no conflict

---

## Project Structure

```text
# Backend — models
spree/core/app/models/spree/stock_location.rb

# Backend — serializers
spree/api/app/serializers/spree/api/v3/admin/stock_location_serializer.rb

# Backend — controllers
spree/api/app/controllers/spree/api/v3/admin/stock_locations_controller.rb

# Frontend
packages/dashboard/src/routes/_authenticated/$storeId/settings/stock-locations.tsx
packages/dashboard/src/hooks/use-stock-locations.ts
packages/dashboard/e2e/stock-locations.spec.ts
```

---

## Phase 1: Core Stock Location Management (✅ Complete)

- `Spree::StockLocation` model with full attribute set
- `KINDS` and `PICKUP_STOCK_POLICIES` constants
- `acts_as_paranoid` soft delete
- `Spree::UniqueName` concern for name uniqueness
- Admin API: full CRUD + stock items + stock movements nested endpoints
- Admin SPA: settings route, hook, E2E tests shipped

---

## Phase 2: 6.0 Activity Tab (PENDING)

- Location-scoped typed stock movement timeline (from `6.0-inventory-operations.md`)
- Renders `kind` + cause entity link per movement
- Answers "what changed in this warehouse this week?"
