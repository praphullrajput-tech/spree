---

description: "Task list for Categories — 5.5 API + SPA shipped; 6.0 rename + Collection split pending"
---

# Tasks: Categories (Taxon Hierarchy)

**Status**: Fully shipped in 5.5; 6.0 table rename + Collection pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/products/categories/` |
| Dashboard components | `packages/dashboard/src/components/spree/categories/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core + API + SPA ✅

- [x] T001 `spree/core/app/models/spree/taxon.rb` — `has_prefix_id :ctg`; `acts_as_nested_set`; `store_id`; `name`, `permalink`, `hide_from_nav`; `has_one_attached :image, :square_image`; `include TranslatableResource`
- [x] T002 `spree/core/app/models/spree/category.rb` — `< Spree::Taxon` alias; overrides `requires_taxonomy?` to return false; `store_id` required
- [x] T003 `spree/api/app/serializers/spree/api/v3/admin/category_serializer.rb` — `ctg_` prefix; name, permalink, depth, parent_id, children_count, image_url, timestamps
- [x] T004 `spree/api/app/controllers/spree/api/v3/admin/categories_controller.rb` — full CRUD; `reposition` action (PATCH)
- [x] T005 `spree/api/app/controllers/spree/api/v3/admin/categories/products_controller.rb` — products nested under category
- [x] T006 `packages/dashboard/src/routes/_authenticated/$storeId/products/categories/index.tsx` — tree view
- [x] T007 `packages/dashboard/src/routes/_authenticated/$storeId/products/categories/new.tsx` — create form with parent picker
- [x] T008 `packages/dashboard/src/routes/_authenticated/$storeId/products/categories/$categoryId.tsx` — detail with products table, edit sheet
- [x] T009 `packages/dashboard/src/schemas/category.ts`
- [x] T010 `packages/dashboard/e2e/categories.spec.ts` — CRUD; nested creation; reposition

**Checkpoint**: full category hierarchy management; reposition; products association ✅

---

## Phase 2: 6.0 — Collections + Rename (PENDING)

- [ ] T011 Rename `spree_taxons` → `spree_categories` table; update all references
- [ ] T012 Drop `Spree::Taxonomy` model and `spree_taxonomies` table
- [ ] T013 Introduce `Spree::Collection` model for automatic/rule-based product grouping
- [ ] T014 Introduce `Spree::CollectionRule` STI base + rule subclasses
- [ ] T015 Admin API: Collections CRUD + rule management
- [ ] T016 SPA: Collections page

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| Automatic/rule-based taxons not exposed in Category API | Low | By design; reserved for 6.0 Collection model |
| Taxonomy management no SPA | Low | By design; Taxonomy is dropped in 6.0; legacy admin covers it |
