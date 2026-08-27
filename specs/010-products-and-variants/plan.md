# Implementation Plan: Products & Variants

**Branch**: `010-products-and-variants` | **Date**: 2026-08-24 | **Spec**: `specs/010-products-and-variants/spec.md`

**Input**: Feature specification from `/specs/010-products-and-variants/spec.md`

**Note**: This document is a reverse-engineered record of an already-shipped feature (brownfield migration), not a forward plan. It captures the architecture and file layout as they exist today so future changes can be checked against it.

## Summary

Products & Variants is the catalog core of Spree: a `Product` groups one or more purchasable `Variant`s, each combining `OptionValue`s across the product's declared `OptionType`s. Every product auto-provisions a hidden "master" variant so simple (non-configurable) products work without an explicit variant step. The feature spans backend models/scopes/finders (`spree/core`), the Admin + Store REST APIs (`spree/api`), the legacy Rails admin (`spree/admin`, not extended further), and the React admin SPA (`packages/dashboard`) for product CRUD, the options builder, and the variants matrix/edit-sheet.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`) and TypeScript (React SPA, `packages/dashboard`)

**Primary Dependencies**: Backend — CanCanCan, Ransack, Pagy, Alba serializers, `state_machines-activerecord` (Product `status`), `acts_as_list` (ProductOptionType, OptionValue, Variant position), `acts_as_paranoid` (soft delete), `acts_as_taggable_on` (tags/labels), Mobility (translations). Frontend — TanStack Router/Query, React Hook Form + Zod, shadcn/ui + Base UI, dnd-kit (variant/option reordering).

**Storage**: PostgreSQL (production) / SQLite3 (backend test default) via ActiveRecord — `spree_products`, `spree_variants`, `spree_option_types`, `spree_option_values`, `spree_product_option_types`, `spree_option_value_variants`, `spree_prices`, `spree_stock_items`.

**Testing**: RSpec + Factory Bot (`spree/core/spec/models/spree/product_spec.rb`, `variant_spec.rb`, `option_type_spec.rb`, etc.), integration specs in `spree/api/spec/integration/` (happy path + simple 422 only), Vitest for `packages/dashboard` unit logic (`variants-matrix.test.ts`), Playwright e2e under `packages/dashboard/e2e/`.

**Target Platform**: Rails engine gems consumed by a Spree host app (`server/`, cloned from spree-starter); React SPA served standalone via Vite, proxying to the Rails Admin/Store API v3.

**Project Type**: Monorepo — `spree/core`, `spree/api`, `spree/admin` (legacy, read-only w.r.t. new work) Ruby gems; `packages/dashboard` TypeScript package. No changes needed in `packages/dashboard-ui` / `dashboard-core` (uses existing generic primitives).

**Performance Goals**: N/A for this reverse-engineered record — no explicit perf budget authored; existing code optimizes via counter caches (`variant_count`, `media_count`, `classification_count`), memoization (`Spree::MemoizedData`), and derived-table JOINs for price sorting to avoid N+1 aggregate scans.

**Constraints**: Master-variant abstraction must remain internally consistent until `docs/plans/6.0-remove-master-variant.md` lands; `Spree::Config.enable_legacy_default_price` legacy shim must keep working alongside multi-currency `Price` until removed.

**Scale/Scope**: Core catalog entity — touched by nearly every other domain (cart/order line items, promotions, tax, stock, search). 5 core models, ~10 Ruby files, ~11 TS/TSX files enumerated below.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Confirmed — backend logic lives in `spree/core`/`spree/api`; SPA consumes only the Admin API via `@spree/admin-sdk` and custom hooks (`use-products.ts`, `use-product.ts`). No direct cross-boundary reach found. Legacy `spree/admin` products controller remains isolated and is not touched by SPA work.
- **II. Admin API Is the Only Frontend Data Source**: Pass — `packages/dashboard` product routes/components call only `adminClient.products.*` through hooks; no server-rendered HTML or direct model access.
- **III. Read/Write Field Symmetry**: Pass, with one documented bridge — `category_ids` (write) ↔ `categories` (read) is a model-level bridge (`Product#category_ids=` translating prefixed category IDs to `taxon_ids`), consistent with "the model owns the bridge." `custom_fields` read/write also matches (Metafields system). No controller/frontend mapper found translating field names.
- **IV. Test-Backed**: RSpec model specs exist for Product/Variant/OptionType/OptionValue; Vitest covers `variants-matrix.ts` pure logic (`variants-matrix.test.ts`); Playwright e2e coverage for the products flow was not independently verified in this pass — see Migration Notes gap in spec.md.
- **V. Translations and Prefixed IDs**: Pass — all Product/Variant/OptionType/OptionValue API responses use prefixed IDs (`prod_`, `variant_`, `opt_`, `optval_`); `OptionType`/`OptionValue` are `translatable_children` under Mobility; dashboard product UI strings route through i18next (not independently re-audited key-by-key in this pass).
- **VI. `docs/plans/` for Architectural Changes**: Pass — this area is explicitly governed by two active pending plans referenced in CLAUDE.md and cited in spec.md's Migration Notes: `6.0-remove-master-variant.md` and `6.0-product-types.md`. No new architectural change is introduced by this migration record itself.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/010-products-and-variants/
├── plan.md              # This file
└── spec.md              # Feature specification (migrated)
```

(No `research.md`/`data-model.md`/`contracts/`/`tasks.md` phase artifacts were generated as part of forward planning — this is a reverse-engineered record; `tasks.md` below documents the already-completed implementation for traceability.)

### Source Code (repository root)

```text
# spree/core — models, scopes, finders, services
spree/core/app/models/spree/product.rb
spree/core/app/models/spree/variant.rb
spree/core/app/models/spree/option_type.rb
spree/core/app/models/spree/option_value.rb
spree/core/app/models/spree/product_option_type.rb
spree/core/app/models/concerns/spree/product_scopes.rb
spree/core/app/models/concerns/spree/default_price.rb
spree/core/app/models/spree/product/webhooks.rb
spree/core/app/models/spree/product/slugs.rb
spree/core/app/models/spree/product/channels.rb
spree/core/app/models/spree/variant/webhooks.rb
spree/core/app/finders/spree/products/find.rb
spree/core/app/services/spree/products/duplicator.rb
spree/core/app/services/spree/products/prepare_nested_attributes.rb
spree/core/spec/models/spree/product_spec.rb
spree/core/spec/models/spree/variant_spec.rb
spree/core/spec/models/spree/option_type_spec.rb
spree/core/spec/models/spree/option_value_spec.rb

# spree/api — Store & Admin REST API v3
spree/api/app/controllers/spree/api/v3/admin/products_controller.rb
spree/api/app/controllers/spree/api/v3/store/products_controller.rb
spree/api/app/serializers/spree/api/v3/product_serializer.rb
spree/api/app/serializers/spree/api/v3/variant_serializer.rb
spree/api/app/serializers/spree/api/v3/option_type_serializer.rb
spree/api/app/serializers/spree/api/v3/option_value_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/product_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/variant_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/option_type_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/option_value_serializer.rb
spree/api/spec/integration/products_spec.rb (and variants/option_types equivalents)

# spree/admin — legacy Rails admin (not extended further; recorded for context)
spree/admin/app/controllers/spree/admin/products_controller.rb

# packages/dashboard — admin SPA routes/components/hooks
packages/dashboard/src/routes/_authenticated/$storeId/products/index.tsx
packages/dashboard/src/routes/_authenticated/$storeId/products/new.tsx
packages/dashboard/src/routes/_authenticated/$storeId/products/$productId.tsx
packages/dashboard/src/routes/_authenticated/$storeId/products/options.tsx
packages/dashboard/src/components/spree/products/product-form-cards.tsx
packages/dashboard/src/components/spree/products/variants-section.tsx
packages/dashboard/src/components/spree/products/variants-options-builder.tsx
packages/dashboard/src/components/spree/products/variants-matrix.ts (+ .test.ts)
packages/dashboard/src/components/spree/products/variant-edit-sheet.tsx
packages/dashboard/src/components/spree/products/variant-media-picker.tsx
packages/dashboard/src/components/spree/products/media-edit-sheet.tsx
packages/dashboard/src/components/spree/products/publishing-card.tsx
packages/dashboard/src/components/spree/products/inventory-section.tsx
packages/dashboard/src/hooks/use-products.ts
packages/dashboard/src/hooks/use-product.ts
packages/dashboard/src/hooks/use-product-media.ts

# packages/sdk / packages/admin-sdk — generated clients (not hand-edited)
packages/admin-sdk/src/types/generated/Product.ts
packages/admin-sdk/src/types/generated/Variant.ts
packages/admin-sdk/src/types/generated/OptionType.ts
packages/admin-sdk/src/types/generated/OptionValue.ts
```

**Structure Decision**: Full-stack feature spanning `spree/core` (models/finders), `spree/api` (Admin + Store v3 controllers/serializers), and `packages/dashboard` (routes/components/hooks) — consistent with the Module Impact table in spec.md. The legacy `spree/admin` controller is documented for context (it is the pre-SPA UI) but receives no new work per Constitution Principle I.

## Complexity Tracking

No constitution violations identified — table intentionally omitted.
