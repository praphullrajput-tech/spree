---
description: "Task list for feature implementation (reverse-engineered, brownfield migration)"
---

# Tasks: Taxes

**Input**: Design documents from `/specs/008-taxes/` (`plan.md`, `spec.md`)

**Note**: This feature is already implemented. All tasks below are marked complete (`[x]`) and organized by the actual components found in the codebase, not by prospective user-story phases — this is a documentation pass (`/speckit.brownfield.migrate`), not a forward implementation plan.

**Tests**: Existing test coverage is recorded per component; no new tests are proposed here.

## Format: `[ID] [Component] Description`

- Include exact file paths in descriptions
- All tasks are `[x]` (done) — this records what exists, not what remains

## Phase 1: Core Models (`spree/core`)

- [x] T001 [core] `Spree::TaxCategory` model in `spree/core/app/models/spree/tax_category.rb` — `has_prefix_id :taxcat`, `acts_as_paranoid`, `has_many :tax_rates, dependent: :destroy`, `has_many :products/:variants, dependent: :nullify`, `before_save :set_default_category` (single-default enforcement), `whitelisted_ransackable_attributes`
- [x] T002 [core] `Spree::TaxRate` model in `spree/core/app/models/spree/tax_rate.rb` — `has_prefix_id :tax`, `acts_as_paranoid`, includes `CalculatedAdjustments`, `AdjustmentSource`, `Metafields`, `Metadata`; `belongs_to :zone` (optional), `belongs_to :tax_category`; scopes `by_zone`, `potential_rates_for_zone`, `for_default_zone`, `for_tax_category`, `included_in_price`; `amount_percentage`/`amount_percentage=` virtual attribute for admin display
- [x] T003 [core] `TaxRate.match(order_tax_zone)` / `TaxRate.adjust(order, items)` / `TaxRate.store_pre_tax_amount(item, rates)` / `TaxRate.included_tax_amount_for(options)` class methods — the entry points for computing and applying tax to line items and shipments
- [x] T004 [core] `TaxRate#adjust`, `#compute_amount`, `#included?`, `#additional?`, private `#label`/`#amount_for_label` — instance-level adjustment creation + display label formatting
- [x] T005 [core] `Spree::Calculator::DefaultTax` in `spree/core/app/models/spree/calculator/default_tax.rb` — `compute_order` (legacy pre-2.2 order-level tax), `compute_shipment_or_line_item` (aliased as `compute_shipment`/`compute_line_item`), `compute_shipping_rate`, private `deduced_total_by_rate`
- [x] T006 [core] `Spree::VatPriceCalculation` concern in `spree/core/app/models/concerns/spree/vat_price_calculation.rb` — `gross_amount` public API; `net_amount`, `default_vat`, `foreign_vat`, `amount_with_foreign_vat`, `outside_default_vat_zone?`, `included_tax_amount`, `default_zone`, `round_to_two_places` private helpers
- [x] T007 [core] `Spree::Adjustable::Adjuster::Tax` in `spree/core/app/models/spree/adjustable/adjuster/tax.rb` — `update` splits adjustments into `included_tax_total`/`additional_tax_total` on recalculation
- [x] T008 [core] `Spree::Zone` tax-zone support in `spree/core/app/models/spree/zone.rb` — `has_many :tax_rates`, `scope :with_default_tax`, `Zone.default_tax` (via `Spree::Current.default_tax_zone`), `Zone.potential_matching_zones`
- [x] T009 [core] `Order#tax_zone` in `spree/core/app/models/spree/order.rb` — resolves `Zone.match(tax_address) || Zone.default_tax`, address chosen via `Spree::Config[:tax_using_ship_address]`, memoized

### Tests (existing) for Phase 1

- [x] T010 [P] [core] `spree/core/spec/models/spree/tax_rate_spec.rb`
- [x] T011 [P] [core] `spree/core/spec/models/spree/tax_category_spec.rb`
- [x] T012 [P] [core] `spree/core/spec/models/spree/calculator/default_tax_spec.rb`
- [x] T013 [P] [core] `spree/core/spec/models/spree/adjustable/adjuster/tax_spec.rb`
- [x] T014 [P] [core] `spree/core/spec/models/spree/order/tax_spec.rb`
- [x] T015 [P] [core] Factories: `spree/core/lib/spree/testing_support/factories/{tax_rate,tax_category}_factory.rb`

---

## Phase 2: Admin API v3 (`spree/api`) — TaxCategory only

- [x] T016 [api] `Spree::Api::V3::Admin::TaxCategoriesController` in `spree/api/app/controllers/spree/api/v3/admin/tax_categories_controller.rb` — `scoped_resource :settings`, inherits full CRUD from `ResourceController`, no overrides beyond `model_class`/`serializer_class`
- [x] T017 [api] `Spree::Api::V3::TaxCategorySerializer` in `spree/api/app/serializers/spree/api/v3/tax_category_serializer.rb` — Store-facing, `id`, `name` only
- [x] T018 [api] `Spree::Api::V3::Admin::TaxCategorySerializer` in `spree/api/app/serializers/spree/api/v3/admin/tax_category_serializer.rb` — extends Store serializer, adds `tax_code`, `description`, `is_default`, `created_at`, `updated_at`
- [x] T019 [core] Ransack allowlist for `TaxCategory` (`whitelisted_ransackable_attributes = %w[name is_default tax_code]`) and `TaxRate` (`%w[amount zone_id tax_category_id included_in_price name]`)

### Tests (existing) for Phase 2

- [x] T020 [P] [api] `spree/api/spec/controllers/spree/api/v3/admin/tax_categories_controller_spec.rb`

**Note**: No equivalent controller/serializer/spec exists for `TaxRate` in `spree/api` — see spec.md Migration Notes.

---

## Phase 3: Legacy Rails Admin (`spree/admin`) — TaxRate's only admin surface

- [x] T021 [admin] `Spree::Admin::TaxRatesController` in `spree/admin/app/controllers/spree/admin/tax_rates_controller.rb` — `load_data` (`@available_zones`, `@available_categories`, `@calculators`), `set_defaults` (defaults `calculator_type` to `Spree::Calculator::DefaultTax` on `new`), `permitted_resource_params`
- [x] T022 [admin] `Spree::Admin::TaxCategoriesController` in `spree/admin/app/controllers/spree/admin/tax_categories_controller.rb`
- [x] T023 [admin] Views in `spree/admin/app/views/spree/admin/tax_rates/` and `spree/admin/app/views/spree/admin/tax_categories/`; shared partials `_tax_nav.html.erb`, order-facing `_tax_rates.html.erb`/`_tax_lines.html.erb`, product form `_tax.html.erb`, shipping method form `_tax_category.html.erb`

### Tests (existing) for Phase 3

- [x] T024 [P] [admin] `spree/admin/spec/controllers/spree/admin/tax_rates_controller_spec.rb`
- [x] T025 [P] [admin] `spree/admin/spec/controllers/spree/admin/tax_categories_controller_spec.rb`
- [x] T026 [P] [admin] `spree/admin/spec/features/spree/admin/settings/tax_rates_spec.rb`
- [x] T027 [P] [admin] `spree/admin/spec/features/spree/admin/settings/tax_categories_spec.rb`

---

## Phase 4: Admin SPA (`packages/dashboard` / `packages/admin-sdk`) — TaxCategory only

- [x] T028 [dashboard] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/tax-categories.tsx`
- [x] T029 [dashboard] Table definition `packages/dashboard/src/tables/tax-categories.tsx`
- [x] T030 [dashboard] Zod schema `packages/dashboard/src/schemas/tax-category.ts`
- [x] T031 [dashboard] Resource hook `packages/dashboard/src/hooks/use-tax-categories.ts`
- [x] T032 [admin-sdk] Generated type `packages/admin-sdk/src/types/generated/TaxCategory.ts`

### Tests (existing) for Phase 4

- [x] T033 [P] [dashboard] `packages/dashboard/e2e/tax-categories.spec.ts`
- [x] T034 [P] [admin-sdk] `packages/admin-sdk/tests/tax-categories.test.ts`

**Note**: No dashboard route, table, schema, or hook exists for `TaxRate` — consistent with the missing Admin API endpoint in Phase 2.

---

## Dependencies & Execution Order

- Phase 1 (core models/calculator/concern/adjuster) underlies everything else — `TaxCategory`/`TaxRate` must exist before either API surface can serialize them.
- Phase 2 (Admin API) and Phase 3 (legacy admin) are independent surfaces over the same Phase 1 models — Phase 2 covers `TaxCategory` only, Phase 3 covers both `TaxCategory` and `TaxRate`.
- Phase 4 (dashboard SPA) depends on Phase 2's `TaxCategory` endpoint (Constitution Principle II) — it has no `TaxRate` counterpart because Phase 2 has none.

## Notes

- This tasks.md is a **retrospective record**, not a forward plan — every task is already done in the current codebase.
- Any future work to close the `TaxRate` API/dashboard gap, or to implement `docs/plans/6.0-tax-provider.md`, should be tracked as a *new* spec-kit feature (or as phases within that plan), not by editing this file's task states.
