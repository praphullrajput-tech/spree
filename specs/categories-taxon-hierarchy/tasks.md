---

description: "Completed and pending task list for Categories (Taxon Hierarchy)"
---

# Tasks: Categories (Taxon Hierarchy)

**Status**: 5.5 work complete; 6.0 work pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Store serializers | `spree/api/app/serializers/spree/api/v3/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/products/categories/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Backend Foundation — 5.5 ✅

- [x] T001 Create `spree/core/app/models/spree/category.rb` — constant alias of `Spree::Taxon` with `manual` scope override; `store_id` enforcement; strip automatic/collection-related scopes
- [x] T002 Update `spree/core/app/models/spree/taxon.rb` — ensure `store_id` propagates to children on create; add `whitelisted_ransackable_attributes` for `name`, `permalink`, `store_id`, `parent_id`
- [x] T003 Update CanCanCan abilities — `can :manage, Spree::Taxon` covers `Spree::Category` via alias

**Checkpoint**: `bundle exec rspec spec/models/spree/category_spec.rb` passes ✅

---

## Phase 2: Backend API — 5.5 ✅

- [x] T004 [P] [US1/US2] Create Store serializer `spree/api/app/serializers/spree/api/v3/category_serializer.rb` — `id`, `name`, `permalink`, `parent_id` (prefixed), `is_root`, `is_child`, `is_leaf`, `children_count`, `position`, `hide_from_nav`, `image_url`, `square_image_url`, `custom_fields` expansion
- [x] T005 [P] [US1/US2] Create Admin serializer `spree/api/app/serializers/spree/api/v3/admin/category_serializer.rb` — extends Store; adds `lft`, `rgt`, `depth`, `products_count`, `meta_keywords`, `private_metadata`, `created_at`, `updated_at`; expandable `children` + `ancestors`
- [x] T006 [US1/US3] Create Admin controller `spree/api/app/controllers/spree/api/v3/admin/categories_controller.rb` — full CRUD + `reposition` action (calls `awesome_nested_set` move methods); validates no circular moves; scoped to `current_store.taxons`
- [x] T007 [US1] Add routes to `spree/api/config/routes.rb` — `resources :categories` with `member { patch :reposition }`
- [x] T008 [US1] Write integration spec `spree/api/spec/integration/spree/api/v3/admin/categories_spec.rb`
- [x] T009 Run `bundle exec rake rswag:specs:swaggerize`

**Checkpoint**: integration spec passes ✅

---

## Phase 3: Type Generation Pipeline — 5.5 ✅

- [x] T010 Run `cd spree/api && bundle exec rake typelizer:generate`
- [x] T011 Run `cd packages/sdk && pnpm generate:zod`
- [x] T012 Run `pnpm typecheck`

---

## Phase 4: Frontend — 5.5 ✅

- [x] T013 [P] [US1] Create hook `packages/dashboard/src/hooks/use-categories.ts` — `useCategories()`, `useCategory(id)`, `useCreateCategory()`, `useUpdateCategory(id)`, `useDeleteCategory()`, `useRepositionCategory()`
- [x] T014 [P] [US1] Create routes: `categories/index.tsx`, `categories/new.tsx`, `categories/$categoryId.tsx`
- [x] T015 [US2] Wire image upload for hero + square image on category edit form
- [x] T016 [US1/US2] Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.categories.*`
- [x] T017 [US1/US2] Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

**Checkpoint**: `pnpm typecheck && pnpm lint` pass ✅

---

## Phase 5: E2E — 5.5 ✅

- [x] T018 Write `packages/dashboard/e2e/categories.spec.ts` — create root → add child → reposition → delete
- [x] T019 Run `pnpm test:e2e` ✅

---

## Phase 6: Polish — 5.5 ✅

- [x] T020 [P] `bundle exec i18n-tasks normalize`
- [x] T021 [P] `pnpm lint && pnpm test`
- [x] T022 Verify no raw IDs in responses (`ctg_…` prefix on all)

---

## Phase 7: 6.0 — Table Rename + Collection Model (PENDING)

**⚠️ These tasks are NOT yet implemented. They are tracked here for planning.**

- [ ] T023 Create migration `*_rename_spree_taxons_to_categories.rb` — rename `spree_taxons` → `spree_categories`, `spree_products_taxons` → `spree_product_categories`, `spree_taxon_rules` → `spree_collection_rules`; rename column `taxon_id` → `category_id`; add `store_id` to categories; create `spree_collections` + `spree_product_collections` tables
- [ ] T024 Create rake task `spree:migrate_taxons_to_categories_and_collections` — set `store_id` on all categories; move automatic taxons to `Spree::Collection`; move `TaxonRules` to `CollectionRules`; idempotent
- [ ] T025 Rename `Spree::Category` from alias to real class (drop alias file; update class definition)
- [ ] T026 Rename `Spree::Classification` → `Spree::ProductCategory`; update associations on `Spree::Product` and `Spree::Category`
- [ ] T027 Create `Spree::Collection` model — flat, store-scoped, `acts_as_list`, `automatic` flag, `rules_match_policy`, `sort_order`, `collection_rules` association
- [ ] T028 Rename `Spree::TaxonRule` → `Spree::CollectionRule`; update STI subtypes
- [ ] T029 Create Admin API: `admin/collections_controller.rb` + `admin/collection_serializer.rb`
- [ ] T030 Add routes for collections: `resources :collections`
- [ ] T031 SPA: Collections routes + hook `use-collections.ts`
- [ ] T032 Drop `spree_taxonomies` table (after data migration run in production)

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| `Spree::Collection` model not yet implemented | High | Track in `docs/plans/6.0-replace-taxons-with-categories.md`; Phase 7 tasks above are the implementation checklist |
| Table still named `spree_taxons` in 5.5 | Medium | By design — rename is a 6.0 breaking change; no action before 6.0 |
| `TaxonRule` STI subtypes still under `Spree::TaxonRules::*` namespace | Low | Rename to `Spree::CollectionRules::*` in T028 above |
