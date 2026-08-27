---
description: "Task list — reverse-engineered from shipped code (brownfield migration)"
---

# Tasks: Shipping & Fulfillment

**Input**: Design documents from `/specs/005-shipping-and-fulfillment/`

**Prerequisites**: plan.md, spec.md

**Note**: This feature is already implemented. Every task below is marked
complete (`[x]`) and annotated with the file(s) that satisfy it, recovered
from the existing codebase rather than written prospectively.

**Organization**: Tasks are grouped by the user stories in spec.md.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 `spree/core` and `spree/api` gems build/test against the shared dummy Rails app (standard engine setup, no feature-specific setup step found)
- [x] T002 [P] Baseline backend spec located: `spree/core/spec/models/spree/order_routing/strategy/reducer_spec.rb` (only located spec file for this feature — see spec.md Migration Notes for coverage gaps)
- [x] T003 [P] `spree/api` integration surface confirmed reachable — `Spree::Api::V3::Admin::Orders::FulfillmentsController` routed under `orders/:order_id/fulfillments`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 [spree/core] Base `spree_shipments` / `spree_shipping_methods` / `spree_shipping_rates` tables (install-generator schema baseline, pre-dates timestamped migrations); later columns via `spree/core/db/migrate/20210915064325_add_metadata_to_spree_shipments.rb`, `spree/core/db/migrate/20241123110646_add_estimated_transit_fields_to_spree_shipping_methods.rb`
- [x] T005 [spree/core] `spree_order_routing_rules` STI table — `spree/core/db/migrate/20260508204041_create_spree_order_routing_rules.rb`
- [x] T006 [spree/core] `Spree::Shipment` model — state machine, manifest, cost/tax totals, prefix id `ful` — `spree/core/app/models/spree/shipment.rb`
- [x] T007 [spree/core] `Spree::ShippingMethod` (prefix `dm`) + `Spree::ShippingRate` (prefix `dr`) — `spree/core/app/models/spree/shipping_method.rb`, `spree/core/app/models/spree/shipping_rate.rb`
- [x] T008 [spree/core] `Spree::OrderRoutingRule` STI base + registration/validation (`type_must_be_registered`, `channel_belongs_to_store`) — `spree/core/app/models/spree/order_routing_rule.rb`
- [x] T009 [spree/api] Ransack allowlist on `OrderRoutingRule` (`type, position, active, store_id, channel_id`) and `Shipment` (`number`) — `order_routing_rule.rb:42`, `shipment.rb:112`
- [x] T010 [spree/api] `Admin::FulfillmentsController` routed under orders, `scoped_resource :fulfillments` — `spree/api/app/controllers/spree/api/v3/admin/orders/fulfillments_controller.rb`

**Checkpoint**: Foundation in place — shipment/rate/routing-rule persistence and Admin API scaffolding all exist and are exercised by the user stories below.

---

## Phase 3: User Story 1 - Order is allocated across stock locations into shipments (Priority: P1) 🎯 MVP

**Goal**: Order line items split into per-location shipments via a pluggable routing strategy.

**Independent Test**: Complete an order with stock split across two locations under the default `Rules` strategy; confirm one shipment per needed location.

### Tests for User Story 1

- [x] T011 [P] [US1] `Spree::OrderRouting::Strategy::Reducer` spec — unique winner, tie carry-forward, default-location/no-rules fallback, abstention — `spree/core/spec/models/spree/order_routing/strategy/reducer_spec.rb`

### Implementation for User Story 1

- [x] T012 [US1] `Order#order_routing_strategy` resolution (channel → store → hardcoded default) — `spree/core/app/models/spree/order.rb:807-809,1067`
- [x] T013 [US1] `Spree::OrderRouting::Strategy::Base` contract (`for_allocation`/`for_sale`/`for_release`/`for_cancellation`) — `spree/core/app/models/spree/order_routing/strategy/base.rb`
- [x] T014 [US1] `Spree::OrderRouting::Strategy::Legacy` — delegates to `Stock::Coordinator`, ignores routing rules — `spree/core/app/models/spree/order_routing/strategy/legacy.rb`
- [x] T015 [US1] `Spree::OrderRouting::Strategy::Rules#for_allocation` — ranks locations via `Reducer#rank_all`, packs via `Stock::Packer`, dedupes via `Stock::Prioritizer`, estimates rates — `spree/core/app/models/spree/order_routing/strategy/rules.rb`
- [x] T016 [US1] `Spree::OrderRouting::Strategy::Reducer#pick`/`#rank_all` — first-non-tie-wins reduction with default-location fallback — `spree/core/app/models/spree/order_routing/strategy/reducer.rb`
- [x] T017 [US1] Concrete routing rules: `DefaultLocation`, `MinimizeSplits` (batched stock-item query), `PreferredLocation` — `spree/core/app/models/spree/order_routing/rules/{default_location,minimize_splits,preferred_location}.rb`
- [x] T018 [US1] `Channel#order_routing_rules` + `ensure_default_order_routing_rules` seeding, `Channel`/`Store#preferred_order_routing_strategy` preference — `spree/core/app/models/spree/channel.rb:17,22,43,152-153`, `spree/core/app/models/spree/store.rb:66,124`

**Checkpoint**: Order allocation into location-scoped shipments is fully functional under both strategies.

---

## Phase 4: User Story 2 - Admin views, tracks, and ships a fulfillment (Priority: P1)

**Goal**: Admin can fulfill/cancel/resume a shipment and update tracking, with inventory kept consistent through each transition.

**Independent Test**: `PATCH .../fulfillments/:id/fulfill` on a `ready` shipment transitions it to `shipped` and records `shipped_at`.

### Implementation for User Story 2

- [x] T019 [US2] `Shipment` state machine (`ready`/`pend`/`ship`/`cancel`/`resume` events) + `determine_state` (payment/backorder/cancellation aware) — `spree/core/app/models/spree/shipment.rb:73-192`
- [x] T020 [US2] `after_ship` → `ShipmentHandler.factory(self).perform`; shipped webhook + lifecycle event hooks — `shipment.rb:88,494-496`
- [x] T021 [US2] `after_cancel`/`after_resume` → `manifest_restock`/`manifest_unstock` per manifest item — `shipment.rb:141-147,507-519`
- [x] T022 [US2] `state_changes` audit trail on every transition — `shipment.rb:103-109`
- [x] T023 [US2] `Admin::FulfillmentsController#fulfill`/`#cancel`/`#resume` — thin wrappers over the state-machine events with `StateMachines::InvalidTransition` rescue — `spree/api/app/controllers/spree/api/v3/admin/orders/fulfillments_controller.rb:55-83`
- [x] T024 [US2] `Admin::FulfillmentsController#update` → `Spree.shipment_update_service` (`Shipments::Update`), permitting exactly `tracking, selected_delivery_rate_id, stock_location_id` — `fulfillments_controller.rb:39-53,126-128`
- [x] T025 [US2] `Shipment#selected_delivery_rate_id`/`=` naming bridge (public API name → `selected_shipping_rate_id` column) owned by the model — `shipment.rb:350-365`
- [x] T026 [US2] `FulfillmentSerializer` (Store) + `Admin::FulfillmentSerializer` — status/fulfillment_type/items/money fields, admin adds metadata/adjustment_total/order_id/stock_location_id — `spree/api/app/serializers/spree/api/v3/fulfillment_serializer.rb`, `spree/api/app/serializers/spree/api/v3/admin/fulfillment_serializer.rb`
- [x] T027 [US2] Manual/out-of-band fulfillment creation bypassing routing (`Admin::FulfillmentsController#create` → `Spree.fulfillment_create_service`) — `fulfillments_controller.rb:11-37`

**Checkpoint**: Admin fulfillment lifecycle (view/track/ship/cancel/resume/manual-create) is fully functional via the Admin API.

---

## Phase 5: User Story 3 - Admin splits/transfers inventory between fulfillments or locations (Priority: P2)

**Goal**: Move inventory between shipments/stock locations without leaving stock or manifests inconsistent.

**Independent Test**: `PATCH .../fulfillments/:id/split` with a target stock location moves inventory units and adjusts stock counts correctly.

### Implementation for User Story 3

- [x] T028 [US3] `Shipment#transfer_to_location`/`#transfer_to_shipment` — builds/reuses target shipment, delegates to `FulfilmentChanger` — `spree/core/app/models/spree/shipment.rb:473-490`
- [x] T029 [US3] `Spree::FulfilmentChanger` validations (`enough_stock_at_desired_location`, `current_shipment_not_already_shipped`, `desired_shipment_different_from_current`) — `spree/core/app/models/spree/fulfilment_changer.rb:144-164`
- [x] T030 [US3] `FulfilmentChanger#handle_stock` — restock current / unstock desired inside one transaction, backorder-aware (`handle_stock_counts?` skips for incomplete orders) — `fulfilment_changer.rb:41-50,144-146`
- [x] T031 [US3] `FulfilmentChanger#move_inventory_units_between_shipments` — splits/merges on-hand vs. backordered units across the two shipments' manifests — `fulfilment_changer.rb:52-98`
- [x] T032 [US3] `FulfilmentChanger#after_process_shipments` — destroys the now-empty current shipment, else refreshes rates/amounts on both shipments and reloads order totals — `fulfilment_changer.rb:110-122`
- [x] T033 [US3] `Admin::FulfillmentsController#split` — resolves variant/quantity/target stock location, calls `FulfilmentChanger#run!`, renders both resulting fulfillments or validation errors — `fulfillments_controller.rb:85-108`

**Checkpoint**: Inventory transfer between shipments/locations round-trips stock and manifests correctly.

---

## Phase 6: User Story 4 - Merchant configures shipping methods, rates, and calculators (Priority: P2)

**Goal**: Admin defines shipping methods with zone/category scope and a pluggable cost calculator; `Stock::Estimator` prices packages against them.

**Independent Test**: Create a `ShippingMethod` with a `FlatRate` calculator via the legacy Rails admin; confirm `Stock::Estimator` produces the expected `ShippingRate` cost.

### Implementation for User Story 4

- [x] T034 [US4] `ShippingMethod` validations (`name`, `display_on`, `at_least_one_shipping_category`) + `display_on`/zone scoping (`frontend?`/`backend?`/`include?`/`requires_zone_check?`) — `spree/core/app/models/spree/shipping_method.rb:36-58,131-146`
- [x] T035 [US4] `ShippingMethod.calculators` — enumerates registered `Spree::ShippingCalculator` subclasses for the admin picker — `shipping_method.rb:82-85`
- [x] T036 [US4] `Calculator::Shipping::FlatRate`/`PerItem`/`FlatPercentItemTotal`/`FlexiRate`/`PriceSack`/`DigitalDelivery` — `spree/core/app/models/spree/calculator/shipping/{flat_rate,per_item,flat_percent_item_total,flexi_rate,price_sack,digital_delivery}.rb`
- [x] T037 [US4] `ShippingMethod#digital?`/`Shipment.digital_delivery` scope — treats `DigitalDelivery`-calculator methods as zone-exempt/trackless — `shipping_method.rb:41-43,127-129`; `shipment.rb:67,133-135`
- [x] T038 [US4] `ShippingRate` tax computation (`tax_amount`, `additional_tax_total`/`included_tax_total` split) + `display_price` including/excluding-tax label — `spree/core/app/models/spree/shipping_rate.rb:16-61`
- [x] T039 [US4] `Spree::Admin::ShippingMethodsController` — `permitted_resource_params`, `set_default_values` (defaults every zone + first calculator), turbo-stream inline `display_on` edit — `spree/admin/app/controllers/spree/admin/shipping_methods_controller.rb`

**Checkpoint**: Shipping methods are configurable and price packages correctly through every calculator type.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T040 [P] Prefixed IDs across the domain — `has_prefix_id :ful/:dm/:dr/:orule` on `Shipment`, `ShippingMethod`, `ShippingRate`, `OrderRoutingRule`
- [x] T041 Free-shipping promotion zeroing — `Shipment#with_free_shipping_promotion?`, `ShippingRate#final_price` — `shipment.rb:218-221`, `shipping_rate.rb:63-71`
- [x] T042 Plugin extension points documented in source comments — custom `OrderRoutingRule` STI subclass (`order_routing_rule.rb:1-13`), custom `Strategy` subclass only for algorithmically-different allocation (`strategy/base.rb:4-8`)
- [x] T043 `docs/plans/6.0-fulfillment-and-delivery.md` / `docs/plans/6.0-order-routing.md` — this migration references both rather than creating a new plan entry (constitution Principle VI)

---

## Dependencies & Execution Order

Foundational shipment/rate/routing-rule persistence (Phase 2) precedes all
four user stories. US1 (allocation) produces the shipments that US2
(lifecycle actions) and US3 (transfers) operate on, so US1 is a practical
prerequisite for exercising US2/US3 end-to-end even though US2's state
machine and US3's `FulfilmentChanger` are independently implemented units.
US4 (shipping-method/calculator configuration) is consumed by US1's rate
estimation step but can be configured and tested in isolation (calculator
math has no dependency on routing).

## Notes

- This tasks.md is a **retroactive record**, not a forward plan — every task cites the file(s) already implementing it.
- Test coverage gaps (`Shipment`, `ShippingMethod`, `FulfilmentChanger`, `Strategy::Rules`/`Strategy::Legacy`, and every `Calculator::Shipping::*` class have no located spec files) are called out in spec.md's Migration Notes rather than hidden here.
- No `packages/dashboard` tasks appear in any phase — no admin SPA surface for this domain was found (see spec.md Module Impact / Migration Notes).
