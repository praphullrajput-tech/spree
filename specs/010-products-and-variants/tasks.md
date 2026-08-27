# Tasks: Products & Variants

**Input**: Design documents from `/specs/010-products-and-variants/`

**Prerequisites**: plan.md, spec.md

**Status**: All tasks below describe already-shipped work, reverse-engineered from the codebase as part of the brownfield spec-kit migration. Marked `[x]` (done) for traceability — no new implementation is proposed by this document.

**Tests**: Existing RSpec/Vitest coverage is noted per task where found; this is a record of what exists, not a request for new tests.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Backend model/service: `spree/core/app/{models,services,finders}/spree/...`, specs in `spree/core/spec/...`
- API endpoint: `spree/api/app/controllers/spree/api/v3/{store,admin}/...`, serializer in `spree/api/app/serializers/spree/api/v3/...`, integration spec in `spree/api/spec/integration/`
- Admin SPA: `packages/dashboard/src/{routes,hooks,components}/...`

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Backend gems (`spree/core`, `spree/api`) build and pass `bundle exec rspec` on `main`
- [x] T002 [P] Frontend workspace (`packages/dashboard`) passes `pnpm typecheck && pnpm lint`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T003 [spree/core] `Spree::Product` model with `has_prefix_id :prod`, `acts_as_paranoid`, status state machine, master-variant auto-provisioning (`spree/core/app/models/spree/product.rb`)
- [x] T004 [spree/core] `Spree::Variant` model with `has_prefix_id :variant`, `acts_as_paranoid`, `acts_as_list scope: :product`, option-value/price/stock associations (`spree/core/app/models/spree/variant.rb`)
- [x] T005 [spree/core] `Spree::OptionType` (`has_prefix_id :opt`, `kind` enum-like column, `acts_as_list`) and `Spree::OptionValue` (`has_prefix_id :optval`, `color_code`, `acts_as_list scope: :option_type`) (`spree/core/app/models/spree/option_type.rb`, `option_value.rb`)
- [x] T006 [spree/core] `Spree::ProductOptionType` ordered join model (`spree/core/app/models/spree/product_option_type.rb`)
- [x] T007 [spree/core] Ransack allowlists (`whitelisted_ransackable_attributes/associations/scopes`) declared on Product, Variant, OptionType, OptionValue
- [x] T008 [spree/core] `Spree::ProductScopes` concern — availability, price sorting, taxon/category filtering, option-value filtering scopes (`spree/core/app/models/concerns/spree/product_scopes.rb`)
- [x] T009 [spree/core] `Spree::DefaultPrice` concern — deprecated legacy single-currency price shim (`spree/core/app/models/concerns/spree/default_price.rb`)
- [x] T010 [spree/core] `Spree::Products::Find` finder for filter/search/sort composition (`spree/core/app/finders/spree/products/find.rb`)

**Checkpoint**: Core model layer complete — all user stories build on this.

---

## Phase 3: User Story 1 - Merchant creates a simple product (Priority: P1) 🎯 MVP

### Tests for User Story 1

- [x] T011 [P] [US1] RSpec model spec covering master-variant auto-provisioning and `Product#prices=`/`Product#find_or_build_master` in `spree/core/spec/models/spree/product_spec.rb`
- [x] T012 [P] [US1] API integration spec (happy path + 422) for `POST /api/v3/admin/products` in `spree/api/spec/integration/products_spec.rb`

### Implementation for User Story 1

- [x] T013 [US1] `Product#prices=` delegating to master variant (`spree/core/app/models/spree/product.rb`)
- [x] T014 [US1] `Admin::ProductsController#permitted_params` accepting flat `name/description/slug/status/prices[]` etc. (`spree/api/app/controllers/spree/api/v3/admin/products_controller.rb`)
- [x] T015 [US1] `packages/dashboard` "New Product" route + form cards (`routes/_authenticated/$storeId/products/new.tsx`, `components/spree/products/product-form-cards.tsx`)
- [x] T016 [US1] `useCreateProduct`/`useProduct` hooks (`packages/dashboard/src/hooks/use-product.ts`)

**Checkpoint**: Simple product creation fully functional end-to-end.

---

## Phase 4: User Story 2 - Configurable product with option types/variants (Priority: P1)

### Tests for User Story 2

- [x] T017 [P] [US2] RSpec spec for `Variant#set_option_value`/`options=`/option-value uniqueness validation in `spree/core/spec/models/spree/variant_spec.rb`
- [x] T018 [P] [US2] Vitest unit test for variant-matrix cartesian generation in `packages/dashboard/src/components/spree/products/variants-matrix.test.ts`

### Implementation for User Story 2

- [x] T019 [US2] `Product#variants=`/`#apply_variants` bulk sync (add/update/remove-by-omission, master upsert for no-option entries) (`spree/core/app/models/spree/product.rb`)
- [x] T020 [US2] `Variant#prices=`/`#stock_items=`/`#set_price`/`#set_stock` per-variant sync (`spree/core/app/models/spree/variant.rb`)
- [x] T021 [US2] `OptionType#option_values=` autosave-backed sync with `mark_for_destruction` (`spree/core/app/models/spree/option_type.rb`)
- [x] T022 [US2] Nested `variants[]` permitted params incl. `options`, `prices`, `stock_items` on Admin API (`spree/api/app/controllers/spree/api/v3/admin/products_controller.rb`)
- [x] T023 [US2] `variants-options-builder.tsx` (option type/value matrix builder), `variants-matrix.ts` (cartesian generation), `variants-section.tsx` (grid), `variant-edit-sheet.tsx` (per-variant edit) in `packages/dashboard/src/components/spree/products/`
- [x] T024 [US2] `options.tsx` admin route for standalone OptionType/OptionValue management (`packages/dashboard/src/routes/_authenticated/$storeId/products/options.tsx`)

**Checkpoint**: Full variant matrix generation and per-variant editing functional.

---

## Phase 5: User Story 3 - Product lifecycle status management (Priority: P2)

### Tests for User Story 3

- [x] T025 [P] [US3] RSpec spec for status state machine transitions and webhook/event firing in `spree/core/spec/models/spree/product_spec.rb`

### Implementation for User Story 3

- [x] T026 [US3] Status state machine (`draft`/`active`/`archived` events + `after_transition` webhook/event hooks) (`spree/core/app/models/spree/product.rb`)
- [x] T027 [US3] `Admin::ProductsController#bulk_status_update` with `:activate` CanCanCan gating (`spree/api/app/controllers/spree/api/v3/admin/products_controller.rb`)
- [x] T028 [US3] `publishing-card.tsx` status/publish UI (`packages/dashboard/src/components/spree/products/publishing-card.tsx`)
- [x] T029 [US3] `useBulkProductStatusUpdate` hook (`packages/dashboard/src/hooks/use-products.ts`)

**Checkpoint**: Lifecycle status transitions functional via API and SPA.

---

## Phase 6: User Story 4 - Storefront browse/filter (Priority: P2)

### Tests for User Story 4

- [x] T030 [P] [US4] API integration spec for `GET /api/v3/store/products` filtering/availability in `spree/api/spec/integration/store/products_spec.rb`

### Implementation for User Story 4

- [x] T031 [US4] `Store::ProductsController` scoped to `available`/`.active`, slug-or-prefixed-ID lookup (`spree/api/app/controllers/spree/api/v3/store/products_controller.rb`)
- [x] T032 [US4] `ProductSerializer`/`VariantSerializer` (Store) computed fields: `purchasable`, `in_stock`, `backorderable`, `available`, `preorder`, `price`/`original_price` via price-list resolution (`spree/api/app/serializers/spree/api/v3/product_serializer.rb`, `variant_serializer.rb`)
- [x] T033 [US4] `Product.available`/`.active`/`.for_channel`/`.with_option_value_ids`/price-range scopes (`spree/core/app/models/concerns/spree/product_scopes.rb`)

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T034 [P] Product/variant duplication service wired to `POST /clone` (Admin API + legacy admin) (`spree/core/app/services/spree/products/duplicator.rb`)
- [x] T035 [P] Bulk category/channel/tag operations with search-index re-enqueue after `update_all`/`touch_all` (`spree/api/app/controllers/spree/api/v3/admin/products_controller.rb`)
- [x] T036 Full backend suite: `cd spree/core && bundle exec rspec` and `cd spree/api && bundle exec rspec`
- [x] T037 Full frontend suite: `pnpm typecheck && pnpm lint && pnpm test` at workspace root

---

## Dependencies & Execution Order

Foundational model layer (Phase 2) blocks all user stories. US1 (simple product) is the base path; US2 (variants) builds directly on the same `Product`/`Variant` models but is independently testable via its own API payload shape. US3 (status) and US4 (storefront read) are independent of each other and of US2, sharing only the Phase 2 foundation.

## Notes

This tasks.md is a **retrospective record**, generated during brownfield spec-kit adoption. All items reflect code already present in the repository at the time of migration (2026-08-24). Future work in this area should start a new spec-kit feature (or update this one via `/speckit-clarify` / `/speckit-plan`) rather than treating these tasks as pending.
