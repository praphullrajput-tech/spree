# Implementation Plan: Categories & Taxonomy

**Branch**: `012-categories-and-taxonomy` | **Date**: 2026-08-25 | **Spec**: `specs/012-categories-and-taxonomy/spec.md`

**Input**: Feature specification from `/specs/012-categories-and-taxonomy/spec.md`

**Note**: This document reverse-engineers an already-implemented feature (brownfield migration); it records the plan as executed, not a forward-looking design.

## Summary

Spree's hierarchical product classification is implemented as `Spree::Taxon`, a nested-set model that today serves two purposes: (1) manual, hierarchical categories, publicly aliased as `Spree::Category` and exposed via `categories` endpoints in both the Store and Admin API v3, and (2) automatic/rule-based "collection-like" taxons (`automatic` + `TaxonRule`) still reachable only through the legacy `Spree::Taxon`/Rails admin taxonomy UI. A separate freeform tagging mechanism (`acts_as_taggable_on`) rounds out "taxonomy" in the broad sense. The Admin API's `CategoriesController` and its `permitted_params` already enforce the Category/Collection boundary from `docs/plans/6.0-replace-taxons-with-categories.md` at the API layer, ahead of the underlying model/table split, which remains pending for 6.0.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`) and TypeScript (React SPA, `packages/dashboard`) — both sides touched.

**Primary Dependencies**: Backend: `awesome_nested_set` (nested set tree), `acts_as_taggable_on` (tags/labels), `FriendlyId` (permalink slugs), Mobility/`Spree::TranslatableResource` (i18n), Action Text (`description`), Alba serializers, CanCanCan, Ransack. Frontend: `@dnd-kit/core`/`@dnd-kit/sortable` (drag-reorder tree), TanStack Query, React Hook Form + Zod, `@spree/dashboard-ui`/`@spree/dashboard-core`.

**Storage**: PostgreSQL/SQLite3 via ActiveRecord — `spree_taxons` (nested set: `parent_id`, `lft`, `rgt`, `depth`, `children_count`), `spree_taxonomies`, `spree_products_taxons` (Classification join), `spree_taxon_rules`, `tags`/`taggings` (acts_as_taggable_on).

**Testing**: RSpec (`spree/core/spec/models/spree/{taxon,category,taxonomy,classification}_spec.rb`, `spree/api/spec/integration/categories_spec.rb`), Vitest (`packages/dashboard/src/components/spree/categories/category-tree-utils.test.ts`), Playwright (no dedicated `categories.spec.ts` located as of this migration — see Migration Notes gap).

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`) consumed by the Spree host app; React SPA (`packages/dashboard`) against the Admin API.

**Project Type**: Monorepo — touches `spree/core`, `spree/api`, `packages/dashboard`, and generated types in `packages/admin-sdk`.

**Performance Goals**: N/A — documenting existing behavior, no new performance targets introduced.

**Constraints**: Nested-set moves must recompute `products_count` for both the source and destination ancestor chains without a full-tree rescan (see `Taxon.recalculate_products_count`); Category API must never read/write the automatic/collection-bound columns (`automatic`, `rules_match_policy`, `sort_order`, `taxon_rules`, `taxonomy_id`).

**Scale/Scope**: One nested-set tree per store (plus taxonomy-backed legacy trees); category depth/breadth unbounded by the model, bounded in practice by admin UX (SPA tree renders collapsed by default, one level at a time).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Pass. Touches `spree/core` (models/finder), `spree/api` (Store + Admin controllers/serializers), `packages/dashboard` (routes/hooks/components), and generated `packages/admin-sdk` types — each through its documented layer (API as the only cross-boundary path from the SPA into the backend). No direct model access from the SPA was found.
- **II. Admin API Is the Only Frontend Data Source**: Pass. `packages/dashboard/src/hooks/use-categories.ts` calls only `adminClient.categories.*`; no server-rendered HTML or direct model reach found.
- **III. Read/Write Field Symmetry**: Pass. `Admin::CategoriesController#permitted_params` permits exactly `name`, `description`, `permalink`, `meta_title`, `meta_description`, `meta_keywords`, `hide_from_nav`, `image`, `square_image`, `custom_fields`, `parent_id` — matching what `CategorySerializer`/`Admin::CategorySerializer` expose on read. No field-name mismatch (e.g. no `label`/`presentation`-style bridge needed here).
- **IV. Test-Backed**: Partial. RSpec model/finder specs and a Vitest unit spec for `category-tree-utils.ts` exist; no Playwright e2e spec for the categories admin flow was located in `packages/dashboard/e2e/` — flagged as a gap in Migration Notes rather than silently assumed.
- **V. Translations and Prefixed IDs**: Pass. Categories use `has_prefix_id :ctg` throughout (API responses and request params); dashboard strings run through i18next (`admin.categories.*`, `admin.fields.*` keys referenced in `use-categories.ts`/`category-form.tsx`).
- **VI. `docs/plans/` for Architectural Changes**: Pass (documented, not newly introduced). `docs/plans/6.0-replace-taxons-with-categories.md` governs this area; its "Constraints on Current Work" section (use `categories` in new API code, don't add new `TaxonRule` subtypes, don't add new Taxonomy-dependent features) already binds the current implementation and is carried into this spec's Migration Notes.

No violations requiring Complexity Tracking — this plan documents existing, already-constitution-conformant code.

## Project Structure

### Documentation (this feature)

```text
specs/012-categories-and-taxonomy/
├── plan.md              # This file
├── spec.md              # Feature specification (already written)
└── tasks.md             # Reverse-engineered task record
```

### Source Code (repository root)

```text
# spree/core — models, finder, tag decorator
spree/core/
├── app/models/spree/taxon.rb                          # Ctg nested-set base model (category + automatic/taxonomy behavior)
├── app/models/spree/category.rb                        # `class Category < Taxon`, default_scope { manual }, requires_taxonomy? false
├── app/models/spree/taxonomy.rb                         # Legacy per-store named container for a taxon tree
├── app/models/spree/classification.rb                  # Product<->Taxon ordered join
├── app/models/spree/taxon_rule.rb (+ taxon_rules/*)     # STI automatic-taxon rules
├── app/models/acts_as_taggable_on/tag_decorator.rb      # Ransack allowlist on ActsAsTaggableOn::Tag
├── app/finders/spree/taxons/find.rb                     # Ransack-style filter finder (ids, parent, taxonomy, name, roots)
└── spec/models/spree/{taxon,category,taxonomy,classification}_spec.rb

# spree/api — Store & Admin REST API v3
spree/api/
├── app/controllers/spree/api/v3/store/categories_controller.rb        # Read-only, permalink/prefixed-id resolution
├── app/controllers/spree/api/v3/admin/categories_controller.rb        # Full CRUD + reposition (nested-set move)
├── app/controllers/spree/api/v3/admin/categories/products_controller.rb  # Category<->product membership + reposition
├── app/serializers/spree/api/v3/category_serializer.rb                # Store-facing fields
├── app/serializers/spree/api/v3/admin/category_serializer.rb          # + metadata, lft/rgt, products_count, timestamps
└── spec/integration/categories_spec.rb (if present — see tasks.md)

# packages/dashboard — admin SPA routes/forms
packages/dashboard/src/
├── routes/_authenticated/$storeId/products/categories/{index,new,$categoryId}.tsx
├── hooks/use-categories.ts                              # CRUD + reposition + product-membership hooks
├── schemas/category.ts                                   # Zod form schema, form<->API mapping
├── components/spree/categories/
│   ├── category-form.tsx                                # Main/sidebar form panels
│   ├── category-tree.tsx / category-tree-utils.ts        # dnd-kit tree (reorder + reparent)
│   ├── category-list.tsx                                 # Flat search-mode list
│   ├── category-products-card.tsx                        # Per-category product membership panel
│   └── category-image-field.tsx                          # Image/square-image upload field
└── components/spree/categories/category-tree-utils.test.ts  # Vitest coverage for tree flatten/projection

# packages/admin-sdk — generated types (not hand-written)
packages/admin-sdk/src/types/generated/Category.ts
```

**Structure Decision**: Full-stack feature already spanning `spree/core` (model layer, where the Category/Taxon aliasing lives), `spree/api` (where the Category/Collection boundary is already enforced ahead of the model split), and `packages/dashboard` (SPA tree/form UI) + generated `packages/admin-sdk` types. No `packages/dashboard-ui`/`dashboard-core` changes were needed — the tree/table UI composes existing primitives.

## Complexity Tracking

> No Constitution Check violations — table intentionally left empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
