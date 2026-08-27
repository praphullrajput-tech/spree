---
description: "Task list for the already-implemented Cart & Checkout feature (brownfield migration — all tasks reflect existing, shipped code)"
---

# Tasks: Cart & Checkout

**Input**: Design documents from `/specs/001-cart-and-checkout/` (spec.md, plan.md — reverse-engineered)

**Prerequisites**: plan.md, spec.md (both migrated from existing code)

**Status**: This feature is already fully implemented and in production. Every task below is marked `[x]` and organized by the actual components found in `spree/core` and `spree/api`, not by a forward-looking phase plan. Gaps (missing tests) are called out explicitly rather than hidden.

**Organization**: Tasks are grouped by the real architectural components discovered during research — the checkout state machine, the pluggable requirements registry, the two cart service namespaces, checkout services, address services, and admin order services — followed by the API surface and its test coverage.

## Format: `[ID] [P?] [Component] Description`

- **[P]**: Independent of other tasks in this list (different files)
- **[Component]**: Which architectural component this task belongs to

---

## Component: Checkout State Machine

- [x] T001 [Checkout-SM] Define `checkout_flow` (`cart → address → delivery? → payment? → confirm? → complete`) in `spree/core/app/models/spree/order/checkout.rb`
- [x] T002 [Checkout-SM] Implement `before_transition to: :complete` guards (line item stock/discontinued checks, payment processing, digital link creation) in `order/checkout.rb`
- [x] T003 [Checkout-SM] Implement per-step entry/exit callbacks (address→tax, delivery→shipments/rates, payment→store-credit recalculation) in `order/checkout.rb`
- [x] T004 [Checkout-SM] Implement `after_transition to: :complete` (finalize!, coupon consumption, gift card redemption, newsletter subscription) in `order/checkout.rb`
- [x] T005 [Checkout-SM] Implement extension hooks (`self.go_to_state`, `insert_checkout_step`, `remove_checkout_step`, `remove_transition`) so decorators can splice steps without monkey-patching the whole flow
- [x] T006 [P] [Checkout-SM] RSpec coverage in `spree/core/spec/models/spree/order/checkout_spec.rb` (53 `it` / 50 `context` blocks)

## Component: Pluggable Checkout Requirements Registry

- [x] T007 [Registry] Define `Spree::Checkout::Registry` (register/remove step & requirement, `ordered_steps` anchor sorting, `reset!`) in `spree/core/app/models/spree/checkout/registry.rb`
- [x] T008 [P] [Registry] Define `Step` value object in `spree/core/app/models/spree/checkout/step.rb`
- [x] T009 [P] [Registry] Define `Requirement` value object in `spree/core/app/models/spree/checkout/requirement.rb`
- [x] T010 [Registry] Implement `Requirements.new(order).call`/`.met?` aggregator in `spree/core/app/models/spree/checkout/requirements.rb` (depends on T007-T009)
- [x] T011 [Registry] Implement built-in `DefaultRequirements` (line items, email, ship address, shipping method, payment) in `spree/core/app/models/spree/checkout/default_requirements.rb`
- [x] T012 [P] [Registry] RSpec coverage: `spree/core/spec/models/spree/checkout/registry_spec.rb` (8 `it`), `requirements_spec.rb` (19 `it`)

## Component: Cart Services (`Spree::Cart::*`, legacy namespace via `OrderContents`)

- [x] T013 [P] [Cart] `Cart::AddItem` — find-or-create line item, price validation, stock reservation — `spree/core/app/services/spree/cart/add_item.rb`
- [x] T014 [P] [Cart] `Cart::Associate` — link guest order to user, `guest_only` guard — `spree/core/app/services/spree/cart/associate.rb`
- [x] T015 [P] [Cart] `Cart::ChangeCurrency` — validate against store-supported currencies — `spree/core/app/services/spree/cart/change_currency.rb`
- [x] T016 [P] [Cart] `Cart::Create` — requires store, builds order with token/market/currency — `spree/core/app/services/spree/cart/create.rb`
- [x] T017 [P] [Cart] `Cart::Destroy` — cancel shipments, void payments, clear addresses, destroy — `spree/core/app/services/spree/cart/destroy.rb`
- [x] T018 [P] [Cart] `Cart::Empty` — destroy all line items/adjustments/shipments/promotions, restart checkout flow, release reservations — `spree/core/app/services/spree/cart/empty.rb`
- [x] T019 [P] [Cart] `Cart::EstimateShippingRates` — dummy-order shipping preview without mutating the real order — `spree/core/app/services/spree/cart/estimate_shipping_rates.rb`
- [x] T020 [Cart] `Cart::Recalculate` — central post-mutation hook (promotions, adjustments, tax, shipments) — `spree/core/app/services/spree/cart/recalculate.rb` (depended on by T013, T021-T024)
- [x] T021 [P] [Cart] `Cart::RemoveItem` — decrement/destroy line item by variant — `spree/core/app/services/spree/cart/remove_item.rb`
- [x] T022 [P] [Cart] `Cart::RemoveLineItem` — destroy by ID, re-reserve stock or fail with `InsufficientStockError` — `spree/core/app/services/spree/cart/remove_line_item.rb`
- [x] T023 [P] [Cart] `Cart::RemoveOutOfStockItems` — auto-remove inactive/discontinued/out-of-stock line items with structured warnings — `spree/core/app/services/spree/cart/remove_out_of_stock_items.rb`
- [x] T024 [P] [Cart] `Cart::SetQuantity` — update quantity, re-reserve stock — `spree/core/app/services/spree/cart/set_quantity.rb`
- [x] T025 [Cart] `Cart::Update` — bulk `line_items_attributes` update with ownership filtering (`filter_order_items`) — `spree/core/app/services/spree/cart/update.rb`
- [x] T026 [Cart] `Spree::OrderContents` facade delegating to the above via `Spree.cart_*_service` — `spree/core/app/models/spree/order_contents.rb`
- [x] T027 [P] [Cart] RSpec: `add_item_spec.rb` (29 it), `associate_spec.rb` (3), `change_currency_spec.rb` (5), `destroy_spec.rb` (11), `empty_spec.rb` (5), `remove_item_spec.rb` (6), `remove_line_item_spec.rb` (9), `remove_out_of_stock_items_spec.rb` (10), `set_quantity_spec.rb` (7)
- [ ] T028 [P] [Cart] **GAP — no spec found**: `Cart::Create`, `Cart::Recalculate`, `Cart::Update`, `Cart::EstimateShippingRates` have no dedicated RSpec file (see spec.md Migration Notes)

## Component: Cart Services (`Spree::Carts::*`, newer namespace — actually invoked by the Store API)

- [x] T029 [P] [Carts] `Carts::Create` — `spree/core/app/services/spree/carts/create.rb`
- [x] T030 [Carts] `Carts::Update` — auto-advance via `try_advance` (never to `complete`), revert to `address` on address/market change, stock reservation dispatch (Reserve/Extend/Release) — `spree/core/app/services/spree/carts/update.rb`
- [x] T031 [P] [Carts] `Carts::Complete` — documented as the forward-compatible completion path for the pending Cart/Order split — `spree/core/app/services/spree/carts/complete.rb`
- [x] T032 [P] [Carts] `Carts::UpsertItems` — `spree/core/app/services/spree/carts/upsert_items.rb`
- [x] T033 [P] [Carts] RSpec: `spree/core/spec/services/spree/carts/{create,update,complete,upsert_items}_spec.rb`

## Component: Checkout Services

- [x] T034 [P] [Checkout] `Checkout::Advance` — loop `order.next` until target/terminal state, Quick Checkout + Google Pay special-case — `spree/core/app/services/spree/checkout/advance.rb`
- [x] T035 [Checkout] `Checkout::Complete` — loop until `complete?` or errors — `spree/core/app/services/spree/checkout/complete.rb` (depends on T034's `Next` primitive)
- [x] T036 [P] [Checkout] `Checkout::Next` — single `order.next` wrapper — `spree/core/app/services/spree/checkout/next.rb`
- [x] T037 [P] [Checkout] `Checkout::GetShippingRates` — require ship address + line items, generate proposed shipments — `spree/core/app/services/spree/checkout/get_shipping_rates.rb`
- [x] T038 [P] [Checkout] `Checkout::AddStoreCredit` — apply up to outstanding balance across prioritized store credits, update existing checkout-state payments in place — `spree/core/app/services/spree/checkout/add_store_credit.rb`
- [x] T039 [P] [Checkout] `Checkout::RemoveStoreCredit` — invalidate checkout-state store-credit payments — `spree/core/app/services/spree/checkout/remove_store_credit.rb`
- [x] T040 [Checkout] `Checkout::SelectShippingMethod` (**@deprecated, removal planned for 6.0**) — `spree/core/app/services/spree/checkout/select_shipping_method.rb`
- [x] T041 [Checkout] `Checkout::Update` — IDOR-safe address ownership validation, country/state ISO resolution, checkout-state reversion rules — `spree/core/app/services/spree/checkout/update.rb`
- [x] T042 [P] [Checkout] RSpec: `add_store_credit_spec.rb` (9 it), `advance_spec.rb` (11), `get_shipping_rates_spec.rb` (8), `remove_store_credit_spec.rb` (3), `select_shipping_method_spec.rb` (11), `update_spec.rb` (21)
- [ ] T043 [P] [Checkout] **GAP — no spec found**: `Checkout::Complete`, `Checkout::Next` have no dedicated RSpec file

## Component: Address Services

- [x] T044 [Addresses] `Addresses::Helper` — country/state ISO resolution, bulk default-address assignment — `spree/core/app/services/spree/addresses/helper.rb`
- [x] T045 [Addresses] `Addresses::Create` — first-address-becomes-default logic, order ship-address assignment + checkout-state reversion (depends on T044) — `spree/core/app/services/spree/addresses/create.rb`
- [x] T046 [Addresses] `Addresses::Update` — change detection, immutable-address (`editable?`) duplicate-on-write behavior, default-flag-only updates (depends on T044) — `spree/core/app/services/spree/addresses/update.rb`
- [x] T047 [P] [Addresses] RSpec: `update_spec.rb` (22 it / 19 context), `phone_validator_spec.rb` (4 it / 20 context)
- [ ] T048 [P] [Addresses] **GAP — no spec found**: `Addresses::Create` has no dedicated RSpec file

## Component: Admin Order Services (`Spree::Orders::*`)

- [x] T049 [Orders] `Orders::Create` — admin one-shot order build (address, items, shipments, non-fatal coupon application) — `spree/core/app/services/spree/orders/create.rb`
- [x] T050 [Orders] `Orders::Update` — admin order update, conditional shipment rebuild — `spree/core/app/services/spree/orders/update.rb`
- [x] T051 [P] [Orders] `Orders::BuildShipments` — shared shipment-building step used by Create/Update — `spree/core/app/services/spree/orders/build_shipments.rb`
- [x] T052 [Orders] `Orders::Complete` — admin completion; documents (but does not enforce) an external `OrderLock` requirement — `spree/core/app/services/spree/orders/complete.rb`
- [x] T053 [P] [Orders] `Orders::Cancel` — `OrderCancellation` record, `order.cancel!` event, graceful invalid-transition handling — `spree/core/app/services/spree/orders/cancel.rb`
- [x] T054 [P] [Orders] `Orders::Approve` — `OrderApproval` record, clears `considered_risky` — `spree/core/app/services/spree/orders/approve.rb`
- [x] T055 [P] [Orders] `Orders::CreateUserAccount` — link-or-create user from guest order, copy name/phone — `spree/core/app/services/spree/orders/create_user_account.rb`
- [x] T056 [P] [Orders] `Orders::UpsertItems` — bulk line item create/update by variant, no auto-recalculation — `spree/core/app/services/spree/orders/upsert_items.rb`
- [x] T057 [P] [Orders] `Orders::UpdateContactInformation` — direct `update_columns` email change, cascades to vendor orders — `spree/core/app/services/spree/orders/update_contact_information.rb`
- [x] T058 [P] [Orders] RSpec: `approve_spec.rb` (7 it), `cancel_spec.rb` (11), `create_spec.rb` (12), `create_user_account_spec.rb` (7), `update_spec.rb` (16), `upsert_items_spec.rb` (19)
- [ ] T059 [P] [Orders] **GAP — no spec found**: `Orders::BuildShipments`, `Orders::UpdateContactInformation` have no dedicated RSpec file

## Component: Store API v3 Surface

- [x] T060 [API] `Spree::Api::V3::CartResolvable` concern — prefixed-ID lookup + CanCanCan authorization via `x-spree-token` header — `spree/api/app/controllers/concerns/spree/api/v3/cart_resolvable.rb`
- [x] T061 [API] `Store::CartsController` — index/show/create/update/destroy/associate/complete, `permitted_params` symmetric with serializer fields — `spree/api/app/controllers/spree/api/v3/store/carts_controller.rb`
- [x] T062 [P] [API] `Store::Carts::ItemsController` — line item CRUD — `spree/api/app/controllers/spree/api/v3/store/carts/items_controller.rb`
- [x] T063 [P] [API] `Store::Carts::FulfillmentsController` — shipping method selection with `try_advance` — `.../carts/fulfillments_controller.rb`
- [x] T064 [P] [API] `Store::Carts::PaymentsController` / `PaymentSessionsController` — payment + payment-session flow with its own nested `complete` — `.../carts/{payments,payment_sessions}_controller.rb`
- [x] T065 [P] [API] `Store::Carts::DiscountCodesController` / `GiftCardsController` / `StoreCreditsController` — `.../carts/{discount_codes,gift_cards,store_credits}_controller.rb`
- [x] T066 [API] Routes wiring for all of the above — `spree/api/config/routes.rb`

## Component: Storefront Session/Cookie Cart Resolution (distinct from CartResolvable)

- [x] T067 [Storefront] `current_order`, `associate_user`, `set_current_order`, `order_includes` helpers — `spree/core/lib/spree/core/controller_helpers/order.rb`

---

## Dependencies & Execution Order (as-built, for reference)

- `Cart::Recalculate` (T020) is a dependency of nearly every other `Cart::*` mutation (T013, T021-T024) — it is the shared post-mutation hook, not an independent leaf.
- `Checkout::Next` (T036) underlies both `Checkout::Advance` (T034) and `Checkout::Complete` (T035).
- `Addresses::Helper` (T044) underlies both `Addresses::Create` (T045) and `Addresses::Update` (T046).
- The `Checkout::Registry`/`Step`/`Requirement`/`Requirements`/`DefaultRequirements` chain (T007-T011) is a self-contained aggregation layer, independently pluggable, that reads the state machine (T001-T005) but does not modify it.
- `Orders::BuildShipments` (T051) is shared by `Orders::Create` (T049) and `Orders::Update` (T050).
- API controllers (T060-T066) depend on the full `Carts::*` (T029-T032) and `Checkout::*` (T034-T041) service layers already existing.

## Notes

- This tasks.md is a **retrospective inventory**, not a forward implementation plan — every `[x]` reflects code already merged and running in production.
- The five `[ ]` (unchecked) gap tasks (T028, T043, T048, T059) are the only unchecked items in this file, and intentionally so: they represent missing test coverage identified during this migration, not unstarted work. They are left unchecked to make the gap visible to `/speckit.analyze` and future contributors, per the "Honest gaps" rule — do not check them off without actually adding the missing spec files.
- No frontend (`packages/dashboard`, Vitest, Playwright) tasks exist because no frontend code implements this feature; admin order editing still runs through the legacy Rails admin.
