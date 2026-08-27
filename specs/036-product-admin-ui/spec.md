# Feature Specification: Product Admin UI (Dashboard SPA)

**Feature Branch**: `036-product-admin-ui`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from the existing implementation (brownfield migration) — no original user description. Source: `packages/dashboard/src/routes/_authenticated/$storeId/products/$productId.tsx`, `packages/dashboard/src/components/spree/products/{product-form-cards,publishing-card,media-edit-sheet,inventory-section,variants-section,variants-options-builder,variant-edit-sheet,variant-media-picker}.tsx`, `packages/dashboard/src/hooks/{use-product,use-product-media,use-products,use-categories,use-channels}.ts`, `packages/dashboard/src/schemas/product.ts`, `packages/dashboard/e2e/products-*.spec.ts`. This feature covers the SPA editing surface only — the underlying `Spree::Product`/`Spree::Variant` models and Admin API v3 endpoints are covered by `010-products-and-variants`; category hierarchy/classification by `012-categories-and-taxonomy`; bulk multi-row editing by `034-bulk-editing-ui`; the underlying data-grid primitive by `035-data-grid-component`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merchant edits core product details (Priority: P1)

A store admin opens a product's detail page in the dashboard SPA and edits name, description, status, tax category, and SEO fields, then saves.

**Why this priority**: The single-product detail page is the primary surface merchants use day to day; every other card on the page depends on this base form being wired up.

**Independent Test**: Navigate to `/$storeId/products/$productId`, edit the Name field and Status select, click Save, and verify a success toast plus the persisted value surviving a refetch.

**Acceptance Scenarios**:

1. **Given** a product edit page has loaded, **When** the admin changes the name and clicks Save, **Then** `useUpdateProduct` PATCHes `/api/v3/admin/products/:id`, the form re-baselines (`isDirty` clears) without waiting for the refetch, and a success toast appears.
2. **Given** the admin has unsaved edits, **When** an unrelated background refetch lands (e.g. window refocus), **Then** the form does NOT reset and lose the merchant's in-progress edits (`form.formState.isDirty` guard in the reset `useEffect`).
3. **Given** a 422 validation error on save, **When** the response returns field-level errors, **Then** `mapSpreeErrorsToForm` routes them onto the matching RHF fields (or `errors.root` for base/nested keys) instead of a generic toast.

---

### User Story 2 - Merchant manages product media with drag-and-drop reorder (Priority: P1)

A store admin uploads images to a product, edits per-image alt text and per-variant assignment, and reorders the gallery by dragging thumbnails.

**Why this priority**: Product imagery is core merchandising; the gallery order is customer-visible on the storefront, so the editing UX must be precise.

**Independent Test**: Open a product with existing media, drag a thumbnail to a new position, and verify the array's `position` values renumber sequentially (1-indexed) and persist on save.

**Acceptance Scenarios**:

1. **Given** the Media card renders existing assets, **When** the admin drags a thumbnail to a new slot, **Then** `MediaCard`'s `DndContext`/`SortableContext` (dnd-kit, `rectSortingStrategy`) reorders the local array and rewrites every item's `position` to `index + 1` — this follows the same `acts_as_list`-backed drag-and-drop pattern mandated for other reorderable collections (constitution / CLAUDE.md "Forms" section), even though `Spree::Product` media itself is `Spree::Asset` with an `acts_as_list` `position` column rather than a UI-only computed field.
2. **Given** an admin opens the per-image edit sheet (`MediaEditSheet`), **When** they change alt text or toggle which variants the image applies to, **Then** the changes stage into `form.media[i]` and ship on the product PATCH — new uploads carry a `signed_id`/`uploadId`, persisted ones carry an `id` and no `signed_id` (to avoid re-creating an `Asset` on a second save before refetch).
3. **Given** an admin deletes a media item, **When** they confirm, **Then** `useDeleteProductMedia` calls the dedicated `DELETE` media endpoint immediately (not deferred to product PATCH) and the remaining items renumber `position`.

---

### User Story 3 - Merchant controls channel publishing and scheduling (Priority: P2)

A store admin assigns a product to one or more sales channels and schedules when it becomes visible/hidden per channel.

**Why this priority**: Multi-channel publishing (see `019-channels-and-order-routing`, `docs/plans/6.0-channels-catalogs-b2b.md`) is required before a product is purchasable anywhere; without it a product exists but is invisible everywhere.

**Independent Test**: Open the Publishing card, click "Manage", toggle a channel on, set a future `published_at`, save, and verify the row shows "Scheduled" with the correct caption; verify a product with `status: draft` shows "Not available" regardless of publication dates.

**Acceptance Scenarios**:

1. **Given** the Publishing card, **When** the admin opens `ManageChannelsSheet` and checks/unchecks a channel, **Then** `product_publications` (a `useFieldArray`) gains/loses an entry with `channel_id`, `published_at: null`, `unpublished_at: null`.
2. **Given** a publication row, **When** the admin clicks it, **Then** `PublicationEditor` opens inline with `StoreDatePicker` (`includeTime`, `inline` — required inside the enclosing `Sheet`, see CLAUDE.md Popover-in-Sheet caveat) for `published_at`/`unpublished_at`.
3. **Given** `scheduleStatus()`, **When** product `status !== 'active'`, **Then** the computed status is `not_available` regardless of the publication window (product status is the outer gate); otherwise the status is derived from now vs. `published_at`/`unpublished_at` (`live` / `scheduled` / `hidden`).
4. **Given** the New Product page (`seedDefaultChannel=true`), **When** channels resolve and the array is still empty, **Then** the store's default active channel is seeded via `form.reset(..., { keepDirtyValues: true })` against merged defaults — never via `append`, which would spuriously flip `isDirty`.

---

### User Story 4 - Merchant assigns categories, tags, and variants (Priority: P2)

A store admin classifies a product into one or more categories, applies free-text tags, and — for configurable products — builds an option-type matrix of variants.

**Why this priority**: Categorization drives storefront navigation and search facets; the variants matrix is required for any product with size/color-style options.

**Independent Test**: Add two categories via the multi-autocomplete, add a tag, save, and verify both persist; separately, add an option type with two values and verify the variants matrix generates the cartesian-product rows.

**Acceptance Scenarios**:

1. **Given** the Categorization card, **When** the admin picks categories via `ResourceMultiAutocomplete` (`categoryAutocompleteProps`), **Then** `category_ids` updates and ships as-is on PATCH — category hierarchy/tree mechanics themselves belong to `012-categories-and-taxonomy`, not this feature.
2. **Given** the Categorization card's tags field, **When** the admin uses `TagCombobox` with `taggableType="Spree::Product"`, **Then** free-text tags are added/removed from the `tags` array.
3. **Given** the Variants card / `variants-options-builder.tsx`, **When** the admin defines option types and values, **Then** the variants matrix (`variants-matrix.ts`) generates one row per combination, each mapped through `variantToWirePayload` on submit (1-indexed `position`, `sku`/`weight` defaulted to schema NOT-NULL defaults, all other scalars sent explicitly — including `null` — so the merchant can clear them).

### Edge Cases

- What happens when a merchant deletes a variant that already has media assigned to it? `assignableVariants` is derived by intersecting `product.variants` against the *live* form `variants` array (post-matrix-trash), so a deleted-but-unsaved variant drops out of the Media card's assignment picker immediately.
- How does the system handle a media upload still in flight when the merchant edits an unrelated card and `mediaItems` later resolves? A dedicated hydration `useEffect` (bypassing the `isDirty` guard) paints in persisted media only when `form.media` is still empty and the media field itself isn't already dirty — otherwise the gallery would render permanently blank.
- What happens on save when the merchant has cleared every price/currency row from a variant? `variantToWirePayload` always ships `prices` (even `[]`) because the backend's `Spree::Variant#prices=` treats array presence as "replace all base prices" — omitting the key would silently leave stale amounts in place.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The dashboard MUST render a single product detail page (`ResourceLayout` with `main`/`sidebar` card slots) backed entirely by the Admin API (`useProduct`, expand list includes `default_variant`, `variants`, `option_types`, `categories`, `tax_category`, `product_publications`, `channels`, `custom_fields`).
- **FR-002**: The product form MUST be a single React Hook Form instance (`productFormSchema` / Zod) whose cards (`GeneralCard`, `VariantsCard`, `MediaCard`, `PricesCard`, `InventoryCard`, `StatusCard`, `PublishingCard`, `CategorizationCard`, `TaxCard`, `SEOCard`) share one submit path.
- **FR-003**: Saving MUST NOT reset in-progress edits from a concurrent background refetch (`isDirty` guard before `form.reset`).
- **FR-004**: The Media card MUST support drag-and-drop reorder (dnd-kit `DndContext`/`SortableContext`, `rectSortingStrategy`, `PointerSensor` + `KeyboardSensor`) and renumber `position` to the new order — never a numeric position input.
- **FR-005**: Media deletion MUST call the dedicated `DELETE` media endpoint directly, independent of the product PATCH save cycle.
- **FR-006**: The Publishing card MUST let an admin add/remove channels via a management sheet and independently schedule `published_at`/`unpublished_at` per channel, with product `status` acting as the outer visibility gate.
- **FR-007**: The Categorization card MUST support multi-category assignment and free-text tagging, both independent of the variants/options matrix.
- **FR-008**: The Variants card MUST derive its matrix rows from the option-types builder and map each row to the wire payload shape the Admin API's variant reconciliation (`Spree::Product#variants=`) expects (id-based upsert/delete).
- **FR-009**: All user-visible strings on the page (labels, statuses, captions, toasts) MUST go through i18next (`admin.pages.products.*`, `admin.fields.*`).

### Key Entities

- **Product form state** (`ProductFormValues`): client-only aggregate of name/description/status/category_ids/tags/tax_category_id/meta fields/slug/variants[]/custom_fields[]/media[]/product_publications[] — not a persisted entity itself, assembled from and disassembled back into `Spree::Product`/`Spree::Variant`/`Spree::Asset`/`Spree::ProductPublication` API resources.
- **Media form row**: `{ id, alt, position, variant_ids, previewUrl, signed_id?, uploadId? }` — `signed_id`/`uploadId`/`previewUrl` are UI-only and stripped before the PATCH payload is built.
- **Publication form row**: `{ id?, channel_id, published_at, unpublished_at }` mapped from/to `Spree::ProductPublication`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | No | Consumed via Admin API only — see `010-products-and-variants`, `012-categories-and-taxonomy` |
| `spree/api` (Store/Admin API v3) | No | Existing endpoints consumed as-is; no new attributes required by this UI layer |
| `packages/dashboard` (admin SPA) | Yes | Product detail route + form cards + media/publishing/categorization editors + hooks (`use-product`, `use-product-media`, `use-categories`, `use-channels`) |
| `packages/dashboard-ui` / `dashboard-core` | No | Consumes existing primitives (`Sheet`, `StoreDatePicker`, `ResourceMultiAutocomplete`, `TagCombobox`) — no new primitives added by this feature |
| `packages/sdk` / `packages/admin-sdk` | No | Types (`Product`, `Variant`, `Media`, `Channel`) already generated from existing serializers |
| `docs/plans/` | No | No new architectural change; implements within boundaries of `6.0-remove-master-variant.md`, `6.0-channels-catalogs-b2b.md`, `6.0-product-media-system.md` (all pre-existing) |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can edit and save a product's core fields, media order, channel publications, categories, and variants matrix from a single page load, with zero full-page reloads.
- **SC-002**: A background refetch (window refocus, unrelated mutation invalidation) never discards an admin's unsaved edits mid-session.
- **SC-003**: Media reorder via drag-and-drop persists in the dragged order on next page load, with no gaps or duplicate `position` values.
- **SC-004**: Every field visible on the page resolves through i18next in all shipped locales (no hardcoded English strings).

## Assumptions

- The Admin API v3 product/media/channel/category endpoints (covered by `010-products-and-variants`, `012-categories-and-taxonomy`, `019-channels-and-order-routing`) are stable and already implemented; this feature only covers their SPA consumption.
- Bulk/multi-row editing across many products (CSV-like grid) is out of scope here — see `034-bulk-editing-ui` and `035-data-grid-component`.
- Product creation (`New Product` flow, `seedDefaultChannel` behavior) shares the same form cards as edit; this spec documents the edit page as the canonical surface and calls out the one create-only branch (default channel seeding).

## Migration Notes

- **Drag-and-drop reorder confirmed**: The Media card (`product-form-cards.tsx` `MediaCard`, ~L340-L440) implements the constitution-mandated dnd-kit pattern (`DndContext` + `SortableContext` with `rectSortingStrategy` for the grid layout, `PointerSensor` with `activationConstraint: { distance: 5 }` + `KeyboardSensor`), matching the `acts_as_list` reorder convention described in the root `CLAUDE.md` ("`acts_as_list` ⇒ drag-and-drop reorder, never a numeric position input") even though media position lives on `Spree::Asset`, not a dedicated join table.
- **No gaps requiring `[NEEDS CLARIFICATION]`** were found for the primary editing flows (general/media/publishing/categorization/variants) — all have working e2e coverage (`products-edit.spec.ts`, `products-edit-media-variants.spec.ts`, `products-new-media.spec.ts`, `products-publishing.spec.ts`, `products-variants.spec.ts`, `products-custom-fields.spec.ts`, `products-translations.spec.ts`, `products-bulk.spec.ts`, `products-prices-inventory.spec.ts`).
- **Cross-references, not re-described here**: backend `Spree::Product`/`Spree::Variant` models and Admin/Store API endpoints → `010-products-and-variants`; category tree/hierarchy CRUD → `012-categories-and-taxonomy`; multi-row bulk editing UI → `034-bulk-editing-ui`; the underlying data-grid primitive used elsewhere in the dashboard → `035-data-grid-component`; channel/order-routing model → `019-channels-and-order-routing`; custom fields inline card → `014-custom-fields-metafields`; resource translations card → `023-translations-i18n`.
- **Known architectural note carried from source comments**: purchasable attributes (sku, barcode, prices, weight, dimensions, stock, track_inventory) live on variants only — the product form has no top-level master-variant fields, per `docs/plans/6.0-remove-master-variant.md`. This UI already reflects that end-state; no migration work remains here.
