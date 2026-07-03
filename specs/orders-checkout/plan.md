# Implementation Plan: Orders & Checkout

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Models + API + SPA fully shipped; `use-orders.ts` hook missing; 6.0 Cart/Order split pending

---

## Summary

`Spree::Order` is the central transaction entity. It carries a checkout state machine (cart → address → delivery → payment → confirm → complete), a high-level `status` (draft/placed/canceled), and derived `payment_state` and `shipment_state` aggregates. `Spree::LineItem` records individual purchased items. The Admin API supports full CRUD plus action endpoints (complete, cancel, approve, resume, resend_confirmation). The Admin SPA has an orders list and order detail page. The 6.0 Cart/Order split will separate `status: cart` records into a distinct `Spree::Cart` model.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Checkout DSL** | Custom `Checkout` concern (not `state_machines-activerecord`) |
| **Scope** | Fully shipped; missing `use-orders.ts` hook; 6.0 split pending |

---

## Key Decisions

1. **Checkout state vs status.** The checkout state (`cart`/`address`/`delivery`/`payment`/`confirm`/`complete`) is a low-level workflow state managed by the `Checkout` concern DSL. `status` (`draft`/`placed`/`canceled`) is an admin-level classification. The two are related but independent.

2. **`payment_state` and `shipment_state` are aggregates.** They are computed from the order's payments and shipments respectively, not stored as separate state machines. The order serializer exposes both.

3. **Action endpoints over PUT transitions.** `complete`, `cancel`, `approve`, `resume`, `resend_confirmation` are POST endpoints on the order resource, not PATCH with a `status` field. This makes the intent explicit and allows server-side validation of each transition.

4. **`SingleStoreResource` for scoping.** Orders belong to a store; all controller scoping goes through `current_store.orders`. Cross-store access is blocked at the query level.

5. **`OrderLock` concern prevents concurrent mutation.** Multiple admin sessions editing the same order simultaneously could corrupt state. The controller locks the order record before mutations.

6. **No `use-orders.ts` hook — inline client call.** The orders list page calls `adminClient.orders.list()` directly in the component. This is inconsistent with other resources (products, customers use hooks). Should be extracted for testability.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Read/Write Symmetry**: Order fields serialized and accepted on write; computed fields (`payment_state`, `shipment_state`) are read-only
- [x] **Prefixed IDs**: `or_…` on orders; `li_…` on line items
- [x] **Serializer Hierarchy**: `Admin::OrderSerializer` extends `V3::OrderSerializer`
- [x] **Type Pipeline**: Typelizer + Zod regen done
- [x] **Security**: CanCanCan `can :manage, Spree::Order`; `OrderLock` prevents concurrent mutations; store-scoped
- [x] **Namespace**: `Spree::Order`, `Spree::LineItem`
- [x] **Plan Conflicts**: `6.0-cart-order-split.md` — Cart/Order split; `5.5-6.0-order-cancellation-and-approval.md` — cancellation/approval models (models shipped, API gap documented in `specs/order-approval-cancellation/`)

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/order.rb                                  ← or_ prefix, checkout DSL, SingleStoreResource
spree/core/app/models/spree/line_item.rb                              ← li_ prefix, price copy from variant

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/order_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/line_item_serializer.rb

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/orders_controller.rb    ← complete, cancel, approve, resume, resend_confirmation

# Frontend (✅ shipped)
packages/dashboard/src/routes/_authenticated/$storeId/orders/index.tsx
packages/dashboard/src/routes/_authenticated/$storeId/orders/$orderId.tsx
packages/dashboard/e2e/orders.spec.ts
# Missing:
packages/dashboard/src/hooks/use-orders.ts                            ← PENDING
```

---

## Phase 1: Core + API + SPA (✅ Complete)

- `Spree::Order` with checkout DSL, status, payment/shipment state aggregates, all concerns
- `Spree::LineItem` with price auto-copy, metafields
- Admin API: full CRUD + action endpoints + OrderLock
- Admin SPA: order list + detail page
- E2E: basic orders listing and navigation

---

## Phase 2: Missing Hook + 6.0 Cart Split (PENDING)

- Extract `use-orders.ts` hook from inline component calls
- `6.0-cart-order-split.md`: `Spree::Cart` as distinct model; `Spree::Order` represents placed orders only
- `status: cart` orders migrate to `Spree::Cart`
- `LineItem` gets `cart_id` FK alongside (or replacing) `order_id`

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Custom checkout DSL (not state_machines gem) | Checkout has complex conditional steps (skip delivery for digital orders, etc.) | `state_machines-activerecord` doesn't support conditional step skipping; the custom DSL gives full control |
| Two "state" concepts (checkout state + status) | Checkout state tracks the current step; status tracks the merchant-visible lifecycle | Collapsing both into one field would require mapping checkout states to merchant concepts — lossy |
