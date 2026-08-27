# Implementation Plan: Shipping & Fulfillment

**Branch**: `005-shipping-and-fulfillment` | **Date**: 2026-08-25 | **Spec**: `specs/005-shipping-and-fulfillment/spec.md`

**Input**: Feature specification from `specs/005-shipping-and-fulfillment/spec.md`

**Note**: This plan is reverse-engineered from an already-shipped implementation
(brownfield migration). It documents the actual architecture rather than
proposing one.

## Summary

Shipping & Fulfillment turns an order's requested inventory into one or more
location-scoped `Spree::Shipment`s ("fulfillments" in API v3), prices each
via a pluggable `Spree::ShippingCalculator`-backed `Spree::ShippingRate`, and
drives each shipment through a `pending → ready → shipped` (+ `canceled` /
`resume`) state machine. Allocation across stock locations is delegated to a
per-order `Spree::OrderRouting::Strategy` (`Rules`, the 5.5+ default, or
`Legacy`, a pre-5.5 escape hatch); `Rules` ranks candidate locations through
an ordered chain of pluggable `Spree::OrderRoutingRule` STI subclasses
reduced by a shared first-non-tie-wins `Reducer`. Post-allocation
corrections (moving units between shipments/locations) go through
`Spree::FulfilmentChanger`. The Admin API v3 exposes the full lifecycle
(update/fulfill/cancel/resume/split/manual-create) via one controller.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`
only — no frontend surface found for this feature).

**Primary Dependencies**: `state_machines-activerecord` (`Shipment` state
machine), CanCanCan + Ransack (Admin API scoping), Alba serializers,
`acts_as_list` (`OrderRoutingRule#position` scoped to `channel_id`),
`ActiveModel::Validations` (`FulfilmentChanger` as a non-persisted service
object), `Spree::ServiceModule::Base`-style result objects
(`Spree.fulfillment_create_service`, `Spree.shipment_update_service`).

**Storage**: PostgreSQL/MySQL/SQLite via ActiveRecord. `spree_shipments`
(`state`, `cost`, `tracking`, `stock_location_id`), `spree_shipping_methods`
(`display_on`, calculator polymorphic association), `spree_shipping_rates`
(`cost`, `selected`, `shipping_method_id`, `tax_rate_id`),
`spree_order_routing_rules` (STI `type`, `channel_id`, `position`,
`active` — added in `20260508204041_create_spree_order_routing_rules.rb`).
No foreign key constraints, per migration conventions. Base
`spree_shipments`/`spree_shipping_methods` tables predate the timestamped
migration set (install-generator schema baseline) — only later add-column
migrations were found (`add_metadata_to_spree_shipments`,
`add_estimated_transit_fields_to_spree_shipping_methods`).

**Testing**: RSpec + Factory Bot. Only `spree/core/spec/models/spree/order_routing/strategy/reducer_spec.rb`
was located and read for this feature (6 examples: unique winner, tie
carry-forward, default-location fallback with/without rules, abstention).
No spec files were found for `Shipment`, `ShippingMethod`, `FulfilmentChanger`,
`Strategy::Rules`/`Strategy::Legacy`, or the `Calculator::Shipping::*`
classes in this pass — flagged as a gap in spec.md Migration Notes.

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`) consumed
by a Spree host app. No standalone frontend target — see Project Structure.

**Project Type**: Monorepo — backend-only for this feature:
`spree/core` (models/services), `spree/api` (Admin API v3
controller/serializers), `packages/admin-sdk` (generated types only, no
hand-written resource methods needed).

**Performance Goals**: Not explicitly benchmarked in source.
`OrderRouting::Rules::MinimizeSplits` batches its stock-item lookup into one
query across the full location×variant matrix (`stock_item_counts`)
specifically to avoid N×M per-location/per-variant queries.

**Constraints**: `FulfilmentChanger#handle_stock` wraps stock decrement/
restock + inventory-unit reassignment in a single `ActiveRecord::Base.transaction`
so a failure never leaves shipments/stock inconsistent. `Reducer#pick` must
always return a location for any non-empty input set (guaranteed via the
default-location/lowest-id fallback) — order allocation cannot leave a
package unassigned.

**Scale/Scope**: Core commerce primitive — touched by every order placement
(allocation), every admin shipment view/action, and every checkout rate
quote. No scale ceiling assumptions found in code.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches only `spree/core` (models/services) and
  `spree/api` (Admin API v3 controller + serializers). No `packages/dashboard`
  or `dashboard-core`/`dashboard-ui` code exists for this domain — the
  Admin API is consumed today only by the legacy Rails admin
  (`Spree::Admin::ShippingMethodsController`, server-rendered) and external
  API clients, not by the React SPA. No boundary is blurred; there is simply
  no SPA consumer yet. PASS.
- **II. Admin API Is the Only Frontend Data Source**: N/A — no dashboard
  code touches this domain in the read source. If/when a dashboard
  fulfillments or shipping-methods page is built, it must consume
  `Spree::Api::V3::Admin::Orders::FulfillmentsController` /  a
  to-be-added shipping-methods Admin API endpoint, not server-rendered
  HTML.
- **III. Read/Write Field Symmetry**: Confirmed. `FulfillmentsController#permitted_params`
  for `update` is exactly `:tracking, :selected_delivery_rate_id, :stock_location_id`,
  matching the serializer's writable surface. The legacy-name bridge
  (`selected_delivery_rate_id` / `selected_delivery_rate_id=` →
  `selected_shipping_rate_id`) lives on the `Shipment` model itself
  (`shipment.rb:350-365`), not in the controller. PASS.
- **IV. Test-Backed**: Only `Reducer` has located RSpec coverage. `Shipment`,
  `ShippingMethod`, `FulfilmentChanger`, and the two `Strategy` subclasses
  have no spec files found in this migration pass. Flagged as a real gap
  in spec.md Migration Notes — PARTIAL, not a blocking violation for a
  documentation-only migration pass, but a follow-up item.
- **V. Translations and Prefixed IDs**: All models use `has_prefix_id`
  (`ful`, `dm`, `dr`, `orule`). No user-visible dashboard strings exist for
  this feature (no SPA surface), so the i18next requirement is N/A today.
  PASS (prefixed IDs); N/A (i18n, no SPA surface).
- **VI. `docs/plans/` for Architectural Changes**: Governed by two active
  plans: `docs/plans/6.0-fulfillment-and-delivery.md` (Shipment→Fulfillment
  / ShippingMethod→DeliveryMethod renames, `FulfillmentProvider` strategy,
  pickup/pickup-point — API-naming bridge shipped, model/table rename
  pending) and `docs/plans/6.0-order-routing.md` (Phase 1 — `Channel`,
  `OrderRoutingRule`, `Strategy::{Rules,Legacy}` — shipped in 5.5, Phase 2+
  layers Catalog/Company on top via a separate plan). This migration
  references both rather than creating a new entry. PASS.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/005-shipping-and-fulfillment/
├── spec.md               # Reverse-engineered feature spec
└── plan.md               # This file
```

(No `research.md`/`data-model.md`/`contracts/` phase artifacts — this is a
migration, not a fresh `/speckit-plan` run. `tasks.md` generated separately.)

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/app/models/spree/shipment.rb
spree/core/app/models/spree/shipment/webhooks.rb
spree/core/app/models/spree/shipment/custom_events.rb
spree/core/app/models/spree/shipping_method.rb
spree/core/app/models/spree/shipping_rate.rb
spree/core/app/models/spree/shipping_category.rb
spree/core/app/models/spree/shipping_method_category.rb
spree/core/app/models/spree/shipping_method_zone.rb
spree/core/app/models/spree/fulfilment_changer.rb
spree/core/app/models/spree/shipment_handler.rb
spree/core/app/models/spree/order_routing_rule.rb
spree/core/app/models/spree/order_routing/rules/default_location.rb
spree/core/app/models/spree/order_routing/rules/minimize_splits.rb
spree/core/app/models/spree/order_routing/rules/preferred_location.rb
spree/core/app/models/spree/order_routing/strategy/base.rb
spree/core/app/models/spree/order_routing/strategy/legacy.rb
spree/core/app/models/spree/order_routing/strategy/rules.rb
spree/core/app/models/spree/order_routing/strategy/reducer.rb
spree/core/app/models/spree/calculator/shipping/flat_rate.rb
spree/core/app/models/spree/calculator/shipping/per_item.rb
spree/core/app/models/spree/calculator/shipping/flat_percent_item_total.rb
spree/core/app/models/spree/calculator/shipping/flexi_rate.rb
spree/core/app/models/spree/calculator/shipping/price_sack.rb
spree/core/app/models/spree/calculator/shipping/digital_delivery.rb
spree/core/app/services/spree/shipments/update.rb
spree/core/app/services/spree/fulfillment_create_service.rb (registered via Spree.fulfillment_create_service)
spree/core/db/migrate/20210915064325_add_metadata_to_spree_shipments.rb
spree/core/db/migrate/20241123110646_add_estimated_transit_fields_to_spree_shipping_methods.rb
spree/core/db/migrate/20260508204041_create_spree_order_routing_rules.rb
spree/core/spec/models/spree/order_routing/strategy/reducer_spec.rb

# spree/admin — legacy Rails admin (shipping-method settings only; not extended further per constitution Principle I)
spree/admin/app/controllers/spree/admin/shipping_methods_controller.rb

# spree/api — Admin REST API v3
spree/api/app/controllers/spree/api/v3/admin/orders/fulfillments_controller.rb
spree/api/app/serializers/spree/api/v3/fulfillment_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/fulfillment_serializer.rb
spree/api/app/serializers/spree/api/v3/shipping_category_serializer.rb

# packages/admin-sdk — generated types (regenerated, not hand-edited)
packages/admin-sdk/src/types/generated/Fulfillment.ts
packages/admin-sdk/src/types/generated/DeliveryMethod.ts
packages/admin-sdk/src/types/generated/DeliveryRate.ts
```

**Structure Decision**: Backend-only per the Module Impact table in
spec.md — `spree/core` owns the shipment state machine, order-routing
allocation, and rate calculation; `spree/api` exposes the fulfillment
lifecycle to the back office; the legacy Rails admin retains
shipping-method *settings* CRUD (not migrated to the SPA, and not to be
extended there per constitution Principle I); `packages/admin-sdk` holds
only generated types, with no dashboard route/hook consuming this domain
yet.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
