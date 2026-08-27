# Feature Specification: Shipping & Fulfillment

**Feature Branch**: `005-shipping-and-fulfillment`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing code as part of `/speckit.brownfield.migrate`. No original user description — this document describes the shipment/fulfillment lifecycle, shipping-rate calculation, and order-routing (multi-location allocation) system as built in `spree/core`, `spree/admin`, and `spree/api`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Order is allocated across stock locations into shipments (Priority: P1)

When an order is placed, its line items must be split into one or more `Spree::Shipment` records ("fulfillments"), each pinned to a single `Spree::StockLocation`, honoring which location(s) actually have the stock and any merchant-configured routing preference.

**Why this priority**: Without allocation there is nothing to ship, rate, or fulfill — this is the entry point for the whole feature.

**Independent Test**: Complete an order whose channel/store uses the default `Rules` strategy, with stock split across two locations; confirm `order.shipments` contains one shipment per location actually needed, each with the correct `inventory_units`.

**Acceptance Scenarios**:

1. **Given** a channel/store with `preferred_order_routing_strategy` left at its default, **When** `Order#create_proposed_shipments` (or the equivalent allocation call) runs, **Then** `Spree::OrderRouting::Strategy::Rules#for_allocation` walks the channel's active `Spree::OrderRoutingRule`s in priority order via `Reducer#rank_all`, packs each ranked location with `Spree::Stock::Packer`, and `Spree::Stock::Prioritizer` removes duplicate coverage so each unit is claimed by exactly one package.
2. **Given** a store still configured for the pre-5.5 behavior, **When** `preferred_order_routing_strategy` is set to `Spree::OrderRouting::Strategy::Legacy`, **Then** allocation instead delegates directly to `Spree::Stock::Coordinator`, ignoring `OrderRoutingRule`s entirely.
3. **Given** no rule produces a unique winner, **When** `Reducer#pick` runs out of rules, **Then** it falls back to the `StockLocation` marked `default: true`, then lowest `id`, so a winner is always chosen for a non-empty location set.

---

### User Story 2 - Admin views, tracks, and ships a fulfillment (Priority: P1)

An admin needs to see a completed order's fulfillments, mark a fulfillment as shipped (adding a tracking number), cancel it, or resume a canceled one, with inventory and order totals kept consistent through each transition.

**Why this priority**: Core back-office operation — no order can be closed out without shipping being recorded.

**Independent Test**: `PATCH /api/v3/admin/orders/:order_id/fulfillments/:id/fulfill` on a `ready` shipment; confirm it transitions to `shipped`, fires `ShipmentHandler`, and the shipped-at timestamp is recorded.

**Acceptance Scenarios**:

1. **Given** a shipment in `ready` or `canceled` state, **When** the admin calls the `fulfill` action, **Then** the state machine's `ship` event transitions it to `shipped`, running `after_ship` (`ShipmentHandler.factory(self).perform`), the shipped webhook, and the `order_routing.for_sale`/lifecycle event hooks.
2. **Given** a shipment in `pending` or `ready`, **When** the admin calls `cancel`, **Then** it transitions to `canceled` and `after_cancel` restocks every manifest item (`manifest_restock`) back onto its stock location.
3. **Given** a `canceled` shipment, **When** the admin calls `resume`, **Then** it transitions back to `ready` (if `determine_state` says ready) or `pending`, and `after_resume` unstocks the manifest items again.
4. **Given** any state, **When** the admin updates `tracking`/`selected_delivery_rate_id`/`stock_location_id` via `PATCH .../fulfillments/:id`, **Then** `Spree.shipment_update_service` (`Shipments::Update`) persists the change without going through the state-machine events.

---

### User Story 3 - Admin splits/transfers inventory between fulfillments or locations (Priority: P2)

An admin needs to move some quantity of a variant from one shipment to a different stock location (creating a new shipment there, or merging into an existing one), for example to route backordered units to a location that just received stock.

**Why this priority**: Common operational correction after initial allocation, but not required for the simplest happy path (single-location order that ships as-is).

**Independent Test**: Call the `split` action with a `variant_id`/`quantity`/`stock_location_id`; confirm inventory units move between shipments and stock counts are restocked/unstocked correctly.

**Acceptance Scenarios**:

1. **Given** a shipment with on-hand and/or backordered units for a variant, **When** `PATCH .../fulfillments/:id/split` runs with a target stock location, **Then** `Shipment#transfer_to_location` builds a new (or reuses the target) shipment and delegates to `Spree::FulfilmentChanger#run!`.
2. **Given** the transfer targets a different stock location on a completed order, **When** `FulfilmentChanger#handle_stock` executes, **Then** it restocks the current location and unstocks the desired location (backorder-aware) inside one DB transaction, then moves `InventoryUnit`s between the two shipments' manifests, splitting/merging on-hand vs. backordered units as needed.
3. **Given** the current shipment ends up with zero total inventory-unit quantity after the transfer, **When** `after_process_shipments` runs, **Then** the now-empty current shipment is destroyed; otherwise both shipments have their rates refreshed and totals recalculated.
4. **Given** the desired stock location cannot supply the requested quantity, **When** `FulfilmentChanger` validates, **Then** `enough_stock_at_desired_location` blocks the transfer with a validation error (skipped for orders not yet completed, per `handle_stock_counts?`).

---

### User Story 4 - Merchant configures shipping methods, rates, and calculators (Priority: P2)

A store admin needs to define `Spree::ShippingMethod`s (name, display scope, shipping categories, zones, tax category) backed by a pluggable `Calculator::Shipping::*` (flat rate, per item, flat percent of item total, flexi-rate tiered, digital-delivery no-op), so checkout can quote a shipping cost per package.

**Why this priority**: Without configured shipping methods/calculators, no shipment can be rated or selected at checkout — but this is setup/configuration, not the transactional core, hence P2.

**Independent Test**: Create a `Spree::ShippingMethod` with a `Calculator::Shipping::FlatRate` calculator via the legacy Rails admin (`Spree::Admin::ShippingMethodsController`); confirm `Stock::Estimator` produces a `Spree::ShippingRate` with the expected cost for a package.

**Acceptance Scenarios**:

1. **Given** the admin shipping-methods form, **When** a new method is created, **Then** it must have `name`, `display_on`, at least one `shipping_category` (`at_least_one_shipping_category` validation), and a calculator type drawn from `ShippingMethod.calculators` (subclasses of `Spree::ShippingCalculator`).
2. **Given** a package of line items, **When** `Calculator::Shipping::FlexiRate#compute_package` runs, **Then** cost is `preferred_first_item` for the first unit plus `preferred_additional_item` per unit beyond it, capped by `preferred_max_items` tiers.
3. **Given** a `Calculator::Shipping::FlatPercentItemTotal`, **When** computed, **Then** cost is `preferred_flat_percent` percent of the package's item total, rounded to cents.
4. **Given** a `Calculator::Shipping::DigitalDelivery` calculator, **When** `ShippingMethod#digital?`/`#requires_zone_check?` are checked, **Then** the method is treated as free/zone-exempt (used by `Shipment#digital?` and the `Shipment.digital_delivery` scope).
5. **Given** a shipping method scoped to zones, **When** `ShippingMethod#include?(address)` is checked, **Then** it returns true only if one of the method's `zones` includes that address (skipped entirely for digital-delivery methods via `requires_zone_check?`).

---

### Edge Cases

- What happens when `refresh_rates` is called on an already-`shipped` shipment? → It returns the existing `shipping_rates` unchanged; rates are never recomputed post-ship.
- What happens when the order's ship address fails validation? → `can_get_rates?` blocks `refresh_rates` from calling the estimator at all, returning `[]`.
- What happens to a shipment's `state` when the order isn't paid yet? → `determine_state` returns `pending` unless `order.paid? || Spree::Config[:auto_capture_on_dispatch]`, even if inventory is otherwise ready.
- What happens when inventory units are backordered? → `determine_state` forces `pending` regardless of payment state; `backordered?` exposes this to callers.
- What happens when a manifest item's `line_item` has been destroyed without cascading? → `Shipment#manifest` defensively `next`s past orphaned inventory units instead of raising.
- What happens when a fulfillment's tracking number is set for a supported carrier? → `ShippingMethod#build_tracking_url` auto-derives a tracking URL via the `tracking_number` gem when no manual `tracking_url` template is configured; otherwise the template's `:tracking` placeholder is substituted.
- What happens when a `FulfilmentChanger` transfer targets the same shipment it started from? → `desired_shipment_different_from_current` rejects it.
- What happens when a shipment's selected shipping rate changes on a completed order? → `selected_shipping_rate_id=` skips `update_amounts`/`order.set_shipments_cost` for completed orders, only reloading — totals for completed orders are managed elsewhere (admin adjustments).
- What happens when a promotion grants free shipping? → `Shipment#with_free_shipping_promotion?` / `ShippingRate#final_price` both special-case the `Promotion::Actions::FreeShipping` adjustment to zero out cost even if `discount_amount` math alone wouldn't.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST represent a unit of fulfillment as `Spree::Shipment`, belonging to one `Order` and one `StockLocation`, with a state machine (`pending → ready → shipped`, plus `canceled`/`resume`) driven by `determine_state` (payment + backorder + cancellation awareness).
- **FR-002**: System MUST allocate an order's requested inventory into one or more shipments via a pluggable `Spree::OrderRouting::Strategy` (`Legacy` or `Rules`, selected per-order via `Order#order_routing_strategy`, configurable at `Channel`/`Store` level).
- **FR-003**: System MUST rank eligible stock locations for the `Rules` strategy via an ordered chain of `Spree::OrderRoutingRule` STI subclasses (`DefaultLocation`, `MinimizeSplits`, `PreferredLocation`, extensible by plugins) reduced by `Spree::OrderRouting::Strategy::Reducer`'s first-non-tie-wins algorithm, always resolving to a winner via the default-location/lowest-id fallback.
- **FR-004**: System MUST quote per-package shipping cost via `Spree::ShippingRate`, generated from `Spree::ShippingMethod`s filtered by zone/shipping-category applicability and priced by a pluggable `Spree::ShippingCalculator` (`FlatRate`, `PerItem`, `FlatPercentItemTotal`, `FlexiRate`, `PriceSack`, `DigitalDelivery`).
- **FR-005**: System MUST let an admin transfer inventory between shipments/stock locations (`Spree::FulfilmentChanger`), correctly splitting on-hand vs. backordered units, restocking/unstocking as needed, and destroying a shipment left with zero quantity.
- **FR-006**: System MUST expose fulfillment lifecycle actions (`fulfill`/`cancel`/`resume`/`split`) plus attribute updates (`tracking`, `selected_delivery_rate_id`, `stock_location_id`) through `Spree::Api::V3::Admin::Orders::FulfillmentsController`, and a manual/out-of-band fulfillment creation endpoint that bypasses order routing (`Spree.fulfillment_create_service`).
- **FR-007**: System MUST compute shipment/rate tax via a `tax_rate` on each `ShippingRate` (`tax_amount`, `additional_tax_total`/`included_tax_total` split by `included_in_price?`).
- **FR-008**: System MUST record every shipment state transition in `state_changes` and fire lifecycle events (`publishes_lifecycle_events`) plus dedicated webhooks (`send_shipment_shipped_webhook`) for shipped/canceled/resumed transitions.
- **FR-009**: System MUST support digital (non-physical) fulfillment: `ShippingMethod#digital?` / `Shipment#digital?` (via `Calculator::Shipping::DigitalDelivery`) exempt a shipment from zone checks and mark it `shippable?` without requiring a tracking number.

### Key Entities

- **Spree::Shipment**: One location-scoped grouping of an order's inventory units ("fulfillment" in API v3 naming — `has_prefix_id :ful`); owns the shipping state machine, manifest, cost/tax totals, and selected `ShippingRate`.
- **Spree::ShippingMethod**: Store-configured, zone/category-scoped shipping option (`has_prefix_id :dm`, "delivery method" in API v3) pairing a `CalculatedAdjustments`-style `Spree::ShippingCalculator` with display scope (`display_on`: front/back/both) and optional tax category.
- **Spree::ShippingRate**: A priced offer of one `ShippingMethod` for one `Shipment` (`has_prefix_id :dr`, "delivery rate" in API v3); one per shipment is `selected`.
- **Spree::OrderRoutingRule**: STI base (`has_prefix_id :orule`) for a single ranking signal used by the `Rules` strategy; channel-scoped, ordered (`acts_as_list scope: :channel_id`), pluggable by extensions.
- **Spree::OrderRouting::Strategy::{Base,Legacy,Rules}**: The allocation algorithm contract (`for_allocation`/`for_sale`/`for_release`/`for_cancellation`) selected per order; `Rules` is the 5.5+ default, `Legacy` is an explicit opt-out delegating to `Stock::Coordinator`.
- **Spree::OrderRouting::Strategy::Reducer**: Shared "walk rules, first unique winner, tie-break to next rule, fall back to default location" algorithm used by both `pick` (single winner) and `rank_all` (full ordering for multi-location fan-out).
- **Spree::FulfilmentChanger**: Non-persisted `ActiveModel::Validations` service object that moves inventory units + physical stock between two shipments (same or different stock locations).
- **Spree::Calculator::Shipping::{FlatRate,PerItem,FlatPercentItemTotal,FlexiRate,PriceSack,DigitalDelivery}**: Pluggable cost strategies implementing `compute_package(package)`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Shipment` (+ `Webhooks`/`CustomEvents` concerns), `Spree::ShippingMethod`, `Spree::ShippingRate`, `Spree::FulfilmentChanger`, `Spree::OrderRoutingRule` + `order_routing/rules/*`, `Spree::OrderRouting::Strategy::{Base,Legacy,Rules,Reducer}`, `Spree::Calculator::Shipping::*`, `Spree::Stock::{Estimator,Coordinator,Packer,Prioritizer,InventoryUnitBuilder}` (shared with `006-stock-and-inventory`), `Spree::ShipmentHandler` |
| `spree/api` (Store/Admin API v3) | Yes | `Spree::Api::V3::Admin::Orders::FulfillmentsController` (create/update/fulfill/cancel/resume/split); serializers `FulfillmentSerializer`, `Admin::FulfillmentSerializer`, `ShippingCategorySerializer` |
| `packages/dashboard` (admin SPA) | No | No dashboard route/hook found for fulfillments or shipping-method settings — see Migration Notes |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated `Fulfillment`, `DeliveryMethod`, `DeliveryRate` types (`packages/admin-sdk/src/types/generated/`), regenerated from the Alba serializers above |
| `docs/plans/` | Yes | Governed by `docs/plans/6.0-fulfillment-and-delivery.md` (Shipment→Fulfillment / ShippingMethod→DeliveryMethod naming, pickup/pickup-point providers — API-level naming bridge already shipped, model/table renames pending) and `docs/plans/6.0-order-routing.md` (Phase 1 — `Channel`, `OrderRoutingRule`, `Strategy::{Rules,Legacy}` — shipped in 5.5; this spec documents that shipped phase) |

### API Contract *(include if feature touches spree/api)*

- **Endpoints** (existing, documented as-built): `POST /api/v3/admin/orders/:order_id/fulfillments` (manual/out-of-band create), `PATCH /api/v3/admin/orders/:order_id/fulfillments/:id`, `PATCH .../fulfillments/:id/fulfill`, `PATCH .../fulfillments/:id/cancel`, `PATCH .../fulfillments/:id/resume`, `PATCH .../fulfillments/:id/split`.
- **Serializer fields (read)**: `number`, `tracking`, `tracking_url`, `status` (aliases `shipment.state`), `fulfillment_type` (`digital`/`shipping`), `fulfilled_at`, money fields (`cost`, `total`, `discount_total`, `additional_tax_total`, `included_tax_total`, `tax_total` + `display_*`), `items` (line item/variant/quantity triples), nested `delivery_method` (`shipping_method`), `stock_location`, `delivery_rates` (`shipping_rates`). Admin adds `metadata`, `adjustment_total`, `pre_tax_amount`, `order_id`, `stock_location_id`, `created_at`/`updated_at`, expandable `order`/`adjustments`.
- **Write params**: `permitted_params` for `update` is exactly `:tracking, :selected_delivery_rate_id, :stock_location_id` — read/write symmetric with the serializer's public naming (`selected_delivery_rate_id` bridges to the legacy `selected_shipping_rate_id=` column via a model-owned alias, per Constitution Principle III). State changes (`fulfill`/`cancel`/`resume`) are dedicated member actions, never mass-assigned via `status`.
- **Auth**: Admin API only (secret key + scopes, or JWT + CanCanCan) — no Store API surface for fulfillments; customers see shipment/rate data only nested under their own cart/order responses (not covered by this controller).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every completed order's line items are fully covered by exactly one shipment's manifest per (variant, backorder-state) — no unit is silently dropped or double-counted across packages.
- **SC-002**: The `Rules` order-routing strategy always resolves every non-empty candidate-location set to a single winner (no unresolved ties reach the caller).
- **SC-003**: A shipment can never be marked `shipped` without either a tracking value or being digital (`shippable?` requires `can_ship? && (tracked? || digital?)`).
- **SC-004**: Cancel/resume of a shipment always leaves stock counts consistent — restocked on cancel, unstocked again on resume, with no double-adjustment.
- **SC-005**: A `FulfilmentChanger` transfer never leaves a partially-updated pair of shipments — stock movement + inventory-unit reassignment happen inside one transaction, and validation (insufficient stock, already-shipped, same-shipment) blocks the operation before any mutation.

## Assumptions

- "Shipment" (internal/model name) and "Fulfillment" (public API v3 name) refer to the same entity; `docs/plans/6.0-fulfillment-and-delivery.md` governs the eventual `Shipment` → `Fulfillment` model/table rename, not yet done at the model layer.
- Similarly, "ShippingMethod" ⇄ "DeliveryMethod" and "ShippingRate" ⇄ "DeliveryRate" are the same pre-rename/post-rename naming pair; this spec uses the current (pre-rename) model names in prose and the current API v3 public names in the API Contract section.
- Pickup / pickup-point fulfillment (per `6.0-fulfillment-and-delivery.md`'s `FulfillmentProvider` strategy) is out of scope here — no such provider abstraction was found in the read source files; only stock-location-based shipment fulfillment exists today.
- `Spree::Stock::Estimator`/`Packer`/`Prioritizer` internals are treated as shared infrastructure with `006-stock-and-inventory` and are not re-specified in full here — only the parts order-routing/shipping directly depends on.
- Zone-based shipping-method applicability (`ShippingMethod#include?`/`zones`) still uses the legacy `Spree::Zone` model, which `docs/plans/6.0-tax-provider.md` and `6.0-delivery-rate-provider.md` plan to replace with a `DeliveryZone`/direct country-state model — not yet done for shipping methods.

## Migration Notes

Honest gaps and one clear "two mechanisms" split found while reverse-engineering this feature:

- **Order routing has two parallel mechanisms that look like they could compete, but don't — they're a documented strategy/rule split, not duplication.** `Spree::OrderRouting::Strategy` (`Legacy`, `Rules`) is the *algorithm* (how to turn "what's ordered" into packages); `Spree::OrderRoutingRule` STI subclasses are *ranking signals* consulted only by the `Rules` strategy. `Legacy` exists purely as a documented escape hatch for stores upgrading from pre-5.5 behavior (comment: "Spree 6.0 drops this strategy along with the underlying Coordinator") and ignores `OrderRoutingRule`s entirely, while `Rules` is the 5.5+ default. This is intentional per `docs/plans/6.0-order-routing.md`, not two independently-evolved competing systems — but it does mean a store's `preferred_order_routing_strategy` setting silently determines whether any configured `OrderRoutingRule`s have any effect at all, which is easy to miss when debugging why a rule "isn't working."
- **`Shipment`/`ShippingMethod`/`ShippingRate` model names lag the public API naming.** The API v3 surface (controller path, serializer keys: `fulfillment`, `delivery_method`, `delivery_rate`) already uses the 6.0 target names via read/write bridging methods (`selected_delivery_rate_id`/`selected_delivery_rate_id=`) per Constitution Principle III, but the underlying Ruby classes, table names, and most internal method names (`shipping_method`, `shipping_rates`, `refresh_rates`) are still the pre-rename names. `docs/plans/6.0-fulfillment-and-delivery.md` explicitly targets this rename plus dropping `ShippingCategory` and adding `FulfillmentProvider`/pickup support — none of which has landed at the model/table level yet.
- **No admin-SPA (`packages/dashboard`) surface found for shipping methods or fulfillments.** Only the legacy Rails admin (`Spree::Admin::ShippingMethodsController`, and presumably an order-fulfillments view not in the read set) manages this domain today. Per Constitution Principle I / `docs/plans/6.0-admin-spa.md`, new admin work should not be added to `spree/admin` — but no dashboard route/hook (`use-shipping-methods`, `use-fulfillments`, etc.) was found to migrate to. This is either a 6.0-pending gap or genuinely out of scope until the fulfillment-and-delivery rename lands; not resolved by this migration.
- **`ShippingCategory` still gates shipping-method applicability** (`ShippingMethod belongs_to shipping_categories`, `at_least_one_shipping_category` validation) even though `6.0-fulfillment-and-delivery.md` lists "drop `ShippingCategory`" as a target — the drop has not happened in the read source.
- **RSpec coverage confirmed only for `Reducer`** (`spree/core/spec/models/spree/order_routing/strategy/reducer_spec.rb`, 63 lines, 6 examples covering unique-winner, tie-carry-forward, default-location fallback, and abstention). No spec files were located in this pass for `Shipment`, `ShippingMethod`, `FulfilmentChanger`, `Strategy::Rules`/`Strategy::Legacy`, or any of the `Calculator::Shipping::*` classes — acceptance scenarios above are inferred from model/service source, not verified against existing specs' exact assertions.
- **No base `create_spree_shipments`/`create_spree_shipping_methods` migration was found** in `spree/core/db/migrate` (only later add-column migrations: `add_metadata_to_spree_shipments`, `add_estimated_transit_fields_to_spree_shipping_methods`) — the base tables likely ship via the install generator's schema baseline rather than a timestamped migration, consistent with this being long-standing core infrastructure rather than a recent addition.
