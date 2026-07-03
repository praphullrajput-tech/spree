# Implementation Plan: Store Credits

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped; no dedicated E2E tests

---

## Summary

`Spree::StoreCredit` is a balance-based credit instrument issued to customers. It tracks `amount`, `amount_used`, and `amount_authorized` to prevent double-spending. Lifecycle actions (VOID, CANCEL, CREDIT, CAPTURE, ELIGIBLE, AUTHORIZE, ALLOCATION) are constants on the model; transitions create `StoreCreditEvent` records for an immutable audit log. `StoreCredit` implements `Spree::PaymentMethod::StoreCredit` as a payment source at checkout. The Admin API has three surfaces: nested under customers (CRUD), nested under orders (add/remove during checkout), and a standalone categories endpoint.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Store ownership** | `Spree::SingleStoreResource` |
| **Scope** | Fully shipped; no dedicated E2E |

---

## Key Decisions

1. **Three-column balance tracking.** `amount` (total issued), `amount_authorized` (reserved at checkout), `amount_used` (permanently consumed). This prevents over-spending: authorize reduces available balance during checkout; capture converts authorized to used; void releases authorized back to available.

2. **Events are immutable audit trail.** Every balance change creates a `StoreCreditEvent` record with action, amount, user total, and optional originator. Events are never updated or deleted (paranoid soft-delete only for disaster recovery).

3. **`exposed_events` scope filters internal events.** `ELIGIBLE` and `AUTHORIZE` actions are internal state transitions; they are filtered from the API response to avoid confusing merchants.

4. **`Spree::StoreCreditCategory` controls non-expiring behavior.** The `GIFT_CARD_CATEGORY_NAME` constant identifies gift-card credits that never expire. Categories also provide display labels in the admin.

5. **`PaymentMethod::StoreCredit` integrates with checkout.** The payment method implementation calls `authorize` on the store credit during checkout; `capture` on order completion; `void` on cancellation. This follows the same interface as gateway payment methods.

6. **Three API surfaces.** Customers surface (CRUD), orders surface (add/remove as payment during checkout), and categories surface (standalone CRUD). This reflects the three contexts where store credits are managed.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Read/Write Symmetry**: `amount`, `memo`, `expires_at`, `category_id` serialized and accepted
- [x] **Prefixed IDs**: `credit_…` (StoreCredit), `scevt_…` (StoreCreditEvent), `sccat_…` (StoreCreditCategory)
- [x] **Serializer Hierarchy**: `Admin::StoreCreditSerializer` extends base serializer
- [x] **Security**: CanCanCan; store-scoped via SingleStoreResource; `amount_used` guard on delete
- [x] **Namespace**: `Spree::StoreCredit`, `Spree::StoreCreditEvent`, `Spree::StoreCreditCategory`

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/store_credit.rb                          ← credit_ prefix, SingleStoreResource
spree/core/app/models/spree/store_credit_event.rb                    ← scevt_ prefix, immutable audit log
spree/core/app/models/spree/store_credit_category.rb                 ← sccat_ prefix
spree/core/app/models/spree/store_credit_type.rb
spree/core/app/models/spree/payment_method/store_credit.rb           ← payment method integration
spree/core/app/models/spree/order/store_credit.rb                    ← order concern
spree/core/app/models/spree/reimbursement_type/store_credit.rb       ← reimbursement strategy

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/store_credit_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/store_credit_category_serializer.rb

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/customers/store_credits_controller.rb
spree/api/app/controllers/spree/api/v3/admin/orders/store_credits_controller.rb
spree/api/app/controllers/spree/api/v3/admin/store_credit_categories_controller.rb

# Frontend (✅ shipped)
packages/dashboard/src/hooks/use-customer-store-credits.ts
packages/dashboard/src/hooks/use-store-credit-categories.ts
# Store credit section in customer detail ($customerId.tsx)
```

---

## Phase 1: Core + API + SPA (✅ Complete)

- StoreCredit + Event + Category models
- All three API surfaces (customers, orders, categories)
- Dashboard: store credit section in customer detail
- Hooks: `use-customer-store-credits.ts`, `use-store-credit-categories.ts`

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Three-column balance (`amount`/`amount_authorized`/`amount_used`) | Checkout reserves credit before capture; prevents double-spending during concurrent checkouts | Two-column design (`amount`/`used`) cannot represent "reserved but not yet captured" state — race condition under concurrent checkouts |
| Three API surfaces | Credits are managed per-customer (CRUD), added to orders (checkout), and organized by category (settings) — three distinct actor contexts | Single endpoint would require `resource_type` routing logic or context inference, which is error-prone |
