# Implementation Plan: Pricing & Price Lists

**Branch**: `011-pricing-and-price-lists` | **Date**: 2026-08-25 | **Spec**: `specs/011-pricing-and-price-lists/spec.md`

**Input**: Feature specification from `specs/011-pricing-and-price-lists/spec.md`

**Note**: This is a brownfield reverse-engineering pass (`/speckit.brownfield.migrate`). The feature is already fully implemented; this plan documents the as-built architecture rather than proposing new work.

## Summary

`Spree::Price` (base + price-list-scoped rows) and `Spree::PriceList` (a schedulable, ordered, rule-gated container of overrides) together implement segmented pricing on top of Spree's variant model. `Spree::Pricing::Context`/`Resolver` answer "what price applies here" at read time; `Spree::Prices::BulkUpsert` and `PriceList#bulk_update_prices` handle high-volume writes; `Spree::PriceHistory` feeds EU Omnibus `prior_price`. The Admin API (`Admin::PriceListsController`/`Admin::PricesController`) exposes the whole editor as one flat, nested-PATCH resource; the dashboard SPA drives it via a spreadsheet-style bulk editor (`bulk-price-table.tsx` + `data-grid/*`) and a price-list detail route.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`) and TypeScript (React SPA, `packages/dashboard` + `packages/dashboard-ui`)

**Primary Dependencies**: Backend: `state_machines-activerecord` (PriceList `status`), `acts_as_list` (PriceList `position`), `acts_as_paranoid` (soft delete on Price/PriceList), Alba serializers, CanCanCan, Ransack. Frontend: TanStack Query, React Hook Form + Zod, `@spree/dashboard-core` registries/hooks, headless `data-grid` primitive in `dashboard-ui`.

**Storage**: PostgreSQL (production) / SQLite3 (backend tests) via ActiveRecord. `spree_prices` has two partial unique indexes (base: `(variant_id, currency)` where `price_list_id IS NULL`; override: `(variant_id, currency, price_list_id)`), both further partial on `amount IS NOT NULL` — placeholder (nil-amount) rows are not unique-constrained targets for upsert. `spree_price_rules` has a unique index on `(type, price_list_id)` scoped by `spree_base_uniqueness_scope`.

**Testing**: RSpec + Factory Bot (`spree/core/spec/models/spree/{price,price_list,price_rule}_spec.rb` and `spree/core/spec/models/spree/price_rules/*_spec.rb`, `spree/core/spec/lib/spree/core/pricing/*_spec.rb`, `spree/core/spec/services/spree/prices/bulk_upsert_spec.rb`), API integration specs (`spree/api/spec/integration/admin/{price_lists,prices}_spec.rb` — happy path + simple 422 only), Vitest (`packages/dashboard/src/components/spree/bulk-price-editor/normalize-money.test.ts`).

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`) consumed by a Spree host app; React SPA (`packages/dashboard`) against the Admin API v3.

**Project Type**: Monorepo — `spree/core`, `spree/api` (Ruby); `packages/dashboard`, `packages/dashboard-ui` (TypeScript). `packages/sdk`/`packages/admin-sdk` carry generated types only (no hand-written price-specific client code found beyond the standard resource methods).

**Performance Goals**: Bulk price edits (hundreds of variant/currency rows) complete in one transactional round trip via `upsert_all`, not N individual `save!` calls. Price resolution is a per-variant lookup bounded by the store's currently-active price list count, not the full catalog.

**Constraints**: No foreign key constraints (project convention) — `Price#variant_id`/`#price_list_id` and `PriceRule#price_list_id` are plain indexed columns. `MAXIMUM_AMOUNT = 99_999_999.99` bound on `amount`/`compare_at_amount`. MySQL's distinct-NULL unique-index semantics require a separate SELECT-then-write path for base prices in both `BulkUpsert` and `PriceList#bulk_update_prices`.

**Scale/Scope**: Backend: 1 concrete model + 1 STI base + 6 STI subclasses + 1 history model + 1 service + 1 context/resolver pair. API: 2 controllers, 6 serializers (store + admin, across Price/PriceList/PriceRule/PriceHistory). Frontend: 3 routes, 2 hook files, 1 schema file, 4 bulk-editor components, 1 shared grid primitive.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (models/services), `spree/api` (Admin controllers/serializers), `packages/dashboard` (routes/hooks/schemas/components), `packages/dashboard-ui` (headless `bulk-price-table`/`data-grid`). Frontend never reaches into Rails models — all price/price-list access goes through `adminClient.priceLists`/`adminClient.prices` (generated Admin SDK). Pass.
- **II. Admin API Is the Only Frontend Data Source**: Confirmed — `use-price-lists.ts`/`use-prices.ts` call `adminClient.*` exclusively; no server-rendered HTML or direct model access from the SPA. Pass.
- **III. Read/Write Field Symmetry**: `PriceRuleSerializer#type`/`#preferences`/`#price_list_id` match `PriceListsController#permitted_params`'s `rules: [:id, :type, { preferences: {} }]` exactly. `PriceSerializer#amount`/`#compare_at_amount`/`#currency`/`#price_list_id` match `PricesController#permitted_params`. `PriceListSerializer#product_ids` (via `product_prefixed_ids`) matches the `product_ids=` writer. Pass — no field-name mismatches found.
- **IV. Test-Backed**: RSpec covers models/services/pricing resolver; API integration specs cover controllers (happy path + 422); Vitest covers the client-side money-normalization helper. No Playwright e2e spec was found under `packages/dashboard/e2e/` specifically for price lists — flagged as a gap (see spec.md Migration Notes is silent on this; noting here for `/speckit-tasks` follow-up if this migration continues into active development).
- **V. Translations and Prefixed IDs**: All ids returned/accepted are prefixed (`price_`, `pl_`, `prule_`, `variant_id` via `variant.prefixed_id`, etc.) per `has_prefix_id` declarations on `Price`/`PriceList`/`PriceRule`. Dashboard copy for price lists is expected to live under `admin.products.price_lists.*` in `packages/dashboard/src/locales/en.json` (referenced by `use-price-lists.ts` i18n keys) — not independently re-verified line-by-line in this pass. Pass (as-built).
- **VI. `docs/plans/` for Architectural Changes**: Gap identified — no dedicated `docs/plans/*price-list*.md` exists; only `5.4-6.0-eu-legal-compliance.md` covers the adjacent `PriceHistory`/`prior_price` slice. Recorded in spec.md Migration Notes rather than silently fixed, per non-destructive migration rules.

No violations requiring Complexity Tracking — this is a documentation-only reverse-engineering pass; no code changes were made.

## Project Structure

### Documentation (this feature)

```text
specs/011-pricing-and-price-lists/
├── plan.md              # This file
├── spec.md              # Feature specification (already written)
└── tasks.md             # Task checklist (already written, all marked done)
```

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/
├── app/models/spree/price.rb
├── app/models/spree/price_list.rb
├── app/models/spree/price_rule.rb
├── app/models/spree/price_rules/{channel_rule,customer_group_rule,market_rule,user_rule,volume_rule,zone_rule}.rb
├── app/models/spree/price_history.rb
├── app/services/spree/prices/bulk_upsert.rb
├── lib/spree/core/pricing/{context,resolver}.rb
├── db/migrate/20251110120000_create_spree_price_lists.rb
├── db/migrate/20251110120001_create_spree_price_rules.rb
├── db/migrate/20251110120002_add_price_list_id_to_spree_prices.rb
├── db/migrate/20251110120003_add_price_list_id_to_spree_line_items.rb
├── db/migrate/20260112000000_fix_spree_prices_unique_indexes.rb
├── db/migrate/20260323000000_create_spree_price_histories.rb
├── db/migrate/20260529000001_add_unique_index_to_spree_price_rules.rb
└── spec/models/spree/{price,price_list,price_rule}_spec.rb, spec/models/spree/price_rules/*_spec.rb, spec/lib/spree/core/pricing/*_spec.rb, spec/services/spree/prices/bulk_upsert_spec.rb

# spree/api — Admin REST API v3 (no Store API surface for price lists)
spree/api/
├── app/controllers/spree/api/v3/admin/{price_lists,prices}_controller.rb
├── app/serializers/spree/api/v3/{price_serializer.rb,price_history_serializer.rb}
├── app/serializers/spree/api/v3/admin/{price,price_list,price_rule,price_history}_serializer.rb
├── config/routes.rb (price_lists + prices resources, lines ~292-309)
└── spec/integration/admin/{price_lists,prices}_spec.rb

# packages/dashboard — admin SPA routes/forms
packages/dashboard/src/
├── routes/_authenticated/$storeId/products/price-lists/{index,new}.tsx
├── routes/_authenticated/$storeId/products/price-lists/$priceListId/index.tsx
├── hooks/use-price-lists.ts
├── hooks/use-prices.ts
├── schemas/price-list.ts
├── components/spree/bulk-price-editor/{bulk-price-editor,bulk-price-editor-dialog,product-bulk-price-editor,currency-parts,normalize-money}.ts(x)
└── locales/en.json (admin.products.price_lists.*)

# packages/dashboard-ui — shared headless primitives
packages/dashboard-ui/src/spree/
├── bulk-price-table.tsx
└── data-grid/{data-grid.tsx,use-data-grid-keyboard.ts}

# packages/sdk / packages/admin-sdk — generated clients
packages/admin-sdk/src/types/generated/{Price,PriceList,PriceRule}.ts   # regenerated, not hand-edited
```

**Structure Decision**: Full-stack feature spanning `spree/core` (domain model + pricing resolution + bulk-write service), `spree/api` (Admin-only CRUD + bulk endpoints), and `packages/dashboard` + `packages/dashboard-ui` (spreadsheet-style bulk editor, price-list detail/list routes). No Store API or `packages/sdk` (customer-facing) surface — price lists are an admin-only concept; the storefront only ever sees resolved `Price`/`PriceHistory` data through product/variant serializers.

## Complexity Tracking

*No violations — table intentionally omitted.*
