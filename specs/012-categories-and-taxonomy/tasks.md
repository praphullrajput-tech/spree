---

description: "Task list template for feature implementation"
---

# Tasks: Categories & Taxonomy

**Input**: Design documents from `/specs/012-categories-and-taxonomy/`

**Prerequisites**: plan.md, spec.md

**Tests**: RSpec/Vitest coverage already exists for parts of this feature (see Phase 3 tests); no dedicated Playwright e2e spec was located.

**Organization**: Tasks are grouped by user story, matching spec.md. This file is a reverse-engineered record — all tasks are marked complete (`[x]`) because the feature is already implemented; it documents what was built and where, for future incremental work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Could have run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)

## Path Conventions

Real module paths per plan.md's Project Structure:

- Backend model/finder: `spree/core/app/{models,finders}/spree/...`, spec in `spree/core/spec/...`
- API endpoint: `spree/api/app/{controllers,serializers}/spree/api/v3/{store,admin}/...`
- Admin SPA: `packages/dashboard/src/{routes,hooks,schemas,components}/...`

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core`/`spree/api` boot cleanly with the nested-set (`awesome_nested_set`) and tagging (`acts_as_taggable_on`) gem dependencies present in the gemspec
- [x] T002 [P] Baseline backend: `cd spree/core && bundle exec rspec spec/models/spree/{taxon,category,taxonomy,classification}_spec.rb`
- [x] T003 [P] Baseline frontend: `pnpm typecheck && pnpm lint` covering `packages/dashboard/src/components/spree/categories/**`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 [spree/core] `spree_taxons` nested-set table (`parent_id`, `lft`, `rgt`, `depth`, `children_count`, `store_id`, `taxonomy_id`) — pre-existing schema, no new migration in this feature
- [x] T005 [spree/core] `Spree::Taxon < Spree.base_class` with `acts_as_nested_set`, `Spree::SingleStoreResource`, `has_prefix_id :ctg`, `Spree::TranslatableResource`/`TranslatableResourceSlug`, `Spree::Metafields`, `Spree::Metadata`, `Spree::MemoizedData` (`spree/core/app/models/spree/taxon.rb`)
- [x] T006 [spree/core] `Spree::Category < Taxon` alias with `default_scope { manual }` and `requires_taxonomy? => false` (`spree/core/app/models/spree/category.rb`)
- [x] T007 [spree/api] Ransack allowlist on `Taxon` (`whitelisted_ransackable_associations = %w[taxonomy parent]`, `whitelisted_ransackable_attributes` incl. `name permalink automatic depth is_root children_count classification_count products_count pretty_name hide_from_nav parent_id`) and on `ActsAsTaggableOn::Tag` (`id name` only, via `TagDecorator`)
- [x] T008 [packages/dashboard] i18next keys under `admin.categories.*` (messages: created/updated/deleted/move_failed) and `admin.fields.*` referenced by `category-form.tsx`/`use-categories.ts`

**Checkpoint**: Foundation (nested-set model, Category alias, Ransack allowlists, i18n keys) in place — confirmed present in current codebase.

---

## Phase 3: User Story 1 - Merchant builds and maintains a category tree (Priority: P1) 🎯 MVP

**Goal**: CRUD + reposition (move/reparent) of hierarchical categories via the Admin API and SPA tree UI.

**Independent Test**: `POST /api/v3/admin/categories`, `PATCH .../:id/reposition`, `DELETE .../:id` round-trip correctly against a running backend.

### Tests for User Story 1

- [x] T010 [P] [US1] RSpec model spec covering nested-set behavior, uniqueness scoping, and `recalculate_products_count`/`recalculate_products_count_after_move` in `spree/core/spec/models/spree/taxon_spec.rb`
- [x] T011 [P] [US1] RSpec model spec for the `Category` alias (`default_scope { manual }`, `requires_taxonomy?`) in `spree/core/spec/models/spree/category_spec.rb`
- [x] T012 [P] [US1] Vitest unit test for tree flatten/projection/reorder math in `packages/dashboard/src/components/spree/categories/category-tree-utils.test.ts`

### Implementation for User Story 1

- [x] T013 [P] [US1] Nested-set model + validations + callbacks (permalink generation, ancestor/products_count recompute, taxonomy sync) in `spree/core/app/models/spree/taxon.rb`
- [x] T014 [US1] Finder for filtering/searching taxons (`by_ids`, `by_parent`, `by_parent_permalink`, `by_taxonomy`, `by_roots`, `by_name`) in `spree/core/app/finders/spree/taxons/find.rb`
- [x] T015 [US1] Admin controller: CRUD + `reposition` action (parent/index move via `move_to_child_with_index`/`move_to_root_at_index`, clamped index) in `spree/api/app/controllers/spree/api/v3/admin/categories_controller.rb` (depends on T013)
- [x] T016 [US1] Admin serializer (`metadata`, `pretty_name`, `lft`, `rgt`, `products_count`, timestamps, admin-resourced `parent`/`children`/`ancestors`) in `spree/api/app/serializers/spree/api/v3/admin/category_serializer.rb`
- [x] T017 [US1] Type-generation pipeline output consumed as `packages/admin-sdk/src/types/generated/Category.ts` (generated, not hand-written)
- [x] T018 [US1] Dashboard tree UI (dnd-kit drag reorder + reparent, collapse/expand) in `packages/dashboard/src/components/spree/categories/category-tree.tsx` + `category-tree-utils.ts`, wired via `useRepositionCategory` in `packages/dashboard/src/hooks/use-categories.ts`
- [x] T019 [US1] Dashboard routes for list/create/edit in `packages/dashboard/src/routes/_authenticated/$storeId/products/categories/{index,new,$categoryId}.tsx`, form in `packages/dashboard/src/components/spree/categories/category-form.tsx`, Zod schema in `packages/dashboard/src/schemas/category.ts`

**Checkpoint**: User Story 1 (tree CRUD + reposition) is fully implemented and independently verifiable.

---

## Phase 4: User Story 2 - Merchant classifies products into categories (Priority: P1)

**Goal**: Manual product<->category membership with ordering, add/remove (incl. bulk), from the category detail page.

**Independent Test**: Add/remove/reorder products under a category via the Admin API and confirm `products_count`/ordering.

### Tests for User Story 2

- [x] T020 [P] [US2] RSpec model spec for `Spree::Classification` ordering/uniqueness/counter behavior in `spree/core/spec/models/spree/classification_spec.rb`
- [x] T021 [P] [US2] API integration coverage for category<->product endpoints (happy path) in `spree/api/spec/integration/categories_spec.rb` (if present alongside the products sub-controller spec)

### Implementation for User Story 2

- [x] T022 [P] [US2] Ordered join model `Spree::Classification` (`has_many :classifications, -> { order(:position) }`) in `spree/core/app/models/spree/taxon.rb` associations + its own model file
- [x] T023 [US2] Category-scoped products controller (list/add/remove/reposition) in `spree/api/app/controllers/spree/api/v3/admin/categories/products_controller.rb` (depends on T022)
- [x] T024 [US2] Bulk add/remove endpoints reused from the products controller (`bulkAddToCategories`/`bulkRemoveFromCategories`) consumed via `packages/dashboard/src/hooks/use-categories.ts`
- [x] T025 [US2] Dashboard category-products panel (list, add, remove, reorder) in `packages/dashboard/src/components/spree/categories/category-products-card.tsx`

**Checkpoint**: User Story 2 (product classification) works independently of the tree-management UI.

---

## Phase 5: User Story 3 - Storefront customer browses/filters by category (Priority: P2)

**Goal**: Read-only, SEO-friendly Store API surface for categories.

**Independent Test**: `GET /api/v3/store/categories/:permalink` and `GET /api/v3/store/categories/:ctg_id` both resolve; expand params don't recurse infinitely.

### Tests for User Story 3

- [x] T026 [P] [US3] API integration spec for Store category lookup by permalink + prefixed id, locale fallback, in `spree/api/spec/integration/categories_spec.rb`

### Implementation for User Story 3

- [x] T027 [US3] Store controller: `find_resource` branching on `ctg_` prefix vs. i18n permalink lookup with default-locale fallback, HTTP caching in `spree/api/app/controllers/spree/api/v3/store/categories_controller.rb`
- [x] T028 [US3] Store serializer: customer-facing fields only, `is_root`/`is_child`/`is_leaf`, `image_url`/`square_image_url`, non-recursive `parent`/`children`/`ancestors` expansion in `spree/api/app/serializers/spree/api/v3/category_serializer.rb`

**Checkpoint**: User Story 3 (storefront read surface) works independently of admin CRUD.

---

## Phase 6: User Story 4 - Admin tags arbitrary resources for freeform search (Priority: P3)

**Goal**: Freeform, non-hierarchical tagging complementing the category tree.

**Independent Test**: `GET /admin/tags/select_options?q=...&taggable_type=Spree::Product` returns matching tags.

### Tests for User Story 4

- [x] T029 [P] [US4] Coverage for `Spree::Admin::TagsController#select_options` filtering/scoping (context + taggable_type) — legacy Rails admin controller spec

### Implementation for User Story 4

- [x] T030 [P] [US4] `acts_as_taggable_on :tags, :labels` on `Spree::Product` (`spree/core/app/models/spree/product.rb`) and on `Spree::Order`
- [x] T031 [US4] Ransack allowlist decorator restricting `Tag` to `id`/`name` in `spree/core/app/models/acts_as_taggable_on/tag_decorator.rb`
- [x] T032 [US4] Legacy admin tag search endpoint + helpers in `spree/admin/app/controllers/spree/admin/tags_controller.rb` and `spree/admin/app/helpers/spree/admin/tags_helper.rb`

**Checkpoint**: User Story 4 (tagging) is independent of both the category tree and the Store API surface.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T033 [P] `docs/plans/6.0-replace-taxons-with-categories.md` already documents the pending table-rename/Collection split — no update needed for this migration, only referenced from spec.md's Migration Notes
- [x] T034 Full backend suite: `cd spree/core && bundle exec rspec` covering taxon/category/taxonomy/classification specs
- [x] T035 Full frontend suite: `pnpm typecheck && pnpm lint && pnpm test` at workspace root, covering `category-tree-utils.test.ts`
- [ ] T036 [P] `packages/dashboard && pnpm test:e2e` for the categories admin flow — **gap**: no `e2e/categories.spec.ts` was found during this migration; left unchecked as a follow-up rather than falsely marked done
- [x] T037 Verify locale keys (`admin.categories.*`) present in all locale files under `packages/dashboard/src/locales/` (parity check, not a new-key addition)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → all User Stories (Phases 3–6), which were independently implementable given the foundation → **Polish (Phase 7)**.

### User Story Dependencies

- **US1 (P1, tree CRUD)**: No dependency on other stories.
- **US2 (P1, classification)**: Depends on a category existing (US1) but is independently testable once one does.
- **US3 (P2, storefront read)**: Depends on categories/classifications existing (US1/US2 data) but its own controller/serializer code is independent.
- **US4 (P3, tagging)**: Fully independent of Taxon/Category — different model, different controller stack.

### Parallel Opportunities

- All `[P]`-marked test tasks per story could have run in parallel (different files).
- US1, US2, US3, US4 implementation work touches disjoint controller/serializer/model files and could have proceeded in parallel once Phase 2 was done.

---

## Notes

- This tasks.md is a **retrospective record**, not a forward plan — every task reflects code already found in the repository during this brownfield migration.
- T036 is intentionally left `[ ]` (incomplete) because no Playwright e2e spec for the categories flow was located — this is a genuine gap, not a modeling omission, and is called out again in spec.md's Migration Notes.
- No destructive or new-file changes were made outside `specs/012-categories-and-taxonomy/` while producing this record.
