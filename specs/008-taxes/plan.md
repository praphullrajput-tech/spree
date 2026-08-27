# Implementation Plan: Taxes

**Branch**: `008-taxes` | **Date**: 2026-08-25 | **Spec**: `specs/008-taxes/spec.md`

**Input**: Feature specification from `/specs/008-taxes/spec.md`

**Note**: This is a reverse-engineered (brownfield) plan documenting an already-built feature. No new implementation work is prescribed; it records the existing architecture as the baseline for the tracked `docs/plans/6.0-tax-provider.md` rewrite.

## Summary

Tax computation is a two-model system (`Spree::TaxCategory` classifies products/variants; `Spree::TaxRate` pairs a category with a `Zone`, a percentage, and an `included_in_price` flag) plus a stateless `Spree::Calculator::DefaultTax` that computes amounts, and a `Spree::VatPriceCalculation` concern that nets/re-adds VAT for cross-zone price display. `TaxRate.adjust(order, items)` is the single entry point that matches rates, stores pre-tax amounts, and creates `Spree::Adjustment` records; `Spree::Adjustable::Adjuster::Tax` re-sums them on recalculation. Only `TaxCategory` has an Admin API v3 endpoint + dashboard route today — `TaxRate` administration remains legacy-Rails-admin-only.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`) and TypeScript (React SPA, `packages/dashboard`) — TaxCategory only on the frontend side; TaxRate has no frontend surface.

**Primary Dependencies**: Backend — `state_machines-activerecord` not used here (no state machine on tax models), CanCanCan, Ransack (`whitelisted_ransackable_attributes` on both `TaxRate` and `TaxCategory`), Alba serializers (`TaxCategorySerializer` only), `paranoia` (`acts_as_paranoid` on both models), `Spree::Metafields`/`Spree::Metadata` (on `TaxRate` only). Frontend — TanStack Query/Router, React Hook Form + Zod (`schemas/tax-category.ts`), shadcn/ui.

**Storage**: PostgreSQL (production) / SQLite3 (backend test default) via ActiveRecord. `spree_tax_rates` and `spree_tax_categories` tables, no FK constraints.

**Testing**: RSpec + Factory Bot (`spree/core/spec/models/spree/{tax_rate,tax_category}_spec.rb`, `spec/models/spree/calculator/default_tax_spec.rb`, `spec/models/spree/adjustable/adjuster/tax_spec.rb`, `spec/models/spree/order/tax_spec.rb`), Rails controller specs + feature specs for the legacy admin (`spree/admin/spec/controllers/spree/admin/tax_rates_controller_spec.rb`, `spree/admin/spec/features/spree/admin/settings/{tax_rates,tax_categories}_spec.rb`), Vitest/Playwright for the TaxCategory dashboard surface (`packages/dashboard/e2e/tax-categories.spec.ts`, `packages/admin-sdk/tests/tax-categories.test.ts`).

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`, legacy `spree/admin`) consumed by a Spree host app; `packages/dashboard` React SPA for the TaxCategory settings page only.

**Project Type**: Monorepo — `spree/core`, `spree/api`, `spree/admin` (legacy, TaxRate only), `packages/dashboard` + `packages/admin-sdk` (TaxCategory only).

**Performance Goals**: N/A — documents existing behavior; no new performance targets introduced.

**Constraints**: Per `docs/plans/6.0-tax-provider.md` "Constraints on Current Work": do not add new tax logic to `TaxRate.adjust`; do not add tax-related global config beyond `Spree::Config[:tax_using_ship_address]`; do not monkey-patch `TaxRate` for external tax services; tax exemption checks (when added) should go through a provider seam, not ad-hoc controller/service checks; `TaxCategory` stays the product-level classification (future external providers map it to their own tax codes).

**Scale/Scope**: Two core models, one calculator, one concern, one adjuster, one legacy admin controller (TaxRate), one Admin API v3 resource (TaxCategory only), one dashboard settings page (TaxCategory only).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Pass. `spree/core` owns models/calculator/concern; `spree/api` owns the TaxCategory Admin API surface; `packages/dashboard` consumes it via `use-tax-categories.ts` (no direct model/DB access). The one boundary gap is architectural, not a violation: `TaxRate` has no `spree/api` surface at all, so its only admin surface is the legacy `spree/admin` engine (pre-dating the v3 API/dashboard split) — flagged in spec.md Migration Notes, not something this plan proposes fixing.
- **II. Admin API Is the Only Frontend Data Source**: Pass for the TaxCategory dashboard page (goes through `Admin::TaxCategoriesController` via `admin-sdk`). N/A for TaxRate — it has no dashboard page to violate this principle with.
- **III. Read/Write Field Symmetry**: Pass. `Admin::TaxCategorySerializer` exposes `name`, `tax_code`, `description`, `is_default` — these map 1:1 to `TaxCategory`'s own columns (no renamed/aliased fields to bridge).
- **IV. Test-Backed**: Pass. RSpec model specs exist for both `TaxRate` and `TaxCategory`, plus calculator/adjuster specs; legacy admin has controller + feature specs; TaxCategory dashboard has a Playwright e2e and an admin-sdk Vitest test.
- **V. Translations and Prefixed IDs**: Pass. Both models declare `has_prefix_id` (`:tax`, `:taxcat`). TaxCategory dashboard strings go through i18next per the existing `tax-categories.tsx` route/table. N/A for TaxRate (no dashboard UI to translate).
- **VI. `docs/plans/` for Architectural Changes**: Pass — `docs/plans/6.0-tax-provider.md` already exists and explicitly governs this area as a planned rewrite (per-Market `TaxProvider`, drops `Zone`, replaces `Adjustment` with `TaxLine`). This spec/plan pair documents current-state only and does not implement that plan.

No violations to record in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/008-taxes/
├── plan.md              # This file
└── spec.md              # Feature specification (already created)
```

(No `research.md`/`data-model.md`/`contracts/`/`tasks.md`-generation phase artifacts — this is a reverse-engineered brownfield migration, not a from-scratch `/speckit-plan` run. `tasks.md` is hand-authored to describe existing components, per the brownfield-migrate workflow.)

### Source Code (repository root)

```text
# spree/core — models, calculator, concern, adjuster
spree/core/
├── app/models/spree/tax_rate.rb
├── app/models/spree/tax_category.rb
├── app/models/spree/calculator/default_tax.rb
├── app/models/concerns/spree/vat_price_calculation.rb
├── app/models/spree/adjustable/adjuster/tax.rb
├── app/models/spree/zone.rb                          # tax-zone matching (Zone.match, Zone.default_tax)
├── app/models/spree/order.rb                          # #tax_zone
├── lib/spree/testing_support/factories/{tax_rate,tax_category}_factory.rb
└── spec/models/spree/{tax_rate,tax_category}_spec.rb, spec/models/spree/calculator/default_tax_spec.rb,
    spec/models/spree/adjustable/adjuster/tax_spec.rb, spec/models/spree/order/tax_spec.rb

# spree/api — Admin API v3 (TaxCategory only; no TaxRate endpoint exists)
spree/api/
├── app/controllers/spree/api/v3/admin/tax_categories_controller.rb
├── app/serializers/spree/api/v3/tax_category_serializer.rb
├── app/serializers/spree/api/v3/admin/tax_category_serializer.rb
└── spec/controllers/spree/api/v3/admin/tax_categories_controller_spec.rb

# spree/admin — legacy Rails admin (TaxRate + TaxCategory; only surface for TaxRate)
spree/admin/
├── app/controllers/spree/admin/tax_rates_controller.rb
├── app/controllers/spree/admin/tax_categories_controller.rb
├── app/views/spree/admin/tax_rates/
├── app/views/spree/admin/tax_categories/
└── spec/controllers/spree/admin/tax_rates_controller_spec.rb,
    spec/features/spree/admin/settings/{tax_rates,tax_categories}_spec.rb

# packages/dashboard + packages/admin-sdk — TaxCategory only, no TaxRate route
packages/dashboard/src/
├── routes/_authenticated/$storeId/settings/tax-categories.tsx
├── tables/tax-categories.tsx
├── schemas/tax-category.ts
├── hooks/use-tax-categories.ts
└── e2e/tax-categories.spec.ts
packages/admin-sdk/
├── src/types/generated/TaxCategory.ts
└── tests/tax-categories.test.ts
```

**Structure Decision**: Backend-heavy, split surface. `spree/core` holds all tax computation logic; `spree/api` + `packages/dashboard`/`packages/admin-sdk` only cover `TaxCategory` (the classification model). `TaxRate` (the actual rate/zone/calculator configuration) has no v3 API or SPA surface — it is administered exclusively through the legacy `spree/admin` engine. This asymmetry is inherited, not introduced by this plan; see spec.md Migration Notes.

## Complexity Tracking

*No violations — table intentionally omitted.*
