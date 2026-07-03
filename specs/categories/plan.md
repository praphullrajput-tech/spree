# Implementation Plan: Categories (Taxon Hierarchy)

**Branch**: `main` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Status**: 5.5 API bridge + Category alias shipped; 6.0 table rename + Collection split pending

---

## Summary

Categories are hierarchical product groupings using a nested-set tree. `Spree::Category < Spree::Taxon` ships in 5.5 as a constant alias pointing to the same table (`spree_taxons`). The Admin API exposes `/categories` without requiring a parent `Taxonomy`. The 6.0 plan renames the table and splits rule-based taxons into `Spree::Collection`.

---

## Key Decisions

1. **`Spree::Category < Spree::Taxon` — same table, new interface.** The alias lets us ship the clean `Category` API surface in 5.5 without a migration. Rails STI uses `type` column discrimination; `Spree::Category` overrides `requires_taxonomy?` to return `false`. The 6.0 table rename (`spree_taxons` → `spree_categories`) happens later.

2. **`acts_as_nested_set` not `ancestry` gem.** Nested sets use `lft`/`rgt` columns for O(1) subtree queries. The `reposition` API action wraps the `move_to_child_of` / `move_to_right_of` nested-set methods.

3. **`reposition` is a dedicated action, not a PUT on position.** Moving a node in a nested set requires updating many rows (shifting lft/rgt values). A dedicated `reposition` endpoint makes the intent explicit and avoids race conditions from concurrent position writes.

4. **No Taxonomy required for Category.** The legacy `Spree::Taxon` model requires a parent `Taxonomy` container. `Spree::Category` overrides this requirement — `store_id` is the scope boundary instead.

5. **Rule-based/automatic taxons excluded from Category API.** The `automatic`, `taxon_rules`, and `rules_match_policy` columns exist on the table but are not exposed in the `categories` API. These are reserved for the 6.0 `Collection` model.

---

## Constitution Check

- [x] **Prefixed IDs**: `ctg_` on both Category and Taxon (same model)
- [x] **API-First**: Admin API before SPA
- [x] **Serializer Hierarchy**: `Admin::CategorySerializer` extends `V3::CategorySerializer`
- [x] **Security**: CanCanCan; `current_store.categories` scope
- [x] **Plan Conflicts**: `6.0-replace-taxons-with-categories.md` — 5.5 alias shipped; 6.0 rename + Collection pending

---

## Project Structure

```text
spree/core/app/models/spree/taxon.rb                                        ← ctg_ prefix, nested set
spree/core/app/models/spree/category.rb                                     ← < Taxon alias
spree/core/app/models/spree/taxonomy.rb                                     ← legacy container (6.0: dropped)
spree/api/app/controllers/spree/api/v3/admin/categories_controller.rb       ← CRUD + reposition
spree/api/app/controllers/spree/api/v3/admin/categories/products_controller.rb
spree/api/app/serializers/spree/api/v3/admin/category_serializer.rb
packages/dashboard/src/routes/_authenticated/$storeId/products/categories/
packages/dashboard/src/components/spree/categories/
packages/dashboard/e2e/categories.spec.ts
```

---

## Phase 1: Core + API + SPA (✅ Complete — 5.5)

## Phase 2: 6.0 — Collections + Rename (PENDING)

- Table rename `spree_taxons` → `spree_categories`
- `Spree::Taxonomy` dropped
- `Spree::Collection` + `Spree::CollectionRule` for automatic grouping
- Collections API surface
