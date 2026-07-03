# Feature Specification: Products & Variants

**Feature Branch**: `main` (fully shipped; 6.0 remove-master-variant pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `6.0-remove-master-variant.md`, `6.0-product-types.md`, `6.0-channels-catalogs-b2b.md`

---

## User Scenarios & Testing

### User Story 1 — Manage Products (Priority: P1)

A merchant admin creates, edits, publishes, and archives products. Each product has a name, description, status (draft/active/archived), slug, SEO metadata, pricing, and is associated with one or more categories and channels.

**Why this priority**: The product catalog is the foundation of commerce; without product management, no selling is possible.

**Independent Test**: Admin creates a product with `name: "Blue T-Shirt"`, `status: active`. Product appears in the list with `id: "prod_…"` and is purchasable at checkout.

**Acceptance Scenarios**:

1. **Given** no products, **When** admin creates an active product with a price, **Then** it appears with `prod_…` ID and is purchasable
2. **Given** a draft product, **When** admin sets `status: active`, **Then** it becomes visible on the storefront
3. **Given** an active product, **When** admin archives it, **Then** it is excluded from storefront listing
4. **Given** a product, **When** soft-deleted, **Then** excluded from default scope; `deleted_at` is set
5. **Given** a product, **When** cloned, **Then** a new draft product is created with `(copy)` suffix

---

### User Story 2 — Manage Variants (Priority: P1)

Admin adds variants to a product (e.g., size + color combinations), each with its own SKU, price, stock, and images. The product has a `default_variant_id` pointing to the primary purchasable variant.

**Why this priority**: Most products come in multiple variations; without variants, merchants cannot offer size/color selection.

**Acceptance Scenarios**:

1. **Given** a product with option types (Size, Color), **When** admin generates variants, **Then** each combination gets a variant with `variant_…` ID
2. **Given** a variant with `price: 29.99`, **When** listed on the storefront, **Then** that price is shown
3. **Given** a default variant, **When** viewing the product, **Then** `default_variant_id` resolves to that variant
4. **Given** a variant, **When** stock is 0 and not backorderable, **Then** `purchasable: false`

---

### User Story 3 — Bulk Operations (Priority: P2)

Admin selects multiple products and performs bulk status updates, category assignments, or channel assignments.

**Acceptance Scenarios**:

1. **Given** selected products, **When** bulk-set to `active`, **Then** all selected products become active
2. **Given** selected products, **When** bulk-added to "Sale" category, **Then** all appear in that category
3. **Given** selected products, **When** bulk-added to "Wholesale" channel, **Then** all are published to that channel

---

### Edge Cases

- What if a product has no active variants? → `purchasable: false`; product detail page shows "out of stock"
- What if slug conflicts with another product? → validated unique per store; 422 on conflict
- _(6.0)_ `is_master` boolean on variants will be eliminated; `default_variant_id` FK on Product becomes the single source of truth per `6.0-remove-master-variant.md`

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::Product` prefix `prod_`; status: `draft`, `active`, `archived` (string column, not enum)
- **FR-002**: `acts_as_paranoid` — soft delete; `deleted_at` column
- **FR-003**: `Spree::Variant` prefix `variant_`; belongs_to product; SKU, price, cost_price, weight, dimensions
- **FR-004**: `default_variant_id` FK on Product points to the primary purchasable variant
- **FR-005**: `is_master` boolean on Variant (legacy); deprecated in 6.0 per `6.0-remove-master-variant.md`
- **FR-006**: Concerns: `TranslatableResource`, `MemoizedData`, `Metafields`, `Metadata`, `Webhooks`, `Slugs`, `Channels`, `SearchIndexable`
- **FR-007**: Admin API: full CRUD + bulk actions (`status_update`, `add_to_categories`, `remove_from_categories`, `add_to_channels`, `remove_from_channels`, `clone`)
- **FR-008**: Variants managed via nested routes under products
- **FR-009**: `in_stock`, `purchasable`, `on_sale` as computed boolean attributes
- **FR-010**: `total_on_hand` computed from stock items across all stock locations

### Key Entities

- **Product** (`Spree::Product`): name, description, slug, status, available_on, discontinue_on, meta_title, meta_description, tax_category_id, default_variant_id. Prefix: `prod_`.
- **Variant** (`Spree::Variant`): SKU, price, cost_price, weight, depth, height, width, is_master (legacy), position. Prefix: `variant_`.

---

## Backend Requirements

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/products` | List products (Ransack, paginated) |
| POST | `/api/v3/admin/products` | Create product |
| GET | `/api/v3/admin/products/:id` | Show product |
| PATCH | `/api/v3/admin/products/:id` | Update product |
| DELETE | `/api/v3/admin/products/:id` | Soft-delete product |
| POST | `/api/v3/admin/products/:id/clone` | Clone product |
| POST | `/api/v3/admin/products/bulk_status_update` | Bulk status update |
| GET | `/api/v3/admin/products/:id/variants` | List variants |
| POST | `/api/v3/admin/products/:id/variants` | Create variant |
| PATCH | `/api/v3/admin/variants/:id` | Update variant |
| DELETE | `/api/v3/admin/variants/:id` | Soft-delete variant |

### Serializer Fields

**Admin ProductSerializer** (extends Store ProductSerializer):
- `id` (prod_…), `name`, `description`, `slug`, `status`, `available_on`, `discontinue_on`, `tax_category_id`, `default_variant_id` (variant_…), `in_stock`, `purchasable`, `total_on_hand`, `meta_title`, `meta_description`, `metadata`, `private_metadata`, `created_at`, `updated_at`, `deleted_at`

**Admin VariantSerializer** (extends Store VariantSerializer):
- `id` (variant_…), `product_id` (prod_…), `sku`, `price`, `cost_price`, `weight`, `depth`, `height`, `width`, `in_stock`, `purchasable`, `on_sale`, `is_master`, `position`, `metadata`, `created_at`, `updated_at`, `deleted_at`

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/products/index.tsx` — list with bulk ops, export, filter by status/category/channel
- `packages/dashboard/src/routes/_authenticated/$storeId/products/$productId.tsx` — detail with variants, media, pricing, inventory, SEO, categories, channels, metafields

### Hooks

- `packages/dashboard/src/hooks/use-products.ts` — TanStack Query with pagination, sorting, Ransack search

---

## Success Criteria

- **SC-001**: Admin can create and publish a product; it appears at checkout
- **SC-002**: Variants with different prices/stock display correctly on the storefront
- **SC-003**: Bulk status update applies to all selected products atomically
- **SC-004**: Soft-deleted products are excluded from storefront; admin list shows them with a filter
- **SC-005**: _(6.0)_ `is_master` eliminated; `default_variant_id` is the sole source of truth

---

## Assumptions

- Price is stored on Variant, not Product; the product's "price" is the default variant's price
- `SearchIndexable` concern syncs to Meilisearch when configured; falls back to DB search
- Product status transitions are not a state machine — they are a plain string assignment with no enforced guards
