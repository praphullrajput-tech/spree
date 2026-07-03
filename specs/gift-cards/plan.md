# Implementation Plan: Gift Cards & Batches

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped

---

## Summary

`Spree::GiftCard` is a single-store monetary instrument with a state machine (`active → partially_redeemed → redeemed`; `active → canceled`), amount tracking (`amount`, `amount_used`, `amount_authorized`), and a unique code. `Spree::GiftCardBatch` enables bulk issuance: an admin specifies count, amount, prefix, and optional expiry; the batch auto-generates all cards via `after_create :generate_gift_cards`. Gift cards integrate into checkout as a payment method — tracked separately from order-level discounts. The feature is fully shipped with Admin API, Store API, SPA routes, hooks, and E2E tests.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **State machine** | `state_machines-activerecord`; column `state` (legacy name — see `6.0-normalize-state-to-status.md`) |
| **Money handling** | `DisplayMoney` concern + `Spree::LocalizedNumber.parse` for currency parsing |
| **Single-store** | `Spree::SingleStoreResource` concern |
| **Scope** | Full-stack; fully shipped |

---

## Key Decisions

1. **State machine column is `state`, not `status`.** Gift cards predate `6.0-normalize-state-to-status.md`. Rename to `status` is pending in 6.0.

2. **`amount_authorized` tracks concurrent in-checkout holds.** When a cart applies a gift card, `amount_authorized` is incremented (holds the balance in-checkout). On order completion, `amount_authorized` decrements and `amount_used` increments. On checkout abandonment or expiry, `amount_authorized` is released. This prevents two concurrent checkouts from double-spending the same card.

3. **Batch generation is synchronous via `after_create`.** Unlike promotion multi-codes (which use `after_commit`), gift card batch generation happens in `after_create` and is subject to the configured `Spree::Config[:gift_card_batch_limit]` to cap synchronous generation time.

4. **Currency-scoped.** A gift card's `currency` must match the cart's `currency`. No cross-currency redemption. Currency defaults to the store's default currency.

5. **Gift cards are not promotions.** They live under the Promotions nav section in the admin SPA (same parent route group) but are modeled separately — `Spree::GiftCard` vs `Spree::Promotion`. They are payment instruments, not discount adjustments.

6. **`GiftCardBatch` has a `limit` guard.** `Spree::Config[:gift_card_batch_limit]` prevents bulk creation of excessively large batches that would block the web process.

7. **Orders access gift cards via a nested controller.** `GET /admin/orders/:id/gift_cards` returns gift cards applied to the order — handled by `Admin::Orders::GiftCardsController`, nested under the orders resource.

---

## Constitution Check

- [x] **API-First**: Admin API and Store API exist before SPA consumed them
- [x] **Read/Write Symmetry**: `code`, `amount`, `currency`, `expires_at` serialized and accepted in `permitted_params`
- [x] **Prefixed IDs**: `gc_…` for gift cards, `gcb_…` for batches
- [x] **Serializer Hierarchy**: `Admin::GiftCardSerializer` extends `V3::GiftCardSerializer`
- [x] **Type Pipeline**: Typelizer + Zod regen after serializer changes
- [x] **Security**: CanCanCan `can :manage, Spree::GiftCard`; store-scoped via `SingleStoreResource`
- [x] **Namespace**: `Spree::GiftCard`, `Spree::GiftCardBatch` — `Spree.base_class` subclasses
- [x] **Plan Conflicts**: Reviewed `6.0-normalize-state-to-status.md` — `state` → `status` rename pending in 6.0; no active conflict today

---

## Project Structure

```text
# Backend — models
spree/core/app/models/spree/gift_card.rb
spree/core/app/models/spree/gift_card_batch.rb

# Backend — serializers
spree/api/app/serializers/spree/api/v3/gift_card_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/gift_card_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/gift_card_batch_serializer.rb

# Backend — controllers
spree/api/app/controllers/spree/api/v3/admin/gift_cards_controller.rb
spree/api/app/controllers/spree/api/v3/admin/gift_card_batches_controller.rb
spree/api/app/controllers/spree/api/v3/admin/orders/gift_cards_controller.rb

# Frontend
packages/dashboard/src/routes/_authenticated/$storeId/promotions/gift-cards.tsx
packages/dashboard/src/hooks/use-gift-cards.ts
packages/dashboard/e2e/gift-cards.spec.ts
```

---

## Phase 1: Core Gift Card System (✅ Complete)

- `Spree::GiftCard` model with state machine and amount tracking
- `Spree::GiftCardBatch` model with auto-generation
- Store API: apply/remove gift card on cart
- Admin API: full CRUD for gift cards and batches; nested on orders
- `Spree::SingleStoreResource` concern for store scoping
- Admin SPA route, hook, and E2E tests shipped

---

## Phase 2: 6.0 Pending

- Rename `state` column to `status` (per `6.0-normalize-state-to-status.md`)
