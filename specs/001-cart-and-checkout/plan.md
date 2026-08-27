# Implementation Plan: Cart & Checkout

**Branch**: `001-cart-and-checkout` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-cart-and-checkout/spec.md`

**Note**: This is a brownfield/migrated plan — reconstructed from existing code, not authored ahead of implementation. It documents the architecture as found, for future spec-kit-driven work to build against.

## Summary

Cart & Checkout is Spree's core commerce loop: build a cart via `Spree::Cart::*` / `Spree::Carts::*` service objects, progress an order through a state-machine-driven checkout (`cart → address → delivery? → payment? → confirm? → complete` in `Spree::Order::Checkout`), and expose both to the Store API v3 (`carts` resource family) for storefront use, plus a parallel admin-facing `Spree::Orders::*` service family for back-office order creation/editing. A newer `Spree::Checkout::Registry`/`Step`/`Requirement` layer sits alongside the state machine as a pluggable, stable requirements contract anticipating the Cart/Order model split (`docs/plans/6.0-cart-order-split.md`).

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`) — backend only; no frontend/SPA involvement was found for this feature (admin order editing still uses the legacy Rails admin, not `packages/dashboard`).

**Primary Dependencies**: `state_machines-activerecord` (checkout state machine in `Order::Checkout`), CanCanCan (cart authorization in `CartResolvable`), Ransack (order/line item filtering), Alba serializers (Store API v3 cart/checkout responses), `Spree::Dependencies` registry (swappable `cart_add_item_service`, `cart_remove_item_service`, `cart_update_service`, `carts_complete_service`, etc.).

**Storage**: PostgreSQL (production) / SQLite3 (test default) via ActiveRecord — no foreign key constraints, per migration conventions; order/line-item/address/shipment/payment tables predate this reverse-engineered spec.

**Testing**: RSpec + Factory Bot. Found at `spree/core/spec/services/spree/{cart,carts,checkout,addresses,orders}/*_spec.rb` and `spree/core/spec/models/spree/order/checkout_spec.rb` (state machine), `spree/core/spec/models/spree/checkout/{registry,requirements}_spec.rb` (pluggable requirements layer). No Vitest/Playwright coverage exists because no frontend code was found for this feature.

**Target Platform**: Rails engine gems (`spree_core`, `spree_api`) consumed by a Spree host app (`server/`, cloned from `spree-starter`); Store API v3 consumed by any client via `@spree/sdk`.

**Project Type**: Monorepo — Ruby gems only for this feature (`spree/core`, `spree/api`); `packages/sdk` generated types are a downstream consumer, not hand-written for this feature.

**Performance Goals**: Not specified in code; no explicit SLAs found in comments or specs. `Cart::Recalculate` runs on nearly every cart mutation and is the highest-frequency path — no load/perf tests were found covering it. [NEEDS CLARIFICATION: no documented perf target]

**Constraints**: Checkout `complete` transition must be safe against concurrent stock/price changes (guarded by `ensure_line_item_variants_are_not_discontinued` / `ensure_line_items_are_in_stock` before-transition callbacks) but `Orders::Complete` (admin) documents an external-locking requirement (`Api::V3::OrderLock#with_order_lock`) it does not itself enforce.

**Scale/Scope**: 13 `Cart::*` services, 4 `Carts::*` services, 8 `Checkout::*` services + 4 pluggable-requirements classes, 3 `Addresses::*` services, 9 `Orders::*` services, 1 state machine module (`Order::Checkout`, ~310 lines) — roughly 1,650 lines of service-layer code plus the state machine and `order_contents.rb` facade.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (services, state machine, models) and `spree/api` (Store API v3 `carts` resource controllers + `CartResolvable` concern). No boundary crossing found — `spree/api` controllers call `spree/core` services exclusively through the `Spree::Dependencies` registry (`Spree.cart_add_item_service`, `Spree::Dependencies.carts_complete_service`, etc.), never reaching into ActiveRecord directly from the controller layer. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: N/A — no `packages/dashboard` code was found touching this feature; admin order editing still runs through the legacy Rails admin controller (`spree/admin/app/controllers/spree/admin/checkouts_controller.rb`), which per constitution Principle I is a phase-out target, not a place for new SPA work. **Pass (nothing to violate).**
- **III. Read/Write Field Symmetry**: Confirmed — `carts_controller.rb#permitted_params` accepts exactly the field set the serializer returns (`email`, `customer_note`, `market_id`, `currency`, `locale`, `shipping_address`/`billing_address` (nested), `metadata`, `items[]`). No renamed-field mapping was found between read and write. **Pass.**
- **IV. Test-Backed**: RSpec covers most services (26+ spec files enumerated in spec.md's Migration Notes), but several services have no dedicated spec (`Cart::Create`, `Cart::Recalculate`, `Cart::Update`, `Cart::EstimateShippingRates`, `Checkout::Complete`, `Checkout::Next`, `Addresses::Create`, `Orders::BuildShipments`, `Orders::UpdateContactInformation`). **Partial — logged as a gap, not a blocking violation for this migrated spec since the feature already ships; any future change to these specific services MUST add the missing spec per Principle IV.**
- **V. Translations and Prefixed IDs**: N/A for i18next (no dashboard UI). Prefixed IDs ARE used correctly — `CartResolvable` resolves via `find_by_prefix_id!`, and all cart/order/address/variant IDs surfaced through the Store API are prefixed. **Pass.**
- **VI. `docs/plans/` for Architectural Changes**: Applies — this feature is directly governed by `docs/plans/6.0-cart-order-split.md` (the eventual Cart/Order model separation this dual `Cart::*`/`Carts::*` namespace anticipates) and `docs/plans/6.0-stock-reservations.md` (stock reservation calls threaded through nearly every `Cart::*` service). Both plans' "Constraints on Current Work" sections bind any future change to this area. **Pass — existing plan entries already cover it; no new plan required for this reverse-engineering pass.**

No violations requiring Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/001-cart-and-checkout/
├── spec.md               # Reverse-engineered feature spec (this pass)
├── plan.md               # This file
└── tasks.md              # Reverse-engineered task list (all marked complete)
```

No `research.md`, `data-model.md`, `contracts/`, or `quickstart.md` were generated — this is a migrated/reverse-engineered plan for already-shipped code, not a forward `/speckit-plan` run.

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/
├── app/models/spree/order.rb                          # includes Order::Checkout; line_items/shipments/payments/adjustments associations
├── app/models/spree/order/checkout.rb                  # the checkout state machine (cart→address→delivery→payment→confirm→complete)
├── app/models/spree/checkout/registry.rb                # pluggable step/requirement registration + ordering
├── app/models/spree/checkout/step.rb                    # Step value object
├── app/models/spree/checkout/requirement.rb              # Requirement value object
├── app/models/spree/checkout/requirements.rb             # aggregates DefaultRequirements + registered steps/requirements
├── app/models/spree/checkout/default_requirements.rb     # built-in per-step requirement checks
├── app/models/spree/order_contents.rb                   # legacy facade delegating to Cart::* services
├── app/services/spree/cart/{add_item,associate,change_currency,create,destroy,empty,estimate_shipping_rates,recalculate,remove_item,remove_line_item,remove_out_of_stock_items,set_quantity,update}.rb
├── app/services/spree/carts/{create,update,complete,upsert_items}.rb   # newer plural namespace, actually called by the Store API v3 controllers
├── app/services/spree/checkout/{add_store_credit,advance,complete,get_shipping_rates,next,remove_store_credit,select_shipping_method,update}.rb
├── app/services/spree/addresses/{create,update,helper}.rb
├── app/services/spree/orders/{approve,build_shipments,cancel,complete,create,create_user_account,update,update_contact_information,upsert_items}.rb
└── spec/services/spree/{cart,carts,checkout,addresses,orders}/*_spec.rb, spec/models/spree/order/checkout_spec.rb, spec/models/spree/checkout/{registry,requirements}_spec.rb

# spree/api — Store REST API v3
spree/api/
├── app/controllers/concerns/spree/api/v3/cart_resolvable.rb           # prefixed-ID + CanCanCan cart resolution for the JSON API
├── app/controllers/spree/api/v3/store/carts_controller.rb             # create/show/update/destroy/associate/complete + permitted_params
├── app/controllers/spree/api/v3/store/carts/{items,discount_codes,gift_cards,fulfillments,payments,payment_sessions,store_credits}_controller.rb
└── config/routes.rb                                                    # nested carts/* resource routes

# spree/core — storefront session/cookie cart resolution (distinct code path from CartResolvable)
spree/core/lib/spree/core/controller_helpers/order.rb                  # current_order, associate_user, set_current_order, order_includes
```

**Structure Decision**: Backend-only, split across two gems: `spree/core` owns the domain logic (cart/checkout/address/order services + the checkout state machine + the pluggable requirements registry), `spree/api` owns the Store API v3 HTTP surface that drives it. No `packages/*` frontend work is part of this feature as currently built — `packages/sdk`'s generated `Cart`/`LineItem`/`Address`/`Payment` types are a downstream, auto-generated consumer of the Alba serializers behind these controllers, not hand-authored feature code.

## Complexity Tracking

> No constitution violations were found requiring justification. Table intentionally left empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
