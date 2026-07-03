# Feature Specification: Categories (Taxon Hierarchy)

**Feature Branch**: `main` (5.5 bridge shipped; 6.0 rename pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: `docs/plans/6.0-replace-taxons-with-categories.md`

---

## User Scenarios & Testing

### User Story 1 — Manage Category Hierarchy (Priority: P1)

An admin operator builds and maintains a product category tree for their store. They create root categories ("Men", "Women", "Accessories"), nest subcategories underneath ("Men > Clothing > T-Shirts"), reorder them by dragging, and delete unused branches.

**Why this priority**: Categories are the primary product classification structure. Every product is organized through them, and the store navigation depends on them.

**Independent Test**: Admin navigates to Products → Categories, creates a root category "Men", adds a child "Clothing" under it, then adds "T-Shirts" under "Clothing". The breadcrumb shows `Men > Clothing > T-Shirts`. Admin then deletes "T-Shirts" and the tree reflects the removal.

**Acceptance Scenarios**:

1. **Given** no categories exist, **When** admin creates a root category with `name: "Men"`, **Then** it appears in the tree as a root node with `is_root: true` and a prefixed ID (`ctg_…`)
2. **Given** a root category exists, **When** admin creates a child category under it, **Then** the child's `parent_id` is set and `depth` increments correctly
3. **Given** a nested category, **When** admin edits its `permalink`, **Then** ancestors' permalinks are not affected; only the node's own permalink updates
4. **Given** a category with products, **When** admin deletes it, **Then** the products lose that category association but are not deleted
5. **Given** a 422 response from the API, **When** `name` is blank, **Then** a field-level error appears inline on the name input

---

### User Story 2 — Manage Category Presentation (Priority: P2)

An admin operator sets SEO metadata, hero image, square image, and description on each category so the storefront can render category landing pages with proper content.

**Why this priority**: Builds on US1. Category content (image, description, SEO) is essential for marketable category pages.

**Independent Test**: Admin edits the "Men" category, uploads a hero image, sets `meta_title` and `meta_description`, and saves. The admin API response includes `image_url` and `meta_title`.

**Acceptance Scenarios**:

1. **Given** a category, **When** admin uploads a hero image, **Then** `image_url` appears in the API response via Active Storage
2. **Given** a category, **When** admin sets `meta_title` and `meta_description`, **Then** they are returned in the admin serializer response
3. **Given** a category with `hide_from_nav: true`, **When** the store API returns the category, **Then** `hide_from_nav` is included in the response for navigation rendering decisions

---

### User Story 3 — Reposition Category in Tree (Priority: P2)

An admin operator moves a category to a new parent or reorders it among its siblings using a drag-and-drop interface. The nested set (`lft`, `rgt`, `depth`) updates automatically.

**Why this priority**: Merchants regularly reorganise their catalogue hierarchy; manual position editing is impractical on nested sets.

**Independent Test**: Admin drags "T-Shirts" from `Men > Clothing` to `Women > Clothing`. The API's `reposition` action updates `parent_id`, and the GET response shows the new ancestor chain.

**Acceptance Scenarios**:

1. **Given** a category at depth 2, **When** admin calls `reposition` with a new `parent_id`, **Then** `lft`/`rgt`/`depth` recalculate and the new parent's `children_count` increments
2. **Given** a reposition that would create a cycle (moving a parent into its own child), **When** the API is called, **Then** a 422 is returned with a validation error
3. **Given** siblings under the same parent, **When** admin reorders them, **Then** positions update and the order persists after page reload

---

### Edge Cases

- What if a category's `name` is duplicate under the same parent? → Uniqueness validated on `[parent_id, store_id, name]` (case-insensitive)
- What if a store has no categories? → Empty state shown; create-first prompt visible
- What if the `permalink` conflicts with an existing category? → Uniqueness validated per store
- What if category deletion cascades to subcategories? → `dependent: :destroy` cascades the tree branch (via `acts_as_nested_set`)
- What if a child category is moved to a new store? → Not supported — all categories in a tree share the same `store_id`

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::Category` must be a subclass (currently alias) of `Spree::Taxon`; prefixed ID `ctg_`
- **FR-002**: Category tree must use `awesome_nested_set` (`lft`, `rgt`, `depth`, `parent_id`, `children_count`)
- **FR-003**: Categories are store-scoped — every category has `store_id`; children copy store from parent on creation
- **FR-004**: Admin API must expose a `reposition` action for moving categories within the tree
- **FR-005**: Store API must expose `parent_id`, `children_count`, `is_root`, `is_child`, `is_leaf` on category responses
- **FR-006**: Category serializers must support expandable `children`, `parent`, `ancestors` associations
- **FR-007**: Categories support `has_one_attached :image` and `:square_image`
- **FR-008**: Categories support `custom_fields` via `Spree::Metafields` concern (expand param)
- **FR-009**: Categories are translatable (`name`, `pretty_name`, `description`, `permalink` via Mobility)
- **FR-010**: Admin can set `hide_from_nav` on any category
- **FR-011**: All IDs in API responses must be prefixed (`ctg_…`); parent IDs use `prefixed_id`
- **FR-012**: `Spree::Taxonomy` provides backward-compatible category grouping until 6.0 table rename
- **FR-013**: _(6.0 pending)_ `Spree::Collection` model — flat, store-scoped, manual + automatic rule-based product groupings
- **FR-014**: _(6.0 pending)_ Table rename `spree_taxons` → `spree_categories`; `Spree::Classification` → `Spree::ProductCategory`

### Key Entities

- **Category** (`Spree::Category < Spree::Taxon`): Node in the product hierarchy. Attributes: `name`, `permalink`, `description`, `meta_title`, `meta_description`, `meta_keywords`, `position`, `hide_from_nav`, `lft`, `rgt`, `depth`, `children_count`, `store_id`, `parent_id`. Has `image` + `square_image` attachments. Has many `products` through `classifications`.
- **Taxonomy** (`Spree::Taxonomy`): Named container for a category tree, scoped to a store. `has_one :root` taxon. Deprecated in 6.0 — categories will be directly store-scoped.
- **_(6.0)_ Collection** (`Spree::Collection`): Flat, curated or rule-based product grouping. Owns `automatic`, `sort_order`, `rules_match_policy`, `collection_rules`.

---

## Backend Requirements

### Data Model

- **Model**: `Spree::Category < Spree::Taxon` (alias in 5.5; full rename in 6.0); table `spree_taxons` (renamed `spree_categories` in 6.0)
- **Nested set**: `acts_as_nested_set`, columns: `lft`, `rgt`, `depth`, `parent_id`, `children_count`
- **Attachments**: `has_one_attached :image`, `has_one_attached :square_image`
- **Soft delete**: Not applicable — hard delete cascades the tree branch

### API Surface

#### Store API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/categories` | List categories (supports `expand[]=children,parent,ancestors`) |
| GET | `/api/v3/categories/:id` | Show category |

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/categories` | List categories |
| GET | `/api/v3/admin/categories/:id` | Show category |
| POST | `/api/v3/admin/categories` | Create category |
| PATCH | `/api/v3/admin/categories/:id` | Update category |
| DELETE | `/api/v3/admin/categories/:id` | Delete category (cascades subtree) |
| PATCH | `/api/v3/admin/categories/:id/reposition` | Move in tree (new `parent_id`) |

### Serializer Fields

**Store serializer** (`Spree::Api::V3::CategorySerializer`):
- `id`, `name`, `permalink`, `description`, `meta_title`, `meta_description`, `hide_from_nav`
- `parent_id`: prefixed string | null
- `is_root`, `is_child`, `is_leaf`: boolean
- `children_count`, `position`: number
- `image_url`, `square_image_url`: string | null
- `custom_fields`: expandable array

**Admin serializer** (`Spree::Api::V3::Admin::CategorySerializer`, extends Store):
- `meta_keywords`, `products_count`
- `lft`, `rgt`, `depth`: number (nested set internals)
- `private_metadata`, `public_metadata`
- `created_at`, `updated_at`
- `children`: expandable (admin serializer)
- `ancestors`: expandable

### Authorization

- CanCanCan: `can :manage, Spree::Taxon` for admin (covers `Spree::Category` via alias)
- Ransack allowlist: `name`, `permalink`, `store_id`, `parent_id`

### i18n (Rails)

- Keys in `spree/core/config/locales/en.yml` under `spree.taxon.*` (to become `spree.category.*` in 6.0)

---

## Frontend Requirements

### SPA Routes

- `products/categories/index.tsx` — tree list
- `products/categories/new.tsx` — create form
- `products/categories/$categoryId.tsx` — edit form

### Resource Hook

- `packages/dashboard/src/hooks/use-categories.ts`

### Components

- `packages/dashboard/src/components/spree/categories/` — category-specific UI components (image picker, breadcrumb, tree display)

### i18n Keys

New keys under `admin.categories.*` in all 6 locale files: page title, breadcrumb, column headers, form labels, empty state, toast messages, delete confirm, tree node labels.

### Date/time fields

`available_on` on Category if present — use `<StoreDatePicker>`.

---

## Success Criteria

- **SC-001**: Admin can create a 3-level deep category tree (root → child → grandchild) in a single session
- **SC-002**: `GET /api/v3/admin/categories` returns paginated list with prefixed IDs (`ctg_…`) and expandable `children`/`ancestors`
- **SC-003**: `PATCH /api/v3/admin/categories/:id/reposition` correctly moves a category to a new parent and updates nested set coordinates
- **SC-004**: Store API `GET /api/v3/categories` includes `is_root`, `is_leaf`, `children_count` on each category
- **SC-005**: Category deletion cascades the entire subtree; products lose the category association but are not deleted
- **SC-006**: _(6.0)_ `Spree::Collection` model exists with automatic rule-based product membership

---

## Assumptions

- In 5.5, `Spree::Category` is a constant alias of `Spree::Taxon` — the underlying table is still `spree_taxons`
- `Spree::Taxonomy` is still required as the tree container in 5.5; it is deprecated and removed in 6.0
- Automatic/rule-based category features (currently on Taxon's `automatic` flag + `TaxonRule`) will migrate to `Spree::Collection` in 6.0 — not in scope for this migration
- The `pretty_name` hierarchical breadcrumb string is computed from the nested set ancestors and is not a stored column
