# Implementation Plan: Stock Reservations

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: 5.5 fully shipped; 6.0 Cart/Order split integration + `allocated_count` term pending

---

## Summary

`Spree::StockReservation` adds time-limited soft holds during checkout to prevent overselling. The model has concrete FKs to `stock_item`, `line_item`, and `order` — no polymorphism. Available stock is computed at query time: `count_on_hand - active_reservations` in 5.5; `count_on_hand - allocated_count - active_reservations` in 6.0 when typed stock movements land. `Spree::StockReservations::ExpireJob` sweeps expired records periodically. TTL is configurable per-store via `preferred_stock_reservation_ttl_minutes`. The Store API creates/extends/releases reservations as part of the checkout flow. The Admin API exposes read-only reservation visibility. Fully shipped in 5.5 (PR #13978).

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Expiry sweep** | `Spree::StockReservations::ExpireJob` — `DELETE WHERE expires_at < NOW()` |
| **Quantifier patch** | `Spree::Stock::Quantifier#total_on_hand` subtracts `active_reservations` |
| **6.0 dependency** | `6.0-typed-stock-movements.md` (adds `allocated_count` term) |
| **Scope** | Full-stack 5.5 shipped; no SPA standalone UI; 6.0 refinements pending |

---

## Key Decisions

1. **`count_on_hand` is never modified by reservations.** Physical stock is only decremented on order completion. Reservations are a soft hold computed at query time. This keeps the stock columns as a pure physical record and avoids the "is this count including reservations or not?" ambiguity.

2. **Concrete FKs, no polymorphism.** `stock_item_id`, `line_item_id`, `order_id` — all concrete. Polymorphic associations would allow reservations to attach to things other than order line items, which is not a use case and would complicate the expiry sweep and the Quantifier formula.

3. **TTL lives on Store, not StockLocation.** Reservation TTL is a checkout-experience policy, not a warehouse property. A cart with items from 3 locations must not merge 3 different TTLs. The Store policy applies uniformly.

4. **`backorderable: true` items skip reservations.** The merchant has opted into selling phantom stock. Reservations add overhead with no benefit for backorderable items. This matches Shopify (`inventoryPolicy: DENY` blocks at 0 → reserve; `CONTINUE` → skip).

5. **Store API only in 5.5.** Reservation create/extend/release hooks fire from checkout service paths only. Legacy v2 API and `Spree::CheckoutController` are intentionally not wired — they remain unaffected but customers checking out via those paths don't create reservations (documented in release notes).

6. **`allocated_count` shim in 5.5.** `StockItem` defines `def allocated_count; 0; end` in 5.5. When 6.0 typed movements land, a real `allocated_count` column replaces the shim. The Quantifier formula continues to work without change.

7. **Global config `stock_reservations_enabled: false` fully disables.** When disabled, the `Quantifier` does not subtract reservations and the checkout service skips reservation creation. Zero overhead compared to pre-5.5.

---

## Constitution Check

- [x] **API-First**: Admin read-only API and Store API checkout integration both exist
- [x] **Read/Write Symmetry**: Admin serializer exposes `quantity`, `expires_at`, `order_id`; no write surface on Admin API (read-only)
- [x] **Prefixed IDs**: `res_…` for reservations; `order_id` returned as prefixed Order ID
- [x] **Serializer Hierarchy**: `Admin::StockReservationSerializer` (admin-only; no Store serializer — Store API creates via service, not serializer)
- [x] **Type Pipeline**: Typelizer + Zod regen after serializer changes
- [x] **Security**: CanCanCan `can :read, Spree::StockReservation` for admin; reservation creation protected by checkout auth
- [x] **Namespace**: `Spree::StockReservation`, `Spree::StockReservations::ExpireJob` — `Spree` namespace throughout
- [x] **Plan Conflicts**: Reviewed `6.0-typed-stock-movements.md` — `allocated_count` shim is the integration point; no conflict. Reviewed `6.0-cart-order-split.md` — reservation moves to `Cart` in 6.0; current `order_id` FK is temporary.

---

## Project Structure

```text
# Backend — models
spree/core/app/models/spree/stock_reservation.rb                ← concrete FKs, active/expired scopes
spree/core/app/models/spree/stock/quantifier.rb                 ← patched: subtracts active_reservations

# Backend — jobs
spree/core/app/jobs/spree/stock_reservations/expire_job.rb      ← DELETE WHERE expires_at < NOW()

# Backend — services
spree/core/app/services/spree/stock_reservations/reserve.rb
spree/core/app/services/spree/stock_reservations/extend.rb
spree/core/app/services/spree/stock_reservations/release.rb

# Backend — serializers
spree/api/app/serializers/spree/api/v3/admin/stock_reservation_serializer.rb

# Backend — controllers
spree/api/app/controllers/spree/api/v3/admin/stock_reservations_controller.rb

# Backend — specs
spree/core/spec/models/spree/stock_reservation_spec.rb
spree/api/spec/integration/spree/api/v3/admin/stock_reservations_spec.rb
```

---

## Phase 1: 5.5 Core (✅ Complete, PR #13978)

- `Spree::StockReservation` model with concrete FKs and TTL
- `active` / `expired` scopes; `extend!` / `release!` methods
- `Spree::Stock::Quantifier` patched: `count_on_hand - active_reservations`
- `allocated_count` shim (returns 0) for 6.0 forward-compatibility
- `Spree::StockReservations::ExpireJob` — periodic sweep
- `Spree::StockReservations::Reserve`, `Extend`, `Release` services
- Store API checkout hooks: reserve on checkout entry, extend on activity, release on abandonment
- Admin API: read-only `index` + `show`
- `Spree::Config[:reserve_stock_on]`, `[:default_stock_reservation_ttl_minutes]`, `[:stock_reservations_enabled]` config keys
- `Store#preferred_stock_reservation_ttl_minutes` preference

---

## Phase 2: 6.0 Refinements (PENDING)

- Cart/Order split integration (`6.0-cart-order-split.md`): reservation moves from `Order` to `Cart` model; `order_id` FK becomes `cart_id`
- `allocated_count` column replaces shim when `6.0-typed-stock-movements.md` lands
- `Quantifier` formula: `count_on_hand - allocated_count - active_reservations`
- Variant Inventory tab on Product detail: surface `active_reservations` count per stock item
