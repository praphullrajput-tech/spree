---
status: migrated
---

# Spec: Categories (Taxon Hierarchy)

**Feature**: Hierarchical product categorization using nested-set trees; `Spree::Category` as the canonical model (aliasing `Spree::Taxon`)

---

## Overview

Categories provide the hierarchical taxonomy for organizing products. The data model is a nested-set tree (`acts_as_nested_set`). In 5.5 the `Spree::Category` constant alias was shipped alongside a dedicated Admin API (`/categories`) that does not require a parent `Taxonomy`. The legacy `Spree::Taxon` model remains as the database table owner until the 6.0 rename. A `reposition` action handles nested-set moves. The 6.0 plan splits rule-based/automatic taxons into a separate `Spree::Collection` model.

---

## User Scenarios

### US1 — Merchant creates a top-level category
Given the Categories page,
When the merchant creates "Men's Clothing",
Then it appears as a root node in the tree; its `permalink` is auto-generated from the name.

### US2 — Merchant creates a sub-category
Given a parent category "Men's Clothing",
When the merchant creates "T-Shirts" as a child,
Then it appears nested under the parent; its permalink is `mens-clothing/t-shirts`.

### US3 — Merchant repositions a category in the tree
Given an existing category hierarchy,
When the merchant drags a category to a new parent or position,
Then `PATCH /api/v3/admin/categories/:id/reposition` updates the nested-set correctly.

### US4 — Merchant assigns products to a category
Given a category "T-Shirts",
When the merchant adds products via the category products panel,
Then `POST /api/v3/admin/categories/:id/products` creates the association.

### US5 — Customer browses a category on the storefront
Given a published category with products,
When the Store API is called with `taxon_id` filter,
Then only products in that category (including descendants) are returned.

---

## Functional Requirements

### FR-001 — Category model
`Spree::Category < Spree::Taxon` alias. `has_prefix_id :ctg`. `acts_as_nested_set dependent: :destroy, counter_cache: :children_count`. `store_id` required (no `taxonomy_id` needed). `name`, `permalink`, `pretty_name` (path display), `hide_from_nav`, `depth`, `lft`, `rgt`, `children_count`. `has_one_attached :image` and `:square_image`. `include TranslatableResource`.

### FR-002 — Taxonomy model (legacy)
`Spree::Taxonomy` is the legacy container for taxon trees. Required for `Spree::Taxon` but bypassed by `Spree::Category`. Dropped in 6.0.

### FR-003 — Admin API — CRUD
`Admin::CategoriesController` — full CRUD scoped to `current_store.categories`. `reposition` action (PATCH) moves node in nested set.

### FR-004 — Admin API — Products nested endpoint
`Admin::Categories::ProductsController` — `POST` to add products; `DELETE` to remove; `index` to list products in category.

### FR-005 — Admin SPA
`products/categories/index.tsx` — tree view of categories; `new.tsx` — create form; `$categoryId.tsx` — detail with products table. Drag-to-reorder handled by `reposition` API.

### FR-006 — 6.0 — Collections (PENDING)
Rule-based and automatic taxons extracted into `Spree::Collection` + `Spree::CollectionRule` models. `Spree::Taxon` table renamed to `spree_categories`. `Spree::Taxonomy` dropped.

---

## Success Criteria

- [ ] `GET /api/v3/admin/categories` returns nested tree with `lft`/`rgt`/`depth`
- [ ] `POST /api/v3/admin/categories` creates a root or child category
- [ ] `PATCH /api/v3/admin/categories/:id/reposition` moves node correctly
- [ ] `GET /api/v3/store/products?q[taxon_id_eq]=ctg_abc` returns products in category + descendants
- [ ] SPA tree view reflects hierarchy with create/edit/delete/reposition

---

## Out of Scope

- Collections (rule-based automatic product grouping) — 6.0 pending
- Taxonomy management UI — legacy admin only; dropped in 6.0
