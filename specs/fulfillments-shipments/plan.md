# Implementation Plan: Fulfillments/Shipments

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Models + API shipped; SPA + hooks pending; 6.0 rename pending

---

## Summary

`Spree::Shipment` (prefixed `ful_` to anticipate 6.0 rename) is the fulfillment record for an order. It has a state machine (pending → ready → shipped; cancel; resume), a selected shipping rate, a stock location, and associated inventory units. `Spree::InventoryUnit` (prefixed `fi_`) tracks individual item units through fulfillment and into returns. The Admin API is nested under orders with `fulfill`, `cancel`, `resume`, and `split` actions. No SPA fulfillment pages exist yet.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **State machine** | `state_machines-activerecord` gem |
| **Scope** | Models + API shipped; SPA entirely PENDING |

---

## Key Decisions

1. **Prefix `ful_` anticipates 6.0 rename.** `Spree::Shipment` already uses `has_prefix_id :ful` (Fulfillment). This is intentional forward-compatibility; the prefix will match the 6.0 model name.

2. **Inventory units track individual item copies.** One `LineItem` with `quantity: 3` creates 3 `InventoryUnit` records. This granularity enables per-unit return tracking (e.g., only 2 of 3 units returned).

3. **`ShipmentUpdateService` owns complex update logic.** Directly updating a shipment's stock_location, shipping_rate, or line items requires recalculating adjustments and propagating changes to the order. The service encapsulates this; the controller delegates to it.

4. **`OrderLock` during mutations.** Same pattern as orders — the fulfillments controller locks the order before mutating shipments to prevent concurrent write corruption.

5. **No standalone fulfillment index.** Fulfillments are always in the context of an order. There is no merchant use case for listing fulfillments across orders without order context.

6. **`split` action for multi-location fulfillment.** When an order needs to ship from two locations, admin splits a shipment — moving selected items to a new shipment with a different `stock_location_id`.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Prefixed IDs**: `ful_…` on shipments (anticipates Fulfillment rename); `fi_…` on inventory units (anticipates FulfillmentItem rename)
- [x] **Serializer Hierarchy**: `Admin::FulfillmentSerializer` extends `V3::FulfillmentSerializer`
- [x] **Security**: CanCanCan + OrderLock; nested under orders (store scoping inherited)
- [x] **Plan Conflicts**: `6.0-fulfillment-and-delivery.md` governs rename; no conflict with current code

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/shipment.rb                              ← ful_ prefix, state machine
spree/core/app/models/spree/shipment/custom_events.rb
spree/core/app/models/spree/shipment/webhooks.rb
spree/core/app/models/spree/inventory_unit.rb                        ← fi_ prefix

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/fulfillment_serializer.rb

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/orders/fulfillments_controller.rb

# Frontend (PENDING)
packages/dashboard/src/hooks/use-order-fulfillments.ts
# Fulfillments panel on order detail page ($orderId.tsx)
```

---

## Phase 1: Models + API (✅ Complete)

- `Spree::Shipment` with state machine, `ful_` prefix, concerns
- `Spree::InventoryUnit` with `fi_` prefix
- Admin API nested under orders: `index`, `show`, `update`, `fulfill`, `cancel`, `resume`, `split`
- Admin serializer

---

## Phase 2: SPA (PENDING)

- Fulfillments panel on order detail (`$orderId.tsx`)
- State-aware action buttons (fulfill/cancel/resume based on current state)
- Tracking number input on `fulfill`
- Split shipment dialog
- Hook: `use-order-fulfillments.ts`

---

## Phase 3: 6.0 — Renames (PENDING)

Per `6.0-fulfillment-and-delivery.md`:

- `Spree::Shipment` → `Spree::Fulfillment` (prefix `ful_` already set)
- `Spree::InventoryUnit` → `Spree::FulfillmentItem` (prefix `fi_` already set)
- `Spree::ShippingMethod` → `Spree::DeliveryMethod`
- `Spree::ShippingRate` → `Spree::DeliveryRate`
- Drop `Spree::ShippingCategory`
- `FulfillmentProvider` strategy per DeliveryMethod

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| InventoryUnit per-item granularity | Returns and partial fulfillment need item-level tracking | Order-level or line-item-level tracking cannot differentiate "2 of 3 units returned" |
| `ShipmentUpdateService` | Shipment updates ripple through rates, adjustments, and order totals | Direct `shipment.update` would leave adjustments stale and order totals incorrect |
