# Feature Specification: Product Media

**Feature Branch**: `main` (5.4 data model + Store API ✅; 5.5 VariantMedia + product-level API ✅; SPA UI in progress)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: `docs/plans/5.4-6.0-product-media-system.md`

---

## User Scenarios & Testing

### User Story 1 — Upload and Manage Product Media (Priority: P1)

An admin operator uploads images (and optionally external video URLs) directly to a product's media gallery. They can reorder media by dragging, set alt text, set a focal point for smart cropping, and delete items. All variants of the product inherit the product-level gallery via the `gallery_media` accessor.

**Why this priority**: Every product needs images. This is the baseline for visual merchandising.

**Independent Test**: Admin opens a product, uploads 3 images to the Media tab, reorders them by dragging, sets alt text on the first, then deletes the second. The Store API `GET /api/v3/products/:id?expand=media` returns 2 images in the new order with the correct `alt` text.

**Acceptance Scenarios**:

1. **Given** a product, **When** admin uploads an image via the Admin API, **Then** an `Spree::Asset` record is created with `viewable_type: 'Spree::Product'`, `media_type: 'image'`, and a prefixed ID (`media_…`)
2. **Given** a product with media, **When** admin reorders them by dragging, **Then** `position` updates and the order persists after reload
3. **Given** a product, **When** admin sets `focal_point_x: 0.7, focal_point_y: 0.3`, **Then** these values are returned in the API response for smart-crop use
4. **Given** a product, **When** admin adds an external video URL (YouTube/Vimeo), **Then** `media_type: 'external_video'` and `external_video_url` are returned
5. **Given** a media item, **When** admin deletes it, **Then** the Active Storage attachment and the `Spree::Asset` record are destroyed

---

### User Story 2 — Assign Media to Variants (Priority: P2)

An admin operator links product-level media assets to specific variants so each variant can display its own gallery subset without re-uploading images. This uses the `VariantMedia` join table introduced in 5.5.

**Why this priority**: Variants (e.g., different colour options) need distinct images without blob duplication.

**Independent Test**: Admin picks a "Red" variant on the product page, selects the "Red" product-level image from the product gallery, and links it. `GET /api/v3/products/:id/variants/:variant_id?expand=media` returns only the "Red" image.

**Acceptance Scenarios**:

1. **Given** a product with 3 media assets, **When** admin links one asset to a specific variant via `PATCH /admin/products/:id/media/:asset_id { variant_ids: ["variant_…"] }`, **Then** a `VariantMedia` row is created
2. **Given** a variant with linked media, **When** `variant.gallery_media` is called, **Then** it returns `associated_media` (via `VariantMedia`) rather than direct variant images
3. **Given** an empty `variant_ids: []`, **When** the PATCH is sent, **Then** all existing `VariantMedia` rows for that asset are cleared
4. **Given** a `variant_ids` array containing a variant from a different product, **When** the assignment is attempted, **Then** it is silently dropped (same-product guard on `Asset#variant_ids=`)

---

### User Story 3 — Storefront Consumes Media (Priority: P3)

A storefront developer fetches product and variant media using `expand=media` on the Store API. The response includes `media_type`, `position`, `alt`, `focal_point_x/y`, and size-keyed URLs (`original_url`, `mini_url` … `xlarge_url`).

**Why this priority**: Pure read path — no UI changes. But the API contract change from `expand=images` to `expand=media` is a breaking change requiring documentation.

**Independent Test**: `GET /api/v3/products/:id?expand=media` returns a `media` array (not `images`) with `media_type`, `focal_point_x/y`, and image URLs. `expand=images` no longer works.

**Acceptance Scenarios**:

1. **Given** a product with media, **When** `GET /api/v3/products/:id?expand=media` is called, **Then** response key is `"media"` (not `"images"`)
2. **Given** a media item with `media_type: 'image'`, **When** the Store API returns it, **Then** `viewable_id` and `viewable_type` are NOT included (admin-only fields)
3. **Given** `media_type: 'external_video'`, **When** the Store API returns it, **Then** `external_video_url` is populated and image URLs are null
4. **Given** a variant with linked product-level media, **When** `GET /api/v3/products/:id/variants/:id?expand=media` is called, **Then** `associated_media` is returned

---

### Edge Cases

- What if a media item's Active Storage blob is missing? → `original_url` returns nil; other sized URLs also nil
- What if `focal_point_x` is outside 0.0–1.0? → Validation on the model; API returns 422
- What if both `color_code` and `image_url` are present on an option value (from Option Types feature)? → Different models — no interaction
- What if the merchant hasn't run the opt-in data migration rake? → Legacy master-pinned assets continue displaying via `gallery_media` fallback
- _(6.0 pending)_ What if the `Spree::Asset` model is renamed to `Spree::Media`? → Prefix `media_…` already in use since 5.4; no client change required

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::Asset` must have `media_type` (string, default `'image'`, required), `focal_point_x`, `focal_point_y` (decimal, nullable), `external_video_url` (string, nullable)
- **FR-002**: `Spree::Asset` is polymorphic (`viewable_type` / `viewable_id`) supporting `Spree::Product` and `Spree::Variant` as viewable targets
- **FR-003**: `Spree::Image < Spree::Asset` is a thin backward-compat subclass (sets `media_type: 'image'`)
- **FR-004**: `Spree::VariantMedia` join table links variants to product-level assets without blob duplication
- **FR-005**: `Spree::Variant#gallery_media` returns `associated_media` (via VariantMedia) when populated; falls back to direct `images`
- **FR-006**: Store API must use `expand=media` (not `expand=images`); response key is `"media"`; `viewable_id`/`viewable_type` excluded from Store API
- **FR-007**: Admin API must expose `POST /admin/products/:id/media` for product-level uploads; default `viewable_type: 'Spree::Product'`
- **FR-008**: Admin API must support `PATCH /admin/products/:id/media/:asset_id { variant_ids: [...] }` for variant-asset linking
- **FR-009**: Direct Upload support via `POST /api/v3/admin/direct_uploads` (returns signed blob ID for subsequent media create)
- **FR-010**: All media IDs prefixed `media_…`; `viewable_id` in admin responses is a prefixed ID
- **FR-011**: _(6.0 pending)_ Rename `Spree::Asset` → `Spree::Media`; `spree_assets` → `spree_media`
- **FR-012**: _(6.0 pending)_ Remove `viewable_id`/`viewable_type` from Admin API responses (callers use nested route context)

### Key Entities

- **Asset** (`Spree::Asset`): A media item (image, video, external video). `media_type`, `position`, `alt`, `focal_point_x/y`, `external_video_url`. Polymorphic `viewable`.
- **Image** (`Spree::Image < Spree::Asset`): Backward-compat subclass; always `media_type: 'image'`.
- **VariantMedia** (`Spree::VariantMedia`): Join between `Spree::Variant` and `Spree::Asset`. Enables per-variant gallery from product-level assets.

---

## Backend Requirements

### Data Model

- **New columns on `spree_assets`** (5.4): `media_type string null: false default: 'image'`, `focal_point_x decimal`, `focal_point_y decimal`, `external_video_url string`
- **New table `spree_variant_media`** (5.5): `variant_id`, `media_id` (FK to `spree_assets`), unique index on `[variant_id, media_id]`
- **No FK constraints**; no default values on new columns

### API Surface

#### Store API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/products/:id?expand=media` | Product with media gallery |
| GET | `/api/v3/products/:id/variants/:id?expand=media` | Variant with its media |

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/products/:id/media` | List product media |
| POST | `/api/v3/admin/products/:id/media` | Upload media (image URL, signed_id, or external URL) |
| PATCH | `/api/v3/admin/products/:id/media/:id` | Update media (alt, focal_point, position, variant_ids) |
| DELETE | `/api/v3/admin/products/:id/media/:id` | Delete media |
| POST | `/api/v3/admin/direct_uploads` | Pre-sign Active Storage direct upload |

### Serializer Fields

**Store serializer** (`Spree::Api::V3::MediaSerializer`):
- `id`: prefixed string (`media_…`)
- `media_type`: string
- `position`: number
- `alt`: string | null
- `focal_point_x`, `focal_point_y`: number | null
- `external_video_url`: string | null
- `original_url`, `mini_url`, `small_url`, `product_url`, `large_url`, `xlarge_url`: string | null
- `product_id`: prefixed string | null
- *(No `viewable_id`, `viewable_type`)*

**Admin serializer** (`Spree::Api::V3::Admin::MediaSerializer`, extends Store):
- `viewable_id`: prefixed string
- `viewable_type`: string
- `download_url`: string (with `disposition: attachment`)
- `metadata`
- `created_at`, `updated_at`

### Authorization

- CanCanCan: `can :manage, Spree::Asset` for admin; gated through parent product authorization

### i18n (Rails)

- Keys under `spree.asset.*`

---

## Frontend Requirements

### SPA Routes

- Media UI is embedded in `packages/dashboard/src/routes/_authenticated/$storeId/products/$productId.tsx` (Media tab) — no dedicated route

### Resource Hooks

- ⚠️ **Missing dedicated hook** — media operations are currently embedded directly in `$productId.tsx`; a `packages/dashboard/src/hooks/use-product-media.ts` hook is the recommended refactor

### i18n Keys

Under `admin.products.media.*` in all 6 locale files: tab label, upload button, alt text label, focal point label, delete confirm, empty state, toast messages.

### Drag-and-drop

Product media grid — `DndContext` + `SortableContext` with `rectSortingStrategy` (grid layout); `PointerSensor` + `KeyboardSensor`; on drag end call `updateMedia(id, { position })`.

---

## Success Criteria

- **SC-001**: `GET /api/v3/products/:id?expand=media` returns `"media"` key (not `"images"`) with `media_type`, `focal_point_x/y`, and image URLs
- **SC-002**: Admin can upload an image to a product and it is stored with `viewable_type: 'Spree::Product'`
- **SC-003**: `PATCH /api/v3/admin/products/:id/media/:id { variant_ids: [...] }` creates `VariantMedia` rows and `variant.gallery_media` returns the linked asset
- **SC-004**: `media_type: 'image'` is always present on new uploads; never null
- **SC-005**: Direct Upload flow: `POST /direct_uploads` → signed_id → `POST /media { signed_id }` completes without re-uploading the blob

---

## Assumptions

- Active Storage is configured (S3, GCS, or local disk)
- The breaking API change (`expand=images` → `expand=media`) was made in 5.4; storefront SDK consumers have migrated
- The opt-in data migration rake (`spree:migrate_master_images_to_product_media`) is available but not run automatically; legacy master-pinned images continue working via `gallery_media` fallback until 6.0
- `Spree::Asset` → `Spree::Media` rename is deferred to 6.0 (coincides with master variant removal)
- No general-purpose file library or DAM — media is scoped to commerce entities (products, variants) only
