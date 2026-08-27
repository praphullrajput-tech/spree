---

description: "Task list — brownfield migration of Order Management (already implemented)"

---

# Tasks: Order Management

**Input**: Design documents from `specs/002-order-management/`

**Note**: This feature is already fully implemented in the codebase. Every task below is marked `[x]` (done) and documents what was built and where, for spec-kit traceability purposes — not as a forward work plan.

**Organization**: Tasks are grouped by actual component (model/updater/finders, Admin API v3, legacy admin, dashboard SPA) rather than by user story, since implementation predates this spec-kit adoption.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Backend stack: `Spree::Order` lives in `spree/core`, consumed by `spree/api` and `spree/admin` engines within the host Rails app
- [x] T002 Frontend stack: `packages/dashboard` React SPA consumes order data exclusively via `@spree/admin-sdk`'s `adminClient.orders`
- [x] T003 Baseline backend tests exist: `spree/core/spec/models/spree/order_spec.rb` (2917 lines, covers scopes/search/callbacks/validations/cancel/resume/approve/finalize)

---

## Phase 2: Foundational (Model, Updater, Finders)

- [x] T004 `[spree/core]` Core model `spree/core/app/models/spree/order.rb` — prefixed ID (`or_`), `status` (draft/placed/canceled) + legacy `state` checkout-flow columns, money validations, Ransack allowlists (`whitelisted_ransackable_attributes/_associations/_scopes`)
- [x] T005 `[spree/core]` Order concerns split by topic: `order/checkout.rb`, `order/currency_updater.rb`, `order/digital.rb`, `order/payments.rb`, `order/store_credit.rb`, `order/gift_card.rb`, `order/address_book.rb`, `order/webhooks.rb`
- [x] T006 `[spree/core]` `Spree::OrderUpdater` (`order_updater.rb`) — recalculates `item_total`/`shipment_total`/`adjustment_total`/`promo_total`/`total`, derives `payment_state`/`shipment_state`, persists via `update_columns` (no callback re-entrancy)
- [x] T007 `[spree/core]` Finders: `Spree::Orders::FindComplete` (lookup by user/number/prefix_id/token/store/email) and `Spree::Orders::FindCurrent` (customer's current incomplete order)
- [x] T008 `[spree/core]` `Spree::OrderCancellation` / `Spree::OrderApproval` associations (`has_many :cancellations, :approvals`) wired per `5.5-6.0-order-cancellation-and-approval.md`
- [x] T009 `[spree/api]` Ransack allowlist on `Spree::Order` covers admin-facing filters: `completed_at, email, number, state, status, payment_state, shipment_state, total, item_total, item_count, considered_risky, channel_id, currency` + associations `shipments, user, created_by, approver, canceler, promotions, bill_address, ship_address, line_items, store, channel, tags`

**Checkpoint**: Model/updater/finder foundation in place — all downstream components (API, legacy admin, SPA) build on this.

---

## Phase 3: Admin API v3 (Primary Interface) 🎯

**Goal**: Full CRUD + lifecycle transitions on orders via `Spree::Api::V3::Admin::OrdersController`

**Component Test**: `POST /api/v3/admin/orders` with `email`/`items`/addresses returns a draft order with `or_...` id; `PATCH .../complete`, `.../cancel`, `.../approve`, `.../resume` transition state; `POST .../resend_confirmation` republishes `order.completed`.

### Implementation

- [x] T010 `[API]` `spree/api/app/controllers/spree/api/v3/admin/orders_controller.rb` — `create` (via `Spree.order_create_service`), `update` (via `Spree.order_update_service`, wrapped in `with_order_lock`), `complete`, `cancel`, `approve`, `resume`, `resend_confirmation`
- [x] T011 `[API]` `Spree::Api::V3::OrderLock` concern — advisory locking around all mutating actions (`with_order_lock`) to prevent concurrent-write races
- [x] T012 `[API]` `authorize_resource!` maps state-transition actions (`complete/cancel/approve/resume/resend_confirmation`) to the `:update` CanCanCan permission
- [x] T013 `[API]` `order_create_params`/`order_update_params` permit flat fields matching serializer output 1:1 (read/write symmetry, constitution Principle III): `email, customer_id, user_id, currency, locale, market_id, channel_id, preferred_stock_location_id, customer_note, internal_note, metadata, tags, shipping_address/billing_address (create) or ship_address/bill_address (update), items`
- [x] T014 `[API]` `resolve_user` resolves `customer_id`/`user_id` params via `Spree.user_class.find_by_param!` (prefixed-ID aware)
- [x] T015 `[P]` `[API]` Store API serializer `spree/api/app/serializers/spree/api/v3/order_serializer.rb` — post-purchase order fields, money fields nulled for `hide_prices` guests
- [x] T016 `[API]` Admin serializer `spree/api/app/serializers/spree/api/v3/admin/order_serializer.rb` — extends Store serializer, adds `status, last_ip_address, considered_risky, internal_note, approver_id, canceler_id, created_by_id, customer_id, preferred_stock_location_id, canceled_at, approved_at, payment_total, tags, metadata, created_at/updated_at` + admin-serialized associations (adjustments, return_authorizations, reimbursements, payment_methods)
- [x] T017 `[P]` `[API]` Nested Admin API v3 controllers: `orders/adjustments_controller.rb`, `orders/fulfillments_controller.rb`, `orders/gift_cards_controller.rb`, `orders/items_controller.rb`, `orders/payments_controller.rb`, `orders/refunds_controller.rb`, `orders/store_credits_controller.rb`

**Checkpoint**: Admin API v3 order lifecycle is fully functional and is the sole data source for the dashboard SPA (constitution Principle II).

---

## Phase 4: Legacy Rails Admin (documented as-is, no new work)

**Goal**: Document existing legacy admin behavior for accuracy; not a target for new feature work per constitution Principle I.

### Implementation

- [x] T018 `[spree/admin]` `spree/admin/app/controllers/spree/admin/orders_controller.rb` — `index` (scoped to `current_store.orders.accessible_by(...).complete`, default sort `completed_at desc`), `show`, `new`, `create`, `edit` (redirects to show), `cancel`, `resend`, `destroy`
- [x] T019 `[P]` `[spree/admin]` Nested legacy controllers: `orders/adjustments_controller.rb`, `orders/billing_address_controller.rb`, `orders/contact_information_controller.rb`, `orders/customer_returns_controller.rb`, `orders/order_promotions_controller.rb`, `orders/payment_links_controller.rb`, `orders/return_authorizations_controller.rb`, `orders/shipping_address_controller.rb`, `orders/user_controller.rb`
- [x] T020 `[spree/admin]` `Spree::Admin::OrderSummaryPresenter` — assembles totals/adjustments breakdown rows (metadata, channel, market, locale, currency, subtotal, shipping, promo, manual/custom adjustments, tax, total, payment total, outstanding balance) for the order show page

**Checkpoint**: Legacy admin behavior documented; confirms no functional gap against the Admin API v3 for the purposes of this spec.

---

## Phase 5: Dashboard SPA (Admin API v3 Consumer)

**Goal**: React SPA order detail/list/create views backed exclusively by the Admin API v3.

### Implementation

- [x] T021 `[dashboard]` `packages/dashboard/src/hooks/use-order.ts` — `useOrder(orderId)` fetches via `adminClient.orders.get` with `expand: [items, fulfillments, fulfillments.delivery_method, fulfillments.stock_location, payments, payments.payment_method, billing_address, shipping_address, customer, created_by, canceler, approver, market, channel]`; `useOrderMutation` for chained/custom-error-handling mutations; `orderQueryKey` for cache key building
- [x] T022 `[P]` `[dashboard]` Routes: `routes/_authenticated/$storeId/orders/index.tsx` (list), `.../new.tsx` (create), `.../drafts.tsx` (draft-status filter), `.../$orderId.tsx` (detail)
- [x] T023 `[P]` `[dashboard]` `schemas/order.ts` (Zod schema/form values) and `tables/orders.tsx` (list table registration) — located but not individually verified line-by-line in this migration pass (flagged in spec.md Migration Notes)

**Checkpoint**: Dashboard SPA fully consumes Admin API v3 for order management; no direct Rails/model access found.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T024 Backend test suite: `cd spree/core && bundle exec rspec spec/models/spree/order_spec.rb` — passing per repository state at time of migration
- [x] T025 `docs/plans/` cross-references confirmed: `6.0-cart-order-split.md`, `6.0-normalize-state-to-status.md`, `5.5-6.0-order-cancellation-and-approval.md`, `6.0-split-adjustments.md` all bear on this feature's future evolution (see spec.md Module Impact)
- [x] T026 Gaps documented in `specs/002-order-management/spec.md` → Migration Notes: missing Admin API v3 integration spec coverage for `complete`/`approve`/`resume`/`resend_confirmation`, unresolved multi-market-same-currency tie-breaker, untested inventory-unit-unassigned shipment-state branch, unread dashboard SPA route internals

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2: model/updater/finders)** → **Admin API v3 (Phase 3)** is the critical path; the legacy admin (Phase 4) and dashboard SPA (Phase 5) both depend on Phase 2, and the SPA additionally depends on Phase 3 per constitution Principle II.
- Phases 3, 4, 5 were (historically) implementable independently once Phase 2 landed — legacy admin predates the Admin API v3 SPA, but both consume the same core model/updater.

## Notes

- All tasks are marked complete because this is a reverse-engineered record of existing code, not a forward implementation plan.
- `[P]` marks components that live in independent files with no direct dependency on sibling tasks in the same phase.
- Any future work in this area should start from `specs/002-order-management/spec.md` → Migration Notes rather than re-discovering these gaps.
