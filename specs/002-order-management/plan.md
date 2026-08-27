# Implementation Plan: Order Management

**Branch**: `002-order-management` | **Date**: 2026-08-25 | **Spec**: `specs/002-order-management/spec.md`

**Input**: Feature specification from `specs/002-order-management/spec.md`

**Note**: This is a brownfield reconstruction — the feature already exists in the codebase. This plan documents the actual implemented architecture rather than a forward-looking design.

## Summary

Order Management covers the full lifecycle of `Spree::Order` — draft creation, item/address/payment attachment, totals recalculation, checkout-flow state transitions, cancellation/resumption/approval, and read access for admins — spanning `spree/core` (model + updater + finders), `spree/api` (Admin API v3 controllers/serializers), the legacy `spree/admin` Rails engine (being phased out), and the `packages/dashboard` SPA (order detail/list/new routes via `@spree/admin-sdk`).

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api` + `spree/admin`) and TypeScript (React SPA, `packages/dashboard`)

**Primary Dependencies**: Backend — CanCanCan (authorization), Ransack (filtering/search allowlists on `Spree::Order`), Pagy (pagination), Alba (`Spree::Api::V3::OrderSerializer` / `Admin::OrderSerializer`), `state_machines-activerecord` (checkout flow state machine on legacy `state` column), `acts_as_taggable_on` (order tags). Frontend — TanStack Query (`useOrder`/`useOrderMutation` in `hooks/use-order.ts`), `@spree/admin-sdk` (`adminClient.orders`).

**Storage**: PostgreSQL (production) / SQLite3 (backend spec default) via ActiveRecord; `spree_orders` table with prefixed ID (`or_`), no FK constraints.

**Testing**: RSpec + Factory Bot (`spree/core/spec/models/spree/order_spec.rb`, 2917 lines — covers scopes, search, callbacks, validations, cancel/resume/approve, `finalize!`); no Admin API v3 orders integration spec was located in the files reviewed for this pass (see spec.md Migration Notes).

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`, `spree/admin`) consumed by a Spree host app; `packages/dashboard` React SPA consuming the Admin API v3.

**Project Type**: Monorepo — Ruby gems `spree/core`, `spree/api`, `spree/admin`; TypeScript package `packages/dashboard` (+ generated types in `packages/admin-sdk`).

**Performance Goals**: Not explicitly specified in code/comments reviewed; `OrderUpdater#update_adjustment_total` batches line-item/shipment/adjustment sums into three aggregate queries (rather than N+1 per-record sums) — an implicit performance constraint worth preserving in any refactor.

**Constraints**: Per-order advisory locking (`Spree::Api::V3::OrderLock` / `with_order_lock`) serializes concurrent mutating Admin API requests against the same order. Store-scoping (`Spree::SingleStoreResource`) is mandatory on every query path — `current_store.orders`, never bare `Spree::Order`.

**Scale/Scope**: Whole-order lifecycle — not a single screen or endpoint. Touches 1 core model + 8 concerns, 1 updater, 2 finders, 1 presenter, 2 controllers (legacy + v3) with ~9 legacy nested controllers and ~7 v3 nested controllers, 2 serializers, 4 dashboard routes + 1 hook.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (model/updater/finders), `spree/api` (Admin API v3), `spree/admin` (legacy — no new work planned there, only documented as-is), and `packages/dashboard` (consumes Admin API v3 only, via `@spree/admin-sdk`). No direct cross-boundary reach found — the SPA goes through `adminClient.orders`, not Rails models. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: Confirmed — `hooks/use-order.ts` calls `adminClient.orders.get(...)` exclusively; no server-rendered HTML scraping or direct Rails model access from `packages/dashboard`. **Pass.**
- **III. Read/Write Field Symmetry**: `Spree::Api::V3::Admin::OrdersController#order_update_params`/`#order_create_params` permit exactly the field names the serializer exposes (`customer_note`, `internal_note`, `currency`, `locale`, `market_id`, `channel_id`, `preferred_stock_location_id`, `tags`, `metadata`, `items`, `ship_address`/`bill_address`). Legacy-name bridges (`customer_note` ← `special_instructions`, `customer_id` ← `user_id`) live on the model via `alias_attribute`, not in the controller. **Pass.**
- **IV. Test-Backed**: RSpec model spec exists and is substantial (`order_spec.rb`, 2917 lines). No Admin API v3 integration spec for `orders_controller.rb` was located in this pass (flagged in spec.md Migration Notes) — this is a **documented gap**, not a plan violation, since this is a reverse-engineering/documentation task, not new implementation.
- **V. Translations and Prefixed IDs**: All order-related IDs in the Admin API v3 serializer are prefixed (`or_`, plus `customer_id`, `market_id`, `channel_id`, `approver_id`, `canceler_id`, `created_by_id`, `preferred_stock_location_id` via `&.prefixed_id`). Dashboard SPA i18n usage was not verified line-by-line in this pass (routes not opened) — **N/A for this migration pass**, flag for follow-up.
- **VI. `docs/plans/` for Architectural Changes**: This feature is governed by multiple active plans — `6.0-cart-order-split.md` (Cart/Order model separation, pending — the single `Spree::Order` model documented here is the pre-split state), `6.0-normalize-state-to-status.md` (the `status` column alongside legacy `state` reflects this in-flight rename), `5.5-6.0-order-cancellation-and-approval.md` (shipped — `OrderCancellation`/`OrderApproval` models are consumed here), `6.0-split-adjustments.md` (pending — `Adjustment` polymorphism is still in use in `OrderSummaryPresenter`/`update_adjustment_total`). This spec/plan pair references these rather than replacing them, per Principle VI. **Pass — no new plan entry needed since this is documentation of existing state, not a new architectural change.**

No violations requiring Complexity Tracking — this plan documents existing architecture, it does not propose new complexity.

## Project Structure

### Documentation (this feature)

```text
specs/002-order-management/
├── plan.md              # This file
├── spec.md              # Feature specification (migrated)
└── tasks.md             # Task breakdown (migrated, all marked complete)
```

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/
├── app/models/spree/order.rb                       # Spree::Order — core model, checkout_flow, validations, scopes
├── app/models/spree/order/checkout.rb               # Checkout state-machine concern
├── app/models/spree/order/currency_updater.rb        # Currency-change handling, market resolution
├── app/models/spree/order/digital.rb                 # Digital-fulfillment predicates
├── app/models/spree/order/payments.rb                # Payment-related order methods
├── app/models/spree/order/store_credit.rb            # Store credit application
├── app/models/spree/order/gift_card.rb                # Gift card application
├── app/models/spree/order/address_book.rb             # Address book integration
├── app/models/spree/order/webhooks.rb                 # Outbound webhook triggers (order placed/canceled/resumed)
├── app/models/spree/order_updater.rb                  # Totals + payment_state/shipment_state recalculation
├── app/finders/spree/orders/find_complete.rb          # Lookup completed orders by user/number/prefix_id/token/store/email
├── app/finders/spree/orders/find_current.rb           # Lookup customer's current incomplete order
├── app/finders/spree/orders/finder_helper.rb          # Shared includes for finders
└── spec/models/spree/order_spec.rb                    # Model spec — scopes, search, cancel/resume/approve, finalize!

# spree/api — Admin & Store REST API v3
spree/api/
├── app/controllers/spree/api/v3/admin/orders_controller.rb          # create/update/complete/cancel/approve/resume/resend_confirmation
├── app/controllers/spree/api/v3/admin/orders/adjustments_controller.rb
├── app/controllers/spree/api/v3/admin/orders/fulfillments_controller.rb
├── app/controllers/spree/api/v3/admin/orders/gift_cards_controller.rb
├── app/controllers/spree/api/v3/admin/orders/items_controller.rb
├── app/controllers/spree/api/v3/admin/orders/payments_controller.rb
├── app/controllers/spree/api/v3/admin/orders/refunds_controller.rb
├── app/controllers/spree/api/v3/admin/orders/store_credits_controller.rb
├── app/serializers/spree/api/v3/order_serializer.rb                 # Store API — post-purchase order data
└── app/serializers/spree/api/v3/admin/order_serializer.rb            # Admin API — extends Store serializer, adds back-office fields

# spree/admin — legacy Rails admin (being phased out, documented as-is, no new work)
spree/admin/
├── app/controllers/spree/admin/orders_controller.rb                  # index/show/new/create/edit/cancel/resend/destroy
├── app/controllers/spree/admin/orders/{adjustments,billing_address,contact_information,customer_returns,order_promotions,payment_links,return_authorizations,shipping_address,user}_controller.rb
└── app/presenters/spree/admin/order_summary_presenter.rb              # Totals/adjustments breakdown view-model

# packages/dashboard — admin SPA routes/forms
packages/dashboard/src/
├── routes/_authenticated/$storeId/orders/{index,new,drafts,$orderId}.tsx
├── hooks/use-order.ts             # useOrder (detail query, expand[]), useOrderMutation, orderQueryKey
├── schemas/order.ts
└── tables/orders.tsx

# packages/admin-sdk — generated types (regenerated, not hand-edited)
packages/admin-sdk/src/types/generated/{Order,LineItem,Payment,Fulfillment,Adjustment,Discount,Reimbursement,ReturnAuthorization}.ts
```

**Structure Decision**: This plan documents an already-implemented, full-stack feature spanning all four backend/frontend module groups per the spec.md Module Impact table. No new module boundaries are proposed; the legacy `spree/admin` engine is documented for historical/current-behavior accuracy only, consistent with constitution Principle I's guidance not to add new features there.

## Complexity Tracking

*No violations — not applicable to this brownfield documentation pass.*
