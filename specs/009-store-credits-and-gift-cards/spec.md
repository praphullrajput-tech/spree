# Feature Specification: Store Credits & Gift Cards

**Feature Branch**: `009-store-credits-and-gift-cards`

**Created**: 2026-08-24

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — `Spree::StoreCredit`, `Spree::GiftCard`, `Spree::GiftCardBatch`, associated services, Admin/Store API v3 controllers, and the `packages/dashboard` gift-card admin UI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin issues a store credit to a customer (Priority: P1)

A store admin views a customer's profile and grants them a store credit (e.g. as a goodwill refund or loyalty reward), specifying an amount, currency, and category.

**Why this priority**: Store credit is the base currency-like entity everything else (gift card redemption, order payment) is built on. Without it, gift cards cannot convert to spendable balance and orders cannot be paid down with credit.

**Independent Test**: Can be fully tested by creating a store credit via `POST /api/v3/admin/customers/:customer_id/store_credits` (or the legacy `Spree::Admin::StoreCreditsController#create`) and confirming the customer's `total_available_store_credit` increases.

**Acceptance Scenarios**:

1. **Given** a customer with no store credit, **When** an admin creates a store credit of amount 50.00 USD, **Then** the customer's available store credit for that store/currency becomes 50.00 and a `spree_store_credit_events` allocation record is created.
2. **Given** a store credit with `amount_used > 0`, **When** an admin attempts to change its `amount`, **Then** the request is rejected with a `store_credit_in_use` error (422).
3. **Given** a store credit with `amount_used.zero?` and `amount_authorized.zero?`, **When** an admin deletes it, **Then** it is soft-deleted (`acts_as_paranoid`).

---

### User Story 2 - Customer applies store credit to an order (Priority: P1)

A logged-in customer (or admin, on their behalf) applies available store credit toward an order's total during checkout.

**Why this priority**: This is the payment-side integration — store credit only has value if it can offset an order total. Core checkout flow.

**Independent Test**: `POST /api/v3/store/carts/:cart_id/store_credits` (authenticated) with an optional `amount`; when omitted, the service applies available credit up to the order total. Verify `order.total_applied_store_credit` reflects the created `Spree::Payment` sourced from the store credit.

**Acceptance Scenarios**:

1. **Given** a customer with $100 available store credit and a $30 order, **When** they apply store credit without specifying an amount, **Then** the order becomes `covered_by_store_credit?` and a payment is created for $30.
2. **Given** an order with store credit applied, **When** the customer removes it (`DELETE .../store_credits`), **Then** the corresponding store-credit payment(s) are invalidated/removed.
3. **Given** an order in a different currency than the store credit, **When** applying store credit, **Then** the application fails with a currency-mismatch error.

---

### User Story 3 - Admin bulk-issues gift cards via a batch (Priority: P2)

A store admin generates a batch of N gift card codes (e.g. for a promotional campaign or printed cards) sharing an amount, currency, prefix, and expiry.

**Why this priority**: Gift cards are the primary vehicle for pre-paid balance to enter the system (as opposed to admin-granted store credit). Batch generation is the main operational workflow for merchandising gift cards at scale.

**Independent Test**: `POST /api/v3/admin/gift_card_batches` with `codes_count`, `amount`, `prefix`; verify `codes_count` `Spree::GiftCard` records are created with unique codes matching the prefix. For counts above `Spree::Config[:gift_card_batch_web_limit]` (default web-inline threshold), verify the batch defers to `Spree::GiftCards::BulkGenerateJob` instead of generating inline.

**Acceptance Scenarios**:

1. **Given** `codes_count: 10` and `prefix: "SUMMER"`, **When** the batch is created, **Then** 10 gift cards are created inline with codes starting with `summer` (normalized lowercase) and status `active`.
2. **Given** `codes_count` exceeding `Spree::Config[:gift_card_batch_web_limit]`, **When** the batch is created, **Then** `Spree::GiftCards::BulkGenerateJob` is enqueued instead of blocking the request.
3. **Given** `codes_count` exceeding `Spree::Config[:gift_card_batch_limit]`, **When** the batch is created, **Then** validation fails.

---

### User Story 4 - Customer redeems a gift card on an order (Priority: P1)

A customer enters a gift card code on their cart/order; if valid (not expired, not already fully redeemed), its balance converts into a store credit on their account and/or is applied to the order.

**Why this priority**: This is the customer-facing redemption flow — the reason gift cards exist as a distinct, code-based entity rather than a plain store credit.

**Independent Test**: `POST /api/v3/store/carts/:cart_id/gift_cards` with `{ code }`; verify the gift card transitions from `active` toward `partially_redeemed`/`redeemed` and a `Spree::StoreCredit` is created with `originator: gift_card`.

**Acceptance Scenarios**:

1. **Given** an active, unexpired gift card code, **When** applied to a cart, **Then** `apply_gift_card` succeeds and the cart reflects the applied balance.
2. **Given** an expired gift card, **When** applied, **Then** the request fails with `gift_card_expired` (422).
3. **Given** an already-redeemed gift card, **When** applied again, **Then** the request fails with `gift_card_already_redeemed` (422).
4. **Given** a gift card code that doesn't exist for the current store, **When** applied, **Then** the request fails with `gift_card_not_found` (404).

---

### Edge Cases

- What happens when a store credit's `create_credit_record` runs with `Spree::Config.credit_to_new_allocation` true vs false? (New allocation record created vs. in-place `amount_used` decrement — both code paths exist and must stay behaviorally distinct.)
- How does the system handle voiding an authorization that was never captured? (`void` looks up the matching `AUTHORIZE_ACTION` event by `authorization_code`; if none is found, it errors rather than silently no-op'ing.)
- What happens when a gift card batch's `codes_count` is increased after creation (re-triggering `create_gift_cards`)? Only the delta (`codes_count - gift_cards.count`) is generated, so batches are idempotent/incrementally re-runnable.
- Gift cards are strictly single-store (`Spree::SingleStoreResource`) — no cross-store redemption.
- A gift card's `active?` is expiry-aware (`super && !expired?`) even though the persisted `state` column may still read `active` — `display_state` and the serializer's `status`/`active` attributes must be read through the model, not the raw column.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow admins to create, view, update, and soft-delete `Spree::StoreCredit` records scoped to a customer and a single store.
- **FR-002**: System MUST prevent editing the `amount` or deleting a store credit once any portion of it has been used (`amount_used > 0`).
- **FR-003**: System MUST support authorize/capture/void/credit lifecycle actions on store credit (used by the store-credit `Spree::PaymentMethod`), recording each as a `Spree::StoreCreditEvent`.
- **FR-004**: System MUST allow a customer (or admin on an order) to apply available store credit to an order/cart, either for a specific amount or automatically up to the order total, and to remove it.
- **FR-005**: System MUST allow admins to bulk-generate gift cards via `Spree::GiftCardBatch`, synchronously for small counts and via background job (`Spree::GiftCards::BulkGenerateJob`) above a configurable web-inline threshold.
- **FR-006**: System MUST generate unique, store-scoped gift card codes (auto-generated if not supplied, normalized to lowercase) and unique batch-prefixed codes.
- **FR-007**: System MUST allow a customer/admin to apply a gift card code to a cart/order, validating it is not expired and not already redeemed, and to remove it.
- **FR-008**: System MUST track gift card lifecycle via a state machine (`active → partially_redeemed → redeemed`, plus `active → canceled`), publishing `gift_card.redeemed` / `gift_card.partially_redeemed` lifecycle events.
- **FR-009**: System MUST link redeemed gift card balance to `Spree::StoreCredit` via a polymorphic `originator` association, so a gift card's balance becomes spendable as store credit.
- **FR-010**: System MUST expose money-formatted, hidden-price-aware serialized representations of both store credits and gift cards on the Store API, nulling display amounts when `hide_prices`/gated pricing is in effect.
- **FR-011**: System MUST prevent deleting a gift card that has been (partially) redeemed.
- **FR-012**: System MUST support metafields/custom fields on both `Spree::StoreCredit` and `Spree::GiftCard` (`Spree::Metafields` include).

### Key Entities *(include if feature involves data)*

- **Spree::StoreCredit**: A monetary balance (`amount`, `amount_used`, `amount_authorized`, `currency`) belonging to a `user` and a single `store`, optionally categorized (`StoreCreditCategory`) and optionally originated by a polymorphic `originator` (e.g. a redeemed `GiftCard`). Soft-deletable. Drives `Spree::Payment` records via the store-credit payment method.
- **Spree::StoreCreditEvent**: Immutable-ish audit trail of actions (`allocation`, `authorize`, `capture`, `void`, `credit`, `cancel`, `eligible`) taken against a store credit, including running `user_total_amount`.
- **Spree::GiftCard**: A code-based, store-scoped, prepaid balance with its own state machine (`active`/`partially_redeemed`/`redeemed`/`canceled`), optional `expires_at`, optional owning `user`, optional `batch`. Redemption produces a `Spree::StoreCredit` originated by the gift card.
- **Spree::GiftCardBatch**: A bulk-issuance request (`codes_count`, `amount`, `currency`, `prefix`, optional `expires_at`) that fans out into N `Spree::GiftCard` records, synchronously or via `BulkGenerateJob`.
- **Spree::StoreCreditCategory**: Simple lookup/label for grouping store credits (e.g. "Refund", "Loyalty", "Gift card").

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::StoreCredit`, `Spree::Order::StoreCredit` concern, `Spree::GiftCard`, `Spree::GiftCardBatch`, `Spree::GiftCards::BulkGenerateJob`, `Spree::Order::GiftCard` concern (`apply_gift_card`/`remove_gift_card`), `Spree.checkout_add_store_credit_service` / `Spree.checkout_remove_store_credit_service` |
| `spree/api` (Store/Admin API v3) | Yes | Store: `Store::Carts::{GiftCards,StoreCredits}Controller`, `Store::Customer::{GiftCards,StoreCredits}Controller`; Admin: `Admin::{GiftCards,GiftCardBatches,StoreCreditCategories}Controller`, `Admin::Customers::StoreCreditsController`, `Admin::Orders::{GiftCards,StoreCredits}Controller`; serializers `V3::{GiftCard,GiftCardBatch,StoreCredit}Serializer` + `V3::Admin::{GiftCard,GiftCardBatch,StoreCredit,StoreCreditCategory}Serializer` |
| `spree/admin` (legacy Rails admin) | Yes | `Spree::Admin::StoreCreditsController` (nested under customer/user) — still live, not yet ported to the SPA for the store-credit CRUD flow itself |
| `packages/dashboard` (admin SPA) | Yes | `routes/.../promotions/gift-cards.tsx`, `hooks/use-gift-cards.ts`, `hooks/use-customer-store-credits.ts`, `hooks/use-store-credit-categories.ts`, `schemas/gift-card.ts`, `schemas/store-credit.ts`, `tables/gift-cards.tsx` |
| `packages/dashboard-ui` / `dashboard-core` | No | Uses existing primitives (`ResourceTable`, `Sheet`, `CurrencySelect`, `StoreDatePicker`) — no new shared primitives added for this feature |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated types/resource methods for gift cards, gift card batches, store credits (`adminClient.customers.storeCredits.*`, gift card batch/list methods) |
| `docs/plans/` | Yes | See Migration Notes — `6.0-normalize-state-to-status.md` names `Spree::GiftCard` as a `state`→`status` rename target still pending |

### API Contract *(include if feature touches spree/api)*

- **Endpoints**:
  - `GET/POST /api/v3/admin/gift_cards`, `GET/PATCH/DELETE /api/v3/admin/gift_cards/:id`
  - `GET/POST /api/v3/admin/gift_card_batches`, `GET /api/v3/admin/gift_card_batches/:id`
  - `POST /api/v3/admin/orders/:order_id/gift_cards`, `DELETE /api/v3/admin/orders/:order_id/gift_cards/:id`
  - `POST/DELETE /api/v3/admin/orders/:order_id/store_credits`
  - `POST/PATCH/DELETE /api/v3/admin/customers/:customer_id/store_credits(/:id)`
  - `POST /api/v3/store/carts/:cart_id/gift_cards`, `DELETE /api/v3/store/carts/:cart_id/gift_cards/:id`
  - `POST/DELETE /api/v3/store/carts/:cart_id/store_credits`
  - `spree/api/app/controllers/spree/api/v3/store/customer/{gift_cards,store_credits}_controller.rb` (customer-facing read/list)
- **Serializer fields (read)**: GiftCard — `code, status, amount, amount_used, amount_authorized, amount_remaining, display_amount, display_amount_used, display_amount_remaining, currency, expires_at, redeemed_at, expired, active`. StoreCredit — `amount, amount_used, amount_remaining, display_amount, display_amount_used, display_amount_remaining, currency`. Admin variants extend these with `created_by`, `category`, timestamps, `memo`.
- **Auth**: Admin endpoints use JWT + CanCanCan (`ResourceController`/`BaseController` + `authorize_resource!`) or secret-key scopes (`scoped_resource :gift_cards` / `:store_credits`); Store API cart endpoints use publishable key (guest cart token) for gift cards, and require authentication (`require_authentication!`) for store credit application since store credit is tied to a logged-in customer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Admin can issue a store credit to a customer and see the updated available balance reflected within one page interaction (no manual refresh needed).
- **SC-002**: A gift card batch of up to the web-inline limit (`Spree::Config[:gift_card_batch_web_limit]`) completes synchronously within a single HTTP request; larger batches return immediately and complete asynchronously without blocking the admin UI.
- **SC-003**: 100% of gift card codes generated within a store are unique (`store_id` scoped uniqueness validation + prefix-scoped uniqueness at insert time).
- **SC-004**: An expired or already-redeemed gift card is rejected with a specific, translatable error code (`gift_card_expired` / `gift_card_already_redeemed`) rather than a generic failure, on 100% of redemption attempts.

## Assumptions

- "Store Credits & Gift Cards" is treated as one feature area because gift card redemption is implemented as a store-credit-issuing mechanism (`GiftCard has_many :store_credits, as: :originator`) — they are not independent subsystems in this codebase.
- The legacy Rails admin `Spree::Admin::StoreCreditsController` (customer-nested) remains the canonical UI for store-credit CRUD; the SPA's gift-card page and `use-customer-store-credits` hook cover gift cards fully and store credits partially (customer-profile panel), consistent with the gradual Rails-admin-to-SPA migration described in `docs/plans/6.0-admin-spa.md`.
- `Spree::StoreCreditCategory` and its API surface (`Admin::StoreCreditCategoriesController`, `Admin::StoreCreditCategorySerializer`) are treated as supporting infrastructure for this feature, not a separate feature.
- Gift card "batches" and standalone (non-batch) gift cards share the same `Spree::GiftCard` model; a batch is optional (`belongs_to :batch, optional: true`).

## Migration Notes

- **Pending rename**: `docs/plans/6.0-normalize-state-to-status.md` targets renaming `state` → `status` across several models; `Spree::GiftCard` still uses a `state` column/state_machine (`state_machine :state, initial: :active`) as of this migration. The GiftCard serializer already exposes a computed `status` attribute (derived from `display_state`), so the API surface is forward-compatible, but the underlying column/state machine rename is not yet done. This constraint from the plan applies to any future work on this feature.
- **No dedicated data-model diagram/API contracts files exist** for this feature pre-migration; this spec reconstructs the contract from controller/serializer code directly rather than from a `docs/plans/` entry — no `docs/plans/*.md` is dedicated solely to store credits/gift cards (they appear only as line items or as the rename target above).
- **Gap**: No RSpec file paths were enumerated during this migration (out of scope for a spec/plan/tasks reverse-engineering pass) — `spree/core/spec/models/spree/{store_credit,gift_card,gift_card_batch}_spec.rb` and `spree/api/spec/integration/**gift_card**` / `**store_credit**` are assumed to exist per repo convention but were not individually verified line-by-line.
- **Gap**: The legacy storefront (non-SPA) gift-card/store-credit checkout UI (if any, outside `packages/dashboard`) was not investigated — this migration covers only the Admin/Store API v3 + `packages/dashboard` admin surface plus core models.
- **Gap**: Exact `Spree::Config[:gift_card_batch_web_limit]` and `Spree::Config[:gift_card_batch_limit]` default values were not read from `spree/core/lib/spree/app_configuration.rb` — referenced by name only, values not confirmed.
