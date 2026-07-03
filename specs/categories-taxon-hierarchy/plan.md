# Implementation Plan: Categories (Taxon Hierarchy)

**Branch**: `main` | **Date**: 2026-05-20 | **Spec**: [spec.md](spec.md)

**Status**: 5.5 shipped; 6.0 pending

---

## Summary

Split the overloaded `Taxon` model into two distinct concepts: **Category** (hierarchical classification) and **Collection** (flat/rule-based merchandising). In 5.5, `Spree::Category` was introduced as a constant alias of `Spree::Taxon`, and the Store and Admin APIs were updated to use `categories` naming throughout. The SPA admin UI for category management shipped with full CRUD and tree repositioning. In 6.0, the `spree_taxons` table renames to `spree_categories`, `Spree::Taxonomy` is dropped, and `Spree::Collection` is introduced as a first-class model.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Serialization** | Alba → Typelizer |
| **Tree structure** | `awesome_nested_set` (`lft`, `rgt`, `depth`, `parent_id`, `children_count`) |
| **Translations** | Mobility gem (`name`, `pretty_name`, `description`, `permalink`) |
| **Scope** | Full-stack (5.5 complete) + 6.0 table rename + Collection model pending |

---

## Key Decisions

1. **`Spree::Category` is an alias in 5.5, a rename in 6.0.** Using a constant alias (`Spree::Category = Spree::Taxon`-subclass) in 5.5 means zero schema changes and full backward compatibility while controllers and serializers use the new name.
2. **`Spree::Taxonomy` is deprecated, not replaced.** Categories in 6.0 are directly `store_id`-scoped — children copy from parent. The Taxonomy's only function (container + root sync) is absorbed by the category tree itself.
3. **Collections own all automatic/rule-based features.** The `automatic` flag, `rules_match_policy`, `sort_order`, and `TaxonRule` association stay on `Spree::Taxon` until 6.0, when they move to `Spree::Collection`.
4. **Prefix stays `ctg_`.** Already in use across the API — no client migration needed.
5. **Nested set stays.** `awesome_nested_set` with `acts_as_nested_set dependent: :destroy` — proven, no reason to change.
6. **`reposition` is a custom admin action** — moving a node in a nested set requires tree-aware recalculation that standard `update` cannot do safely.
7. **No Collection in 5.5.** Automatic taxons ("On Sale", "New Arrivals") keep working via the existing `TaxonRule` path until 6.0 introduces `Spree::Collection`.

---

## Constitution Check

- [x] **API-First**: Category API endpoints updated before SPA consumed them
- [x] **Read/Write Symmetry**: Serializer exposes `name`; controller accepts `name`; `label` alias maps to `name`
- [x] **Prefixed IDs**: All IDs prefixed `ctg_…`; `parent_id` uses `prefixed_id` in serializer
- [x] **Serializer Hierarchy**: `Admin::CategorySerializer` extends `V3::CategorySerializer`
- [x] **Type Pipeline**: Typelizer + Zod regen run after serializer changes
- [x] **Security**: CanCanCan `can :manage, Spree::Taxon`; store-scoped via `current_store.taxons`
- [x] **Namespace**: `Spree::Category`, `Spree::Taxonomy` — `Spree.base_class`
- [x] **Plan Conflicts**: Reviewed `6.0-product-types.md` (`ProductTypeCategory` uses `category_id` not `taxon_id`); `6.0-channels-catalogs-b2b.md`; no conflicts

---

## Project Structure

```text
# Backend — models
spree/core/app/models/spree/category.rb              ← constant alias + scope override
spree/core/app/models/spree/taxon.rb                 ← core nested set model
spree/core/app/models/spree/taxonomy.rb              ← deprecated container (6.0 removal)
spree/core/app/models/spree/taxon_rule.rb            ← STI rules (move to CollectionRule in 6.0)

# Backend — serializers
spree/api/app/serializers/spree/api/v3/category_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/category_serializer.rb

# Backend — controller
spree/api/app/controllers/spree/api/v3/admin/categories_controller.rb

# Backend — specs
spree/core/spec/models/spree/category_spec.rb
spree/core/spec/models/spree/taxon_spec.rb
spree/api/spec/integration/spree/api/v3/admin/categories_spec.rb

# Frontend
packages/dashboard/src/routes/_authenticated/$storeId/products/categories/
├── index.tsx
├── new.tsx
└── $categoryId.tsx
packages/dashboard/src/hooks/use-categories.ts
packages/dashboard/src/components/spree/categories/
packages/dashboard/e2e/categories.spec.ts
```

---

## Phase 0: Research (Complete)

- Existing `Spree::Taxon` model is the nested set root; all current code references `taxons`
- Store API v3 already used `categories` naming; Admin API added in this work
- `Spree::Classification` joins Product ↔ Taxon (renamed `ProductCategory` in 6.0)
- `awesome_nested_set` handles `lft`/`rgt`/`depth` recalculation; `reposition` must call `move_to_child_of` or `move_to_root`

---

## Phase 1: Backend — 5.5 (✅ Complete)

- `Spree::Category` constant alias with `manual` scope override
- `Admin::CategoriesController` with full CRUD + `reposition` action
- `CategorySerializer` (Store) and `Admin::CategorySerializer` (extends Store)
- `reposition` moves the nested set node using `awesome_nested_set`'s move methods
- CanCanCan abilities scoped to `Spree::Taxon` (covers alias)

---

## Phase 2: Frontend — 5.5 (✅ Complete)

- `use-categories.ts` TanStack Query wrappers
- Category routes: list, new, edit
- `components/spree/categories/` — hierarchy-aware UI components
- i18n keys in all 6 locale files
- E2E: `categories.spec.ts`

---

## Phase 3: 6.0 Pending

### 3a: Table + Model Rename

- Migration: rename `spree_taxons` → `spree_categories`, `spree_products_taxons` → `spree_product_categories`
- Rename column `taxon_id` → `category_id` on join table
- `Spree::Taxon` → `Spree::Category` (drop alias; full rename)
- `Spree::Classification` → `Spree::ProductCategory`
- Data migration rake: `spree:migrate_taxons_to_categories_and_collections`
- Drop `spree_taxonomies` table after data migration

### 3b: Collection Model

- New `Spree::Collection` model — flat, store-scoped, `acts_as_list`
- `Spree::ProductCollection` join table
- `Spree::TaxonRule` → `Spree::CollectionRule` rename
- Move `automatic`, `sort_order`, `rules_match_policy` from Category to Collection
- Admin API: `/api/v3/admin/collections` CRUD
- SPA: Collections section (separate from Categories)

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Custom `reposition` action (not standard `update`) | Moving nodes in a nested set requires tree-aware recalculation; `update(parent_id:)` alone would corrupt `lft`/`rgt`/`depth` | No Rails built-in handles nested set moves — `awesome_nested_set` provides the move API |
| `Spree::Category` alias (not subclass) in 5.5 | STI would break (`Spree::Category` rows stored as `Spree::Taxon` in `type` column) | Subclassing fought STI — constant alias is the only correct 5.5 approach |
