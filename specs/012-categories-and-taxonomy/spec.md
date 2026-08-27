# Feature Specification: Categories & Taxonomy

**Feature Branch**: `012-categories-and-taxonomy`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — no original user description. Source: `spree/core/app/models/spree/{category,taxon,taxonomy,classification}.rb`, `spree/core/app/models/acts_as_taggable_on/tag_decorator.rb`, `spree/core/app/finders/spree/taxons/find.rb`, `spree/admin/app/controllers/spree/admin/{taxons_controller,tags_controller}.rb`, `spree/admin/app/helpers/spree/admin/{tags_helper,taxons_helper}.rb`, `spree/api/app/controllers/spree/api/v3/{store,admin}/categories_controller.rb`, `spree/api/app/controllers/spree/api/v3/admin/categories/products_controller.rb`, `spree/api/app/serializers/spree/api/v3/{category_serializer.rb,admin/category_serializer.rb}`, `packages/dashboard/src/{components/spree/categories/**,hooks/use-categories.ts,schemas/category.ts,routes/_authenticated/$storeId/products/categories/**}`, `docs/plans/6.0-replace-taxons-with-categories.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merchant builds and maintains a category tree (Priority: P1)

A store admin creates, renames, moves, and deletes hierarchical categories (e.g. Men > Clothing > T-Shirts) for a store, including image/metadata/SEO fields, via the admin dashboard (React SPA, backed by the Admin API).

**Why this priority**: Category hierarchy is the primary organizational scaffold merchants use to structure a catalog — nothing else in the feature works without it.

**Independent Test**: `POST /api/v3/admin/categories` with `name`, optional `parent_id`; `GET /api/v3/admin/categories` returns the row with computed `depth`/`children_count`/`pretty_name`; `PATCH .../:id/reposition` moves it to a new parent/index.

**Acceptance Scenarios**:

1. **Given** an admin authenticated via JWT or a secret key with category scopes, **When** they POST a category with a `parent_id` (prefixed `ctg_...`), **Then** the category is created as a child in the nested set (`awesome_nested_set`) and inherits its store from context, not a `Taxonomy`.
2. **Given** an existing category, **When** the admin calls the `reposition` action with `new_parent_id`/`new_position`, **Then** the node moves in the nested set (`move_to_child_with_index`/`move_to_root`) and `products_count` is recalculated for both the old and new ancestor chains.
3. **Given** a category with children, **When** the admin deletes it, **Then** the subtree is destroyed (`dependent: :destroy` via nested set) and ancestor `products_count`/`children_count` are recalculated before the destroy commits.

---

### User Story 2 - Merchant classifies products into categories (Priority: P1)

An admin assigns one or more categories to a product (manual classification), reorders products within a category, and views/edits a category's product list from the category detail page.

**Why this priority**: Classification is what makes the category tree useful — a category with no products has no storefront value.

**Independent Test**: `POST /api/v3/admin/categories/:id/products` (or the product-side bulk endpoint) adds a product to a category; `GET /api/v3/admin/categories/:id/products` returns it ordered by classification position; reposition endpoint reorders it.

**Acceptance Scenarios**:

1. **Given** a category and a product, **When** the admin adds the product to the category (individually or via bulk add), **Then** a `Spree::Classification` join row is created and the category's `products_count` increments.
2. **Given** several products classified under a category, **When** the admin drags a row to reorder, **Then** the classification `position` updates and product order is preserved on next fetch.
3. **Given** a classified product, **When** the admin removes it from the category, **Then** the `Classification` row is destroyed and `products_count` is recalculated.

---

### User Story 3 - Storefront customer browses/filters by category (Priority: P2)

A storefront (Store API consumer) reads the category tree and per-category product listings to build navigation and category landing pages, including SEO-relevant fields (`permalink`, `pretty_name`, meta tags, `description_html`).

**Why this priority**: Categories exist to power storefront navigation and SEO; without a read-only public surface the admin-side tree has no consumer.

**Independent Test**: `GET /api/v3/store/categories/:permalink_or_id` (publishable key) returns a category with `is_root`/`is_child`/`is_leaf`, `image_url`, and expandable `parent`/`children`/`ancestors`.

**Acceptance Scenarios**:

1. **Given** a published category, **When** a storefront requests it by permalink, **Then** the Store API resolves it via i18n-scoped `find_by!(permalink:)` with fallback to the default locale if not found in the current locale.
2. **Given** a category ID with the `ctg_` prefix, **When** a storefront requests it directly, **Then** the Store API resolves it via `find_by_prefix_id!` instead of the permalink path.
3. **Given** a category, **When** the client requests `?expand=children,ancestors,parent`, **Then** the nested serializers render without recursing into their own children/ancestors (empty expand passed down to prevent infinite recursion).

---

### User Story 4 - Admin tags arbitrary resources for freeform search (Priority: P3)

An admin attaches freeform tags/labels to products and orders (`acts_as_taggable_on`), and the admin UI offers tag autocomplete (`select_options` JSON endpoint) scoped by context and taggable type.

**Why this priority**: Tags are a lightweight, non-hierarchical complement to the category tree — used for internal search/filtering, not primary classification, hence lower priority than the tree itself.

**Independent Test**: `GET /admin/tags/select_options?q=sum&context=tags&taggable_type=Spree::Product` returns matching `ActsAsTaggableOn::Tag` rows as `{id, name}` pairs.

**Acceptance Scenarios**:

1. **Given** existing tags, **When** an admin searches with a `q` query, **Then** matching tags (case-insensitive `LIKE`) are returned, capped at 100, ordered by name.
2. **Given** a `taggable_type` param, **When** the search runs, **Then** only tags actually attached to that taggable type are returned (joined through `taggings`).
3. **Given** a product, **When** an admin assigns tags via `acts_as_taggable_on :tags, :labels`, **Then** the tag is created if new and is Ransack-queryable by `id`/`name` only (`Spree::RansackableAttributes` allowlist on the `Tag` decorator).

### Edge Cases

- What happens when a category's parent belongs to a different taxonomy/store? `parent_belongs_to_same_taxonomy` validation blocks cross-taxonomy moves; the Admin API additionally resolves `parent_id` within the current `scope`, so a parent from another store or an automatic taxon cannot be targeted.
- How does the system handle an out-of-range `reposition` index? `reposition_index` clamps the requested position into `0..siblings_count` so an out-of-range value appends to the end instead of erroring.
- What happens to `products_count` when a subtree is moved to a new parent? `recalculate_products_count_after_move` recomputes both the old and new ancestor chains after the nested-set move.
- What happens when an automatic (rule-based) taxon is queried through the Category API? The Admin/Store Category API scopes to `Spree::Category` (`default_scope { manual }`), so automatic taxons are invisible through the categories endpoints — they remain reachable only through the legacy `Spree::Taxon`/admin taxonomy UI.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support a hierarchical nested-set tree of categories (`acts_as_nested_set`, `parent_id`/`lft`/`rgt`/`depth`/`children_count`), each optionally requiring a `Spree::Taxonomy` (legacy `Taxon` rows) or none (`Spree::Category` rows, store-owned directly via `store_id`).
- **FR-002**: System MUST let an admin create/update/delete a category via the Admin API (`Spree::Api::V3::Admin::CategoriesController`), permitting only category-half attributes (`name`, `description`, `permalink`, meta fields, `hide_from_nav`, images, custom fields) — explicitly excluding collection-bound fields (`automatic`, `sort_order`, `rules_match_policy`, `taxon_rules`) and `taxonomy_id`.
- **FR-003**: System MUST support repositioning a category within the nested set via a dedicated `reposition` action (new parent and/or sibling index), recalculating `products_count` for all affected ancestors.
- **FR-004**: System MUST expose a read-only Store API surface (`Spree::Api::V3::Store::CategoriesController`) resolving categories by permalink (i18n-scoped, default-locale fallback) or prefixed ID, serving customer-facing fields only (no timestamps, no internal state).
- **FR-005**: System MUST support manual product classification (`Spree::Classification`, ordered join table) with per-category product listing, add/remove (including bulk), and reordering.
- **FR-006**: System MUST support automatic (rule-based) taxons (`automatic` flag + `Spree::TaxonRule` STI rules + `rules_match_policy` + `sort_order`) on the legacy `Spree::Taxon` model, regenerating matched products on rule change — but MUST NOT expose these fields through the Category API (they're pending migration to `Spree::Collection` in 6.0).
- **FR-007**: System MUST support freeform tagging of arbitrary resources (`Spree::Product`, `Spree::Order`) via `acts_as_taggable_on`, with a Ransack allowlist restricted to `id`/`name` on the `Tag` model, and an admin autocomplete endpoint scoped by `context` and `taggable_type`.
- **FR-008**: System MUST enforce name/permalink uniqueness scoped to `[parent_id, taxonomy_id]` for taxonomy-backed taxons, or `[parent_id, store_id]` for taxonomy-less categories — so two stores can each have a top-level category with the same name.
- **FR-009**: System MUST translate category fields (`name`, `pretty_name`, `description`, `permalink`) via `Spree::TranslatableResource`/Mobility, with `description` additionally backed by Action Text.
- **FR-010**: System MUST scope categories per store (`Spree::SingleStoreResource`), falling back from a direct `store_id` to the parent taxonomy's store for legacy rows not yet backfilled.

### Key Entities

- **Spree::Taxon**: The underlying nested-set model — hierarchical, optionally taxonomy-backed, carries both category-classification fields and automatic/collection-rule fields (`automatic`, `rules_match_policy`, `sort_order`, `taxon_rules`).
- **Spree::Category**: `Taxon` subclass, `default_scope { manual }`, `requires_taxonomy? == false` — the public-facing name used by the Admin/Store Category API and the dashboard; does not need a `Taxonomy`.
- **Spree::Taxonomy**: Legacy named container for a tree of taxons, scoped to a store (root taxon mirrors its name). Slated for removal in 6.0.
- **Spree::Classification**: Ordered join between `Product` and `Taxon`/`Category`, backing manual membership and per-category product ordering.
- **Spree::TaxonRule**: STI base for automatic-taxon membership rules (match policy + value), regenerating matched products on change.
- **ActsAsTaggableOn::Tag**: Freeform tag/label attached to `Product`/`Order` via `acts_as_taggable_on :tags, :labels`; decorated with a Ransack allowlist (`id`, `name` only).

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Taxon`, `Spree::Category` (`< Taxon` alias), `Spree::Taxonomy`, `Spree::Classification`, `Spree::TaxonRule`(+ STI subtypes), `Spree::Taxons::Find` finder, `ActsAsTaggableOn::TagDecorator` |
| `spree/api` (Store/Admin API v3) | Yes | `Store::CategoriesController`, `Admin::CategoriesController` (incl. `reposition`), `Admin::Categories::ProductsController`, `CategorySerializer`/`Admin::CategorySerializer` |
| `packages/dashboard` (admin SPA) | Yes | `routes/.../products/categories/{index,new,$categoryId}.tsx`, `hooks/use-categories.ts`, `schemas/category.ts`, `components/spree/categories/{category-form,category-tree,category-tree-utils,category-list,category-products-card,category-image-field}.tsx` |
| `packages/dashboard-ui` / `dashboard-core` | No | Category tree/table built from `packages/dashboard-ui` primitives (`Table`, `DragHandle`, `RowActions`) but no new primitives were added specifically for this feature |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated types (`Category.ts` in both SDKs) — regenerated from serializers, not hand-written |
| `docs/plans/` | Yes | `docs/plans/6.0-replace-taxons-with-categories.md` governs this area directly — see Migration Notes |

### API Contract *(include if feature touches spree/api)*

- **Existing endpoints**: `GET/POST /api/v3/admin/categories`, `GET/PATCH/DELETE /api/v3/admin/categories/:id`, `PATCH /api/v3/admin/categories/:id/reposition`, `GET/POST/DELETE /api/v3/admin/categories/:id/products` (+ product reposition); `GET /api/v3/store/categories`, `GET /api/v3/store/categories/:id_or_permalink`; legacy `GET /admin/tags/select_options` (Rails admin, non-v3).
- **Serializer fields (read, Store)**: `name`, `permalink`, `position`, `depth`, `meta_title`, `meta_description`, `meta_keywords`, `children_count`, `parent_id`, `description`, `description_html`, `image_url`, `square_image_url`, `is_root`, `is_child`, `is_leaf` — matches `permitted_params` on write for the admin-writable subset (`name`, `description`, `permalink`, meta fields, `hide_from_nav`, `image`, `square_image`, `custom_fields`), per Constitution Principle III.
- **Serializer fields (read, Admin, additive)**: `metadata`, `pretty_name`, `lft`, `rgt`, `products_count`, `created_at`, `updated_at`.
- **Auth**: Admin API — secret key (scoped) or Admin JWT + CanCanCan. Store API — publishable key, read-only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A merchant can build a multi-level category tree and reorder/reparent any node via a single `reposition` request, with `products_count` staying correct on both sides of the move.
- **SC-002**: A storefront client can resolve a category by SEO-friendly permalink or prefixed ID in one request, in the correct locale (with fallback), without leaking internal fields (timestamps, nested-set internals).
- **SC-003**: Assigning/removing products from a category is reflected in that category's `products_count` and product ordering without requiring a full tree refetch.
- **SC-004**: Automatic-taxon (collection-like) fields never leak through the Category API surface — verified by `permitted_params` explicitly excluding them.

## Assumptions

- This spec documents the system **as implemented** (post-5.5 `Spree::Category` alias); no new behavior is proposed.
- "Taxonomy" (the plan's target for removal) is still live in the current codebase and required for legacy `Spree::Taxon` rows; `Spree::Category` rows bypass it via direct `store_id`.
- Automatic/rule-based taxon behavior (`Spree::TaxonRule`, `products_matching_rules`) is included here because it lives on the same `Taxon` model today, even though the governing plan assigns it to a future `Spree::Collection` model, not Category.
- Tag/label functionality (`acts_as_taggable_on`) is included as part of this feature's "taxonomy" scope because it's a freeform classification mechanism alongside the hierarchical one, even though it's architecturally unrelated to `Taxon`/`Category`.

## Migration Notes

Gaps and inferences made while reverse-engineering this spec, flagged for follow-up rather than silently resolved:

- **`Spree::Category` is currently a subclass of `Spree::Taxon`, not a renamed/standalone model.** `class Category < Taxon` with `default_scope { manual }` and `requires_taxonomy? == false` (`spree/core/app/models/spree/category.rb`). All Category behavior (nested set, translations, metafields, validations) is inherited from `Taxon` wholesale — there is no independent `spree_categories` table yet; Category rows live in `spree_taxons` alongside legacy taxonomy-backed taxons and automatic (collection-like) taxons.
- **The Category/Collection split described in `docs/plans/6.0-replace-taxons-with-categories.md` has NOT happened yet.** Per that plan's status line: "API/serializer bridge shipped in 5.5 (`Spree::Category < Spree::Taxon` constant alias + `categories` controllers/serializers/associations); table rename + `Collection` split + rule engine pending in 6.0." Concretely still pending: renaming `spree_taxons` → `spree_categories`, dropping `Spree::Taxonomy` entirely, renaming `Spree::Classification` → `Spree::ProductCategory`, extracting `automatic`/`rules_match_policy`/`sort_order`/`TaxonRule` onto a new `Spree::Collection` model, and the `coll_` prefix / `Spree::CollectionRule` rename.
- **The Admin/Store Category API already enforces the target boundary today** even though the underlying model hasn't split: `Admin::CategoriesController#permitted_params` explicitly excludes `automatic`, `sort_order`, `rules_match_policy`, `taxon_rules`, and `taxonomy_id` — so the API surface is already Collection-clean, ahead of the model layer.
- **`Spree::Taxonomy` is still required for legacy rows.** `Taxon#store` falls back to `taxonomy&.store` when `store_id` is nil, and `validates :taxonomy, presence: true, if: :requires_taxonomy?` still applies to non-Category taxons — the plan's "drop Taxonomy entirely" step has not started.
- **Brand handling (Open Question 1 in the plan) is unresolved in code** — no `Spree::Brand` model or `kind` column was found; brands, if used, still rely on a taxonomy-name convention.
- **Legacy Rails admin (`spree/admin/app/views/spree/admin/taxons`, `taxonomies`) still exists** alongside the new dashboard SPA category pages — per CLAUDE.md, no new features should be added there, but it wasn't confirmed whether it has been fully superseded or is still reachable/used for automatic taxons (which the SPA Category API excludes).
- **Tags (`acts_as_taggable_on`) were not covered by the `6.0-replace-taxons-with-categories.md` plan at all** — included in this spec purely because it's a classification mechanism, but it has no relationship to the Taxon/Category/Collection migration; flagged here so a future reader doesn't assume otherwise.
