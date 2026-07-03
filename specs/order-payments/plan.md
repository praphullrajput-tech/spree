# Implementation Plan: Order Payments

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Models + API shipped; dashboard SPA pending

---

## Summary

`Spree::Payment` is the record of a payment attempt against an order. It has a state machine (checkout → processing → pending/completed/failed/void/invalid), tracks authorized vs captured amounts, stores AVS/CVV responses, and carries a polymorphic `source` (CreditCard, StoreCredit, GiftCard). The Admin API nested under orders supports `index`, `show`, `create`, `capture`, and `void`. The Admin SPA has no payment panel on the order detail page yet — legacy Rails admin handles capture/void.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **State machine** | `state_machines-activerecord` gem |
| **Scope** | Models + API complete; SPA pending |

---

## Key Decisions

1. **State machine is the source of truth.** Transitions (`capture!`, `void!`, `complete!`) are defined on the model. Controllers call the service/transition and return the updated state — they do not set `state` directly.

2. **`captured_amount` separate from `amount`.** Auth-then-capture stores the authorized `amount` at creation; `captured_amount` is updated when capture completes. This supports partial capture.

3. **Polymorphic source.** `source_type` + `source_id` point to whatever object funded the payment (CreditCard, StoreCredit, GiftCard). The serializer reflects the source type; controllers accept `source_id` (prefixed) for off-session charges.

4. **Nested under orders.** Payments are always in the context of an order; a standalone payments endpoint would be ambiguous. The nested route enforces scope.

5. **`PaymentSession` for async gateways.** Some gateways (e.g., 3DS flows) require async confirmation. `PaymentSession` (`ps_…`) tracks the gateway-side session; once confirmed, the parent Payment transitions to `pending` then `completed`.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Read/Write Symmetry**: `amount`, `source_id`, `payment_method_id` accepted; same names returned
- [x] **Prefixed IDs**: `py_…` on payments; `ps_…` on sessions; `pss_…` on setup sessions
- [x] **Serializer Hierarchy**: `Admin::PaymentSerializer` (admin-only)
- [x] **Type Pipeline**: Typelizer + Zod regen after serializer changes
- [x] **Security**: CanCanCan `can :manage, Spree::Payment`; scoped to order's store
- [x] **Namespace**: `Spree::Payment`, `Spree::PaymentSession`, `Spree::PaymentSetupSession`
- [x] **Plan Conflicts**: None; Cart/Order split (`6.0-cart-order-split.md`) may affect `order_id` FK in 6.0

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/payment.rb                               ← state machine, captured_amount, source polymorphic
spree/core/app/models/spree/payment/processing.rb                    ← capture/void/purchase gateway calls
spree/core/app/models/spree/payment/webhooks.rb                      ← async gateway webhook handling
spree/core/app/models/spree/payment/gateway_options.rb               ← gateway call builder
spree/core/app/models/spree/payment_session.rb                       ← async session tracking
spree/core/app/models/spree/payment_setup_session.rb                 ← async source tokenization
spree/core/app/models/spree/credit_card.rb                           ← polymorphic source

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/payment_serializer.rb

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/orders/payments_controller.rb

# Frontend (PENDING)
packages/dashboard/src/hooks/use-order-payments.ts                   ← TanStack Query wrappers
# Order detail payments panel (embedded in $orderId.tsx)
```

---

## Phase 1: Models + API (✅ Complete)

- `Spree::Payment` with full state machine + `captured_amount` + AVS/CVV fields
- `PaymentSession` + `PaymentSetupSession` for async flows
- `CreditCard` as polymorphic source
- Admin API nested under orders: `index`, `show`, `create`, `capture`, `void`
- Admin serializer with all fields

---

## Phase 2: SPA Dashboard (PENDING)

- Payments panel on order detail page
- Capture/void buttons (state-aware — only shown when transition is valid)
- Payment history timeline
- Hook: `use-order-payments.ts`
- i18n keys under `admin.orders.payments.*`

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Two amount fields (`amount` + `captured_amount`) | Auth-then-capture is a real pattern; partial capture requires separate tracking | Single `amount` field would conflate authorization with settlement |
| `PaymentSession` indirection | Async gateways (3DS, bank redirect) need a server-side session record tied to the gateway's session | Storing gateway state on the Payment directly mixes async state with the payment lifecycle |
