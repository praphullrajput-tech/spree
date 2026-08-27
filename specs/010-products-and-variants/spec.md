# Feature Specification: Products & Variants

**Feature Branch**: `010-products-and-variants`

**Created**: 2026-08-24

**Status**: migrated

**Input**: Reverse-engineered from the existing implementation (brownfield migration) — `Spree::Product`, `Spree::Variant`, `Spree::OptionType`/`Spree::OptionValue`/`Spree::ProductOptionType`, the Admin API v3 products endpoint, the legacy Rails admin products controller, and the `packages/dashboard` products SPA (list, create, edit, variants matrix, options builder).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merchant creates a simple (single-variant) product (Priority: P1)

A merchant adds a new product to the catalog with a name, description, price, and stock — no option types (size/color) required. Spree still creates an internal master `Variant` under the hood to carry SKU/price/stock, but the merchant never sees "master" in the UI; it's presented as the product itself.

**Why this priority**: The overwhelming majority of SKUs in a typical catalog are simple, non-configurable products. This is the baseline path every other story builds on.

**Independent Test**: Create a product via `POST /api/v3/admin/products` with `name`, `status`, and a `prices` array (no `variants`/`options`); verify a single purchasable variant (the master) is returned with the given price and the product is listed in the admin SPA.

**Acceptance Scenarios**:

1. **Given** a merchant on the "New Product" page, **When** they fill in name, description, and price and save, **Then** the product is created in `draft` status with one purchasable default variant.
2. **Given** a saved simple product, **When** the merchant edits price/stock, **Then** the change is written to the master variant transparently.

---

### User Story 2 - Merchant creates a configurable product with option types and variants (Priority: P1)

A merchant defines one or more option types (e.g. "Size", "Color") with option values, then generates a matrix of variants (e.g. S/Red, S/Blue, M/Red...), each with its own SKU, price, and stock levels per location.

**Why this priority**: Variant-driven catalogs (apparel, multi-SKU goods) are core to any commerce platform; without this the product model degrades to a single-SKU system.

**Independent Test**: `PATCH /api/v3/admin/products/:id` with `product_option_types` implied via variant `options: [{name, value}]` entries; verify each variant is created with its own `option_values`, `prices`, and `stock_items`, and that `product.variant_count` reflects the non-master variant count.

**Acceptance Scenarios**:

1. **Given** a product with no option types, **When** the merchant adds "Size" (S, M, L) and "Color" (Red, Blue) via the options builder, **Then** the variants matrix offers to generate up to 6 variant combinations.
2. **Given** an existing variant matrix, **When** the merchant edits one variant's SKU/price/stock via the variant edit sheet, **Then** only that variant is updated (siblings and the product are untouched).
3. **Given** a full variants payload sent to `PATCH /api/v3/admin/products/:id`, **When** a previously-existing variant is omitted from the payload, **Then** that variant is destroyed (payload is a full replace when any non-master variant ID is present).

---

### User Story 3 - Merchant manages product lifecycle status (draft / active / archived) (Priority: P2)

A merchant moves a product through `draft → active` (publish) and `active/draft → archived` (discontinue), gated by CanCanCan `:activate` permission separate from general `:update`.

**Why this priority**: Controls what is visible on the storefront/API without deleting data; required before any product is customer-visible.

**Independent Test**: `POST /api/v3/admin/products/bulk_status_update` with `{ids: [...], status: 'active'}`; verify only accessible products transition and the search index is re-enqueued.

**Acceptance Scenarios**:

1. **Given** a `draft` product, **When** an admin without `:activate` permission attempts to set `status: active`, **Then** the status change is silently skipped (existing status preserved) while other attribute changes still save.
2. **Given** an `active` product, **When** it is archived, **Then** it drops out of `Product.available`/`.active` storefront scopes immediately.

---

### User Story 4 - Storefront customer browses and filters products/variants (Priority: P2)

A customer (or storefront app) lists/searches products via the Store API, filters by category/option value/price/stock, and reads back computed fields (`purchasable`, `in_stock`, `price` with price-list resolution, `preorder`).

**Why this priority**: This is the read surface every storefront integration depends on; it must stay stable and fast.

**Independent Test**: `GET /api/v3/store/products?q[search]=...` with a publishable key; verify only `active`, non-discontinued, currently-published (per channel) products with a price in the requested currency are returned, each variant option-value-filterable via `with_option_value_ids`.

**Acceptance Scenarios**:

1. **Given** a product published to Channel A but not Channel B, **When** a request scoped to Channel B is made, **Then** the product is excluded from results (unless it has an active pre-order variant and `include_preorderable` applies).
2. **Given** a `price_lte`/`price_gte` Ransack filter, **When** applied to the collection, **Then** results are limited to products whose variant prices in the requested currency satisfy the bound.

---

### Edge Cases

- What happens when a product's master variant fails validation (e.g. duplicate SKU)? → Product save is blocked; master's errors are copied onto the product record (`validate_master`).
- How does the system handle deleting a product referenced by a completed order? → `ensure_not_in_complete_orders` aborts the destroy with `errors.add(:base, :cannot_destroy_if_attached_to_line_items)`.
- What happens when a variant's option values reference a deleted/removed option type? → `variants_and_option_values` scope excludes variants without at least one live option value join, hiding "orphaned" variants from storefront display.
- What happens when all variants for a product are soft-deleted but the master is untouched? → Product remains available via master (simple-product fallback), governed by `has_variants?` counter cache.
- What happens on `products=` bulk sync when an entry has no `options` and no matching `id`? → It targets the master variant (upsert), never creates a duplicate "no-option" variant.
- How are cross-currency prices handled when a variant lacks a price row for the requested currency? → `price_in` returns an unsaved `Spree::Price.new` stub (amount `nil`), which downstream `purchasable?`/`available` scopes treat as unpriced/excluded.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST auto-provision one master `Variant` per `Product` on creation (`after_initialize :ensure_master`), carrying SKU/price/weight/dimensions for simple products.
- **FR-002**: System MUST support many non-master `Variant`s per product, each tied to a unique combination of `OptionValue`s through `OptionValueVariant`, validated via `validates :option_value_variants, presence: true, unless: :is_master?`.
- **FR-003**: System MUST let a product declare its option types via `ProductOptionType` (ordered join, `acts_as_list scope: :product`) independent of which values a given variant uses.
- **FR-004**: System MUST expose a `status` state machine (`draft → active`, `active/draft → archived`) with dedicated events (`activate`, `archive`, `draft`) each firing lifecycle webhooks/events.
- **FR-005**: System MUST scope product availability by store, channel publication (`Spree::ProductPublication`), discontinue date, and priced-currency via `Product.available`/`.active`.
- **FR-006**: System MUST compute `purchasable?`/`in_stock?`/`backorderable?`/`preorder?` at both Product (aggregating across variants) and Variant (own stock/backorder/preorder state) levels.
- **FR-007**: System MUST support inline bulk sync of variants (`Product#variants=`), prices (`Variant#prices=`), stock items (`Variant#stock_items=`), and media (`Product#media=`/`Variant` gallery) from a single nested API payload, with add/update/remove-by-omission semantics.
- **FR-008**: System MUST enforce read/write field symmetry on the Admin API v3 products endpoint — `permitted_params` accepts exactly the attributes the admin serializer will later expose (name, description, slug, status, tax_category_id, category_ids, custom_fields, media, product_publications, nested variants incl. prices/stock/options).
- **FR-009**: System MUST support bulk operations scoped by CanCanCan ability: `bulk_status_update`, `bulk_add/remove_to_categories`, `bulk_add/remove_to_channels`, `bulk_destroy`, each re-enqueuing the search index since `update_all`/`touch_all` skip `after_commit`.
- **FR-010**: System MUST support product duplication (`Products::Duplicator` via `Product#duplicate`) exposed as `POST /api/v3/admin/products/:id/clone` (Admin API) and `POST /clone` (legacy admin).
- **FR-011**: System MUST prevent destroying a `Product`/`Variant` that has line items on a completed order (`ensure_not_in_complete_orders`).
- **FR-012**: System MUST let `OptionType` declare a `kind` (`dropdown`/`color_swatch`/`buttons`) governing SPA rendering, and let `OptionValue` carry an optional `color_code` (hex) for swatch rendering.
- **FR-013**: Admin SPA MUST let a merchant build the option-type/option-value matrix, generate a variant grid from the cartesian product of selected values, and edit per-variant SKU/price/stock/media via a dedicated sheet (`variant-edit-sheet.tsx`), all driven by `useProduct`/`useUpdateProduct` hooks — never calling `adminClient` directly from components.
- **FR-014**: Store API MUST return prefixed IDs (`prod_...`, `variant_...`, `optval_...`, `opt_...`) for every resource and accept the same on write.
- **FR-015**: System MUST support product-scoped and variant-scoped custom fields (`Spree::Metafields`) and free-form `metadata` (`Spree::Metadata`).

### Key Entities

- **Product**: Catalog grouping entity — name, description (rich text), slug, status, SEO meta fields, tax/shipping category, store ownership, media gallery, channel publications, taxon/category classifications, tags. Always has exactly one master `Variant` (soft-deletable) and zero-or-more non-master `Variant`s.
- **Variant**: Purchasable unit — SKU, dimensions/weight, cost price, per-currency `Price` rows, `StockItem`s per location, option-value combination (empty for master), track-inventory flag, preorder/backorder settings, tax category override.
- **OptionType**: Named axis of variation (e.g. "Size"), with an ordered set of `OptionValue`s, a `kind` (dropdown/color_swatch/buttons), and `filterable` flag for storefront faceting.
- **OptionValue**: A single value on an axis (e.g. "Large"), with presentation text, optional `color_code`, ordered within its `OptionType` (`acts_as_list scope: :option_type`).
- **ProductOptionType**: Ordered join between `Product` and `OptionType`, defining which axes a given product varies on and in what display order.
- **Price**: Per-variant, per-currency amount + `compare_at_amount`, optionally scoped to a `PriceList` (see EU Omnibus `prior_price`).

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Product`, `Spree::Variant`, `Spree::OptionType`, `Spree::OptionValue`, `Spree::ProductOptionType`, `Spree::ProductScopes`, `Spree::DefaultPrice`, `Spree::Products::Find` finder, `Spree::Products::Duplicator`/`PrepareNestedAttributes` services |
| `spree/api` (Store/Admin API v3) | Yes | `Admin::ProductsController` (CRUD + clone + bulk ops), `Store::ProductsController` (read-only, scoped by availability/channel), `ProductSerializer`/`VariantSerializer`/`OptionTypeSerializer`/`OptionValueSerializer` (Store + Admin) |
| `spree/admin` (legacy Rails admin) | Yes (legacy, not extended) | `Spree::Admin::ProductsController` — still the live UI for some flows during SPA migration; no new work planned here per Module Boundaries principle |
| `packages/dashboard` (admin SPA) | Yes | Routes: `products/index.tsx`, `new.tsx`, `$productId.tsx`, `options.tsx`; components: `product-form-cards.tsx`, `variants-section.tsx`, `variants-options-builder.tsx`, `variant-edit-sheet.tsx`, `publishing-card.tsx`, `inventory-section.tsx`, `variants-matrix.ts`; hooks: `use-products.ts`, `use-product.ts`, `use-product-media.ts` |
| `packages/dashboard-ui` / `dashboard-core` | No | Uses existing generic primitives/registries; no new shared components identified |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated types (`Product`, `Variant`, `OptionType`, `OptionValue`) consumed by dashboard/admin-sdk; regenerated from serializers, not hand-written |
| `docs/plans/` | Yes | Governed by `docs/plans/6.0-remove-master-variant.md` (master-variant elimination) and `docs/plans/6.0-product-types.md` (Prototype → ProductType rename) — both pending, see Migration Notes below |

### API Contract *(include if feature touches spree/api)*

- **Admin endpoints**: `GET/POST /api/v3/admin/products`, `GET/PATCH/DELETE /api/v3/admin/products/:id`, `POST /api/v3/admin/products/:id/clone`, `POST /api/v3/admin/products/bulk_status_update`, `POST /api/v3/admin/products/bulk_add_to_categories`, `POST /api/v3/admin/products/bulk_remove_from_categories`, `POST /api/v3/admin/products/bulk_add_to_channels`, `POST /api/v3/admin/products/bulk_remove_from_channels`, `DELETE /api/v3/admin/products/bulk_destroy`
- **Store endpoints**: `GET /api/v3/store/products`, `GET /api/v3/store/products/:id_or_slug` (read-only)
- **Serializer fields (read, Store)**: `name`, `slug`, `description`/`description_html`, `meta_title`/`meta_description`/`meta_keywords`, `variant_count`, `default_variant_id`, `thumbnail_url`, `available_on`, `preorder_ships_at`, `purchasable`, `in_stock`, `backorderable`, `available`, `preorder`, `price`, `original_price`, `tags`, plus expandable `variants`, `option_types`, `option_values`, `categories`, `custom_fields`, `prior_price`
- **Serializer fields (read, Admin — extends Store)**: adds `status`, `cost_price`/margins on variants, timestamps, `product_publications`, internal media/stock detail
- **Write parity**: Admin `permitted_params` accepts `name, description, slug, status, meta_title, meta_description, meta_keywords, tax_category_id, promotionable, digital, tags[], category_ids[], metadata{}, prices[], custom_fields[], media[], product_publications[], variants[]` — matching what the admin serializer/read surface exposes (per Constitution Principle III; category_ids bridges to `taxon_ids`, custom_fields bridges Metafield definitions)
- **Auth**: Store API — publishable key, read-only. Admin API — secret key + scopes (`read_products`/`write_products`) or JWT + CanCanCan (`:manage`/`:activate`/`:destroy` on `Spree::Product`)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A merchant can create a simple product (name + price + stock) and see it purchasable on the storefront within one save action (no separate "add variant" step required).
- **SC-002**: A merchant can generate a full variant matrix (up to double-digit combinations) from 2 option types in a single "Generate variants" action, with each variant individually editable afterward.
- **SC-003**: Product list/search/filter (by category, option value, price range, stock, tags) returns correct, store-scoped results via both the legacy admin Ransack UI and the Admin API v3 Ransack-compatible filters.
- **SC-004**: Bulk status/category/channel operations on 100+ selected products complete in a single request and leave the search index consistent (no stale entries).
- **SC-005**: No Store API response ever exposes a raw (non-prefixed) database ID for Product/Variant/OptionType/OptionValue.

## Assumptions

- The master-variant abstraction (`is_master: true` row per product) is treated as an internal implementation detail throughout this spec, consistent with current behavior — it is scheduled for removal per `docs/plans/6.0-remove-master-variant.md`, at which point "simple product" attributes (SKU/price/stock) move to a `default_variant_id` FK directly on `Product`.
- `Spree::Config.enable_legacy_default_price` toggles a deprecated single-currency `price`/`default_price` shim on top of the multi-currency `Price` model; new work should target `Variant#price_in`/`#set_price` directly, not the legacy shim.
- The legacy Rails admin (`spree/admin`) products controller remains the system of record for some workflows (e.g. Turbo-based inline variant editing) during the SPA migration; this spec does not propose extending it further, per the Module Boundaries principle.
- Prototypes (`Spree::Prototype`) are used only at product-creation time to seed `option_types`/`taxons`; the model itself is out of scope here and is superseded by `docs/plans/6.0-product-types.md`.

## Migration Notes

- **`docs/plans/6.0-remove-master-variant.md`** (pending, 6.0 target): Eliminates `is_master` and adds a `default_variant_id` FK directly on `Product`. This spec's FR-001 ("auto-provision a master Variant"), the `Product#sync_variant_state!` comment noting "changes shape once master is removed," and the whole `find_or_build_master`/`variants_including_master` surface area are all constrained by this plan — any new feature work here should avoid deepening reliance on `is_master` semantics where a `default_variant`-based abstraction would do.
- **`docs/plans/6.0-product-types.md`** (pending, 6.0 target): Renames `Prototype` → `ProductType` and adds `MetafieldDefinition` schema enforcement. `Product#prototype_id`/`add_associations_from_prototype` (used only on create, to seed option types/taxons) is the integration point that will need to move to the new model.
- **Known gaps not covered by current code** (surfaced during this reverse-engineering pass, not implemented):
  - No explicit "duplicate SKU across stores" guard beyond the existing `spree_base_uniqueness_scope`-scoped validation — cross-store SKU collisions are prevented by store scoping already, but this was not independently re-verified against multi-store test coverage.
  - `Spree::Products::Find` (Store API v2/legacy finder) and the v3 `Admin::ProductsController#collection` (SearchProvider-based) implement filtering via two different code paths; this spec describes both but does not attempt to unify them — that would be a separate architectural change requiring its own `docs/plans/` entry.
  - Option-type/option-value translation (`translatable_children :option_values`) exists on the model but this spec does not enumerate the translations API surface — see `5.5-6.0-resource-translations-api.md` for that cross-cutting work.
