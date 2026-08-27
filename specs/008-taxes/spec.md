# Feature Specification: Taxes

**Feature Branch**: `008-taxes`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — no original user description. Source: `spree/core/app/models/spree/tax_rate.rb`, `tax_category.rb`, `calculator/default_tax.rb`, `models/concerns/spree/vat_price_calculation.rb`, `models/spree/adjustable/adjuster/tax.rb`, `models/spree/zone.rb`, `models/spree/order.rb` (`#tax_zone`), `spree/admin/app/controllers/spree/admin/{tax_rates,tax_categories}_controller.rb`, `spree/api/app/controllers/spree/api/v3/admin/tax_categories_controller.rb`, `spree/api/app/serializers/spree/api/v3/{,admin/}tax_category_serializer.rb`, `packages/dashboard/src/{hooks/use-tax-categories.ts,tables/tax-categories.tsx,schemas/tax-category.ts,routes/_authenticated/$storeId/settings/tax-categories.tsx}`. Planned rewrite tracked in `docs/plans/6.0-tax-provider.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merchant configures tax categories and rates (Priority: P1)

A store admin creates `Spree::TaxCategory` records (e.g. "Standard", "Food", "Clothing") to classify products/variants for tax purposes, and creates `Spree::TaxRate` records that pair a `TaxCategory` with a `Zone`, a percentage `amount`, an `included_in_price` flag (VAT vs. sales tax), and a `Spree::Calculator` (default `Spree::Calculator::DefaultTax`). This is the entire configuration surface for tax behavior.

**Why this priority**: Without a category + rate configured, no tax adjustment can ever be computed — this is the base of the whole feature.

**Independent Test**: Create a `TaxCategory` "Standard" and a `TaxRate` (`zone: default tax zone`, `tax_category: Standard`, `amount: 0.20`, `included_in_price: true`); assert `TaxRate.match(zone)` returns it and `TaxCategory.default` reflects the `is_default` flag correctly (only one category can be default at a time — enforced by `TaxCategory#set_default_category`).

**Acceptance Scenarios**:

1. **Given** an admin in the legacy Rails admin (`Spree::Admin::TaxRatesController`), **When** they create a `TaxRate` with a zone, tax category, amount, and calculator, **Then** the rate is persisted and defaults to `calculator_type: 'Spree::Calculator::DefaultTax'` (`set_defaults` before_action).
2. **Given** an admin creates a second `TaxCategory` with `is_default: true`, **When** it saves, **Then** the previously-default category is flipped to `is_default: false` (`before_save :set_default_category`).
3. **Given** the Admin API (`Spree::Api::V3::Admin::TaxCategoriesController`), **When** an admin `POST`s/`PATCH`es a tax category (`name`, `tax_code`, `description`, `is_default`), **Then** the category is created/updated — this API surface exists only for `TaxCategory`, not for `TaxRate` (no v3 Admin API endpoint for tax rates was found).

---

### User Story 2 - Order totals are taxed on completion/recalculation (Priority: P1)

`Spree::TaxRate.adjust(order, items)` is the entry point that matches applicable rates for the order's `tax_zone`, destroys stale tax adjustments, computes and stores `pre_tax_amount` on each relevant line item/shipment, and creates a `Spree::Adjustment` per matching rate via `AdjustmentSource#create_adjustment`. On subsequent recalculations, `Spree::Adjustable::Adjuster::Tax#update` re-runs `adjustment.update!` for existing tax adjustments (split into `included_tax_total` / `additional_tax_total`).

**Why this priority**: This is the customer-facing payoff — taxes must actually show up on the order total, correctly split between included (VAT) and additional (sales tax).

**Independent Test**: Build an order with a line item whose `tax_category` matches a non-included `TaxRate` (`amount: 0.10`); call `TaxRate.adjust(order, order.line_items)`; assert an eligible `Spree::Adjustment` exists with `amount == discounted_amount * 0.10` and `order.additional_tax_total` reflects it.

**Acceptance Scenarios**:

1. **Given** a `TaxRate` with `included_in_price: false` (sales tax) matching the order's tax zone and the line item's tax category, **When** `TaxRate.adjust` runs, **Then** `Calculator::DefaultTax#compute_shipment_or_line_item` computes `discounted_amount * rate.amount`, rounded to two places, and it is added as an additional (on-top) adjustment.
2. **Given** a `TaxRate` with `included_in_price: true` (VAT), **When** the rate is applied, **Then** the pre-tax amount is deduced from the already-tax-inclusive price (`store_pre_tax_amount` divides by `1 + sum(included rates)`) and the tax portion is computed via `deduced_total_by_rate` — item prices do not change, only the included/excluded split.
3. **Given** an item whose `tax_category_id` matches no rate for the order's zone, **When** `TaxRate.adjust` runs, **Then** its `pre_tax_amount` is stored as the full amount (no included tax to deduce) and no tax adjustment is created.
4. **Given** an order recalculation after a rate/item already has tax adjustments, **When** `Adjuster::Tax#update` runs, **Then** it separately sums `included_tax_total` and `additional_tax_total` across all tax adjustments rather than recomputing from scratch.

---

### User Story 3 - Cross-border VAT display uses the default tax zone (Priority: P2)

`Spree::VatPriceCalculation#gross_amount` lets storefront-facing price display show a price adjusted for a *different* VAT zone than the store's default (e.g. showing a French customer the correct gross price when the store's default VAT zone is Germany), by netting out the default zone's included tax and re-adding the target zone's rate.

**Why this priority**: Important for EU multi-country VAT display correctness, but only exercised for storefront price presentation — narrower than the core adjust/recalculate flow.

**Independent Test**: With `Zone.default_tax` = Germany (19% included VAT) and a `price_options[:tax_zone]` = France (20%), call `gross_amount(amount, price_options)`; assert the result nets out the German VAT and re-applies the French rate, rounded to two places.

**Acceptance Scenarios**:

1. **Given** `price_options[:tax_zone]` equals the store's default VAT zone (or is absent), **When** `gross_amount` is called, **Then** the amount is returned unchanged (`outside_default_vat_zone?` is false).
2. **Given** `price_options[:tax_zone]` differs from the default zone, **When** `gross_amount` is called, **Then** it computes `net_amount` (deduce default zone's included tax via `TaxRate.included_tax_amount_for`) then re-applies the target zone's included tax rate (`amount_with_foreign_vat`).

### Edge Cases

- Multiple `included_in_price: true` rates matching the same item (e.g. combined national + regional VAT) → `store_pre_tax_amount` divides by `1 + sum(all included rates' amounts)`, not per-rate.
- A `TaxCategory` is destroyed while products/variants still reference it → `has_many :products/:variants, dependent: :nullify` clears the FK rather than blocking or cascading deletes.
- A `Zone` used by a `TaxRate` is destroyed → `TaxRate` has no `dependent:` option declared on `belongs_to :zone` (only `inverse_of`); orphaned rates would silently stop matching any order (`Zone.potential_matching_zones` returns nothing for a missing zone).
- Legacy pre-2.2 orders with tax applied at the order level (not per-line-item) → `Calculator::DefaultTax#compute_order` is a distinct code path retained "for legacy reasons," matching line items by `tax_category` and summing `total` rather than using `discounted_amount`/`pre_tax_amount`.
- `amount_percentage` virtual attribute (admin form convenience: `0.20` stored ⇄ `20` displayed) has no bounds validation — only the underlying `amount` is validated (`numericality`, `allow_nil: true`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let merchants define `Spree::TaxCategory` records (name, `tax_code`, `description`, `is_default`) to classify products/variants for tax purposes, with exactly one category flagged `is_default` at a time.
- **FR-002**: System MUST let merchants define `Spree::TaxRate` records pairing a `TaxCategory` + `Zone` with a percentage `amount`, an `included_in_price` flag, and a pluggable `Spree::Calculator` (default `Spree::Calculator::DefaultTax`).
- **FR-003**: System MUST compute and apply tax adjustments to line items and shipments via `TaxRate.adjust(order, items)`, matching rates by the order's resolved `tax_zone` (`Zone.match(tax_address) || Zone.default_tax`, address chosen via `Spree::Config[:tax_using_ship_address]`) and the item's `tax_category_id`.
- **FR-004**: System MUST store a `pre_tax_amount` on each taxed item (`store_pre_tax_amount`) so included-tax (VAT) rates can be deduced from a tax-inclusive price without altering the displayed price.
- **FR-005**: System MUST split tax totals into `included_tax_total` (VAT-style, already in price) and `additional_tax_total` (added on top) via `Spree::Adjustable::Adjuster::Tax`.
- **FR-006**: System MUST support cross-zone VAT display recalculation for storefront price presentation via `Spree::VatPriceCalculation#gross_amount`, using `TaxRate.included_tax_amount_for` to look up rates for an arbitrary `{tax_zone:, tax_category:}` pair.
- **FR-007**: System MUST expose `TaxCategory` CRUD via the Admin API (`Spree::Api::V3::Admin::TaxCategoriesController`) with a Store-API-visible read-only subset (`id`, `name` only).
- **FR-008**: System MUST continue to support legacy order-level tax computation (`Calculator::DefaultTax#compute_order`) for orders predating per-line-item tax adjustments (pre-Spree-2.2).
- **FR-009**: `TaxRate` administration (create/update/destroy rates, assign zone/category/calculator) MUST remain available to merchants — currently only via the legacy Rails admin (`spree/admin/app/controllers/spree/admin/tax_rates_controller.rb` + its views), with **no equivalent Admin API endpoint or dashboard SPA route** (see Migration Notes).

### Key Entities

- **Spree::TaxCategory**: Classification label for products/variants (name, tax code, description, default flag). Has many tax rates (destroyed with it); has many products/variants (nullified, not destroyed, when the category is removed).
- **Spree::TaxRate**: A percentage rate tying a `TaxCategory` to a `Zone`, with `included_in_price` (VAT vs. additional) and a calculator. Includes `CalculatedAdjustments`/`AdjustmentSource` to create/compute `Spree::Adjustment` records.
- **Spree::Calculator::DefaultTax**: Computes tax amounts for orders (legacy), line items/shipments, and shipping rates, given a `TaxRate` as its `calculable`.
- **Spree::VatPriceCalculation** (concern): Cross-zone VAT netting/re-adding logic for storefront price display.
- **Spree::Zone**: Geographic grouping (countries/states) that a `TaxRate` is scoped to; also used for shipping methods. `Zone.default_tax` designates the store's default VAT zone.
- **Spree::Adjustment** (via `Adjustable::Adjuster::Tax`): The financial record of a tax rate's effect on a line item or shipment; polymorphically sourced from the `TaxRate`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::TaxRate`, `Spree::TaxCategory`, `Spree::Calculator::DefaultTax`, `Spree::VatPriceCalculation` concern, `Spree::Adjustable::Adjuster::Tax`, `Spree::Zone` (tax-zone matching), `Order#tax_zone` |
| `spree/api` (Store/Admin API v3) | Yes (TaxCategory only) | `Admin::TaxCategoriesController` (full CRUD), `TaxCategorySerializer` (Store: `id`,`name`) / `Admin::TaxCategorySerializer` (adds `tax_code`, `description`, `is_default`, timestamps). **No v3 API controller/serializer exists for `TaxRate`.** |
| `packages/dashboard` (admin SPA) | Yes (TaxCategory only) | `routes/.../settings/tax-categories.tsx`, `tables/tax-categories.tsx`, `schemas/tax-category.ts`, `hooks/use-tax-categories.ts`. **No dashboard route for tax rates** — rate management remains legacy-Rails-admin-only (`spree/admin/app/views/spree/admin/tax_rates/`). |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Yes (TaxCategory only) | Generated `TaxCategory.ts` type (both SDKs); no generated `TaxRate` type since no serializer exists |
| `docs/plans/` | Yes | `docs/plans/6.0-tax-provider.md` (Draft, targets 6.0) supersedes this entire feature — see Migration Notes |

### API Contract *(include if feature touches spree/api)*

- **Existing endpoints**: `Spree::Api::V3::Admin::TaxCategoriesController` — standard `ResourceController` CRUD (`index`/`show`/`create`/`update`/`destroy` inherited, `scoped_resource :settings`). No Store API write endpoint; no endpoint of any kind for `TaxRate`.
- **Serializer fields (read, Store)**: `id`, `name` (`Spree::Api::V3::TaxCategorySerializer`).
- **Serializer fields (read, Admin)**: `name`, `tax_code`, `description`, `is_default`, `created_at`, `updated_at` (`Spree::Api::V3::Admin::TaxCategorySerializer`, extends Store) — matches `TaxCategory`'s writable attributes 1:1 (no controller-level `permitted_params` override found; presumably falls back to the base `ResourceController`'s generic parameter permitting for this model's own columns).
- **Auth**: Admin API — secret key (scopes, presumably `read_settings`/`write_settings` per `scoped_resource :settings`) or Admin JWT + CanCanCan. Store API — publishable key, read-only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A merchant can configure a `TaxCategory` + `TaxRate` pair and see it applied as an order-level adjustment on the next recalculation, with no manual intervention.
- **SC-002**: VAT-inclusive (`included_in_price: true`) and sales-tax-style (`included_in_price: false`) rates produce mathematically distinct outcomes — the former nets out of an unchanged price, the latter adds on top — verified by `spec/models/spree/calculator/default_tax_spec.rb` and `spec/models/spree/tax_rate_spec.rb`.
- **SC-003**: Only one `TaxCategory` is ever `is_default: true`, enforced automatically on save (`tax_category_spec.rb`).
- **SC-004**: Cross-zone VAT display (`gross_amount`) returns the input amount unchanged whenever the requested zone matches the store's default, avoiding spurious recalculation for the common case.

## Assumptions

- This spec documents the system **as implemented**; no new behavior is proposed.
- "Taxes" as a feature = `TaxRate` + `TaxCategory` + `DefaultTax` calculator + `VatPriceCalculation`, all built on the pre-6.0 polymorphic `Spree::Adjustment` model (tracked separately for replacement by `docs/plans/6.0-split-adjustments.md`'s `TaxLine`).
- Admin API secret-key scope names for `TaxCategoriesController` are inferred from `scoped_resource :settings` and the project-wide `read_/write_<resource>` convention (`docs/plans/5.5-admin-api-key-scopes.md`); not verified against `Spree::ApiKey`'s declared scope list in this migration.
- `Zone` model itself is treated here only as a dependency of tax matching (its shipping-method use is out of scope for this spec).

## Migration Notes

Gaps and inferences made while reverse-engineering this spec, flagged for follow-up rather than silently resolved:

- **No Admin API v3 endpoint or serializer exists for `Spree::TaxRate`** — only `TaxCategory` has a v3 controller/serializer pair. Tax rate CRUD is only reachable through the legacy Rails admin (`spree/admin/app/controllers/spree/admin/tax_rates_controller.rb`), which will need an Admin API + serializer + dashboard route if the legacy admin is retired ahead of the 6.0 tax-provider rewrite.
- **No dashboard SPA route for tax rates** (`packages/dashboard` only has `settings/tax-categories.tsx`) — consistent with the missing API endpoint above.
- **Known future rewrite**: `docs/plans/6.0-tax-provider.md` (Draft, targets Spree 6.0) plans to **replace this entire feature**: `TaxRate.adjust`, `Calculator::DefaultTax`, and `Adjustable::Adjuster::Tax`'s direct TaxRate coupling are all slated for removal in favor of a pluggable `Spree::TaxProvider::Base` interface (per-`Market` `tax_provider`, `estimate`/`commit`/`void`/`refund` contract). The plan also drops the `Zone` model entirely in favor of direct `country_id`/`state_id` FKs on `TaxRate`, and moves tax totals from `Adjustment` records to typed `TaxLine` records (coordinated with `6.0-split-adjustments.md`). Per that plan's "Constraints on Current Work": *do not add new tax logic to `TaxRate.adjust`*, *do not add tax config beyond `Spree::Config[:tax_using_ship_address]`*, *do not monkey-patch `TaxRate` for external tax services* — these constraints bind any future work on this spec even before the provider rewrite lands.
- **`TaxRate#label`/`#amount_for_label`** (adjustment display label formatting) were read but not covered by a dedicated user story — they're a private presentation detail of `AdjustmentSource#create_adjustment`, not independently testable behavior.
- **CanCanCan ability / secret-key scopes** for `TaxCategoriesController` were not found explicitly declared in the controller; assumed to follow the `scoped_resource :settings` + standard scope convention but not verified against `Spree::ApiKey`.
