# Implementation Plan: Product Media

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: 5.4 + 5.5 data model shipped; SPA admin UI in progress

---

## Summary

Moved Spree from a variant-1:1-image model to a product-level media gallery where blobs are never duplicated. `Spree::Asset` gains `media_type`, `focal_point_x/y`, and `external_video_url` (5.4). A new `Spree::VariantMedia` join table (5.5) enables variants to reference product-level assets. The Store API switched from `expand=images` to `expand=media` (breaking change, 5.4). The Admin API added polymorphic upload and direct-upload endpoints. The SPA product media tab (drag-to-reorder, focal-point picker, alt text, variant assignment) is in progress for the product edit page. 6.0 renames `Spree::Asset` → `Spree::Media`.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **File storage** | Active Storage (S3 / GCS / local) |
| **Direct upload** | Active Storage direct upload (pre-signed blob → `signed_id`) |
| **Scope** | Full-stack — 5.4/5.5 data model + API complete; SPA UI in progress |

---

## Key Decisions

1. **Product is the default upload target in 5.5.** New uploads to `POST /admin/products/:id/media` default to `viewable_type: 'Spree::Product'`. Variant-level uploads still work via the `?variant_id=` path.
2. **Rename `images` → `media` in Store API (5.4, breaking).** Clean break — no deprecated alias. SDK bumped to 0.11.0.
3. **`viewable_id`/`viewable_type` excluded from Store API.** Admin-only fields. Storefronts don't need to know the upload target.
4. **Single `Spree::Asset` class** — `Spree::Image` is a thin backward-compat subclass only. No STI on `media_type`.
5. **`media_type` defaults to `'image'`, never null.** All existing records backfilled on migration.
6. **`VariantMedia` join has no `position` column** — gallery order comes from the asset's product-level `position`; merchants reorder once on the product gallery and every variant follows.
7. **Opt-in data migration rake** (`spree:migrate_master_images_to_product_media`) — never runs automatically. Becomes mandatory in 6.0 as part of master variant removal.
8. **`Spree::Asset` → `Spree::Media` rename deferred to 6.0** — prefix `media_…` already in use since 5.4; no client-side change required at rename time.
9. **Scope boundary: commerce entities only.** No general DAM, no "Files" page, no cross-entity library. See plan doc "Scope Boundary" section.

---

## Constitution Check

- [x] **API-First**: New media endpoints in Admin API before SPA consumed them
- [x] **Read/Write Symmetry**: `alt`, `focal_point_x`, `focal_point_y` serialized and accepted in `permitted_params`
- [x] **Prefixed IDs**: `media_…` prefix on all asset IDs; `viewable_id` is prefixed in admin responses
- [x] **Serializer Hierarchy**: `Admin::MediaSerializer` extends `V3::MediaSerializer`; no `viewable_id/type` in Store
- [x] **Type Pipeline**: Typelizer + Zod regen after 5.4 serializer changes; SDK 0.11.0 changeset
- [x] **Security**: CanCanCan via parent product authorization; same-product guard on `variant_ids=`
- [x] **Namespace**: `Spree::Asset`, `Spree::Image`, `Spree::VariantMedia` — `Spree.base_class`
- [x] **Plan Conflicts**: Reviewed `6.0-remove-master-variant.md` — Phase 2 of master removal absorbs media re-homing; no conflict

---

## Project Structure

```text
# Backend
spree/core/app/models/spree/asset.rb                    ← single class, all media logic
spree/core/app/models/spree/image.rb                    ← thin backward-compat subclass
spree/core/app/models/spree/variant_media.rb            ← 5.5 join table

spree/api/app/serializers/spree/api/v3/media_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/media_serializer.rb
spree/api/app/controllers/spree/api/v3/admin/media_controller.rb
spree/api/app/controllers/spree/api/v3/admin/direct_uploads_controller.rb

# Type pipeline (auto-generated)
packages/sdk/src/types/generated/
packages/admin-sdk/src/types/generated/

# Frontend (in progress)
packages/dashboard/src/routes/_authenticated/$storeId/products/$productId.tsx   ← Media tab
packages/dashboard/e2e/products-edit-media-variants.spec.ts
packages/dashboard/e2e/products-new-media.spec.ts
```

---

## Phase 1: 5.4 — Data Model + Store API (✅ Complete, PR #13778)

- New columns on `spree_assets`: `media_type`, `focal_point_x/y`, `external_video_url`; backfill `media_type = 'image'`
- `Spree::Image` merged into `Spree::Asset`; `Spree::Image` kept as thin subclass
- `MediaSerializer` replaces `ImageSerializer`; `expand=media` replaces `expand=images`
- `Admin::MediaSerializer` extends Store; adds `viewable_id`, `viewable_type`, `download_url`
- Type pipeline run; SDK 0.11.0

---

## Phase 2: 5.5 — VariantMedia + Product-Level API (✅ Complete)

- New table `spree_variant_media` + `Spree::VariantMedia` model
- `Variant#variant_media`, `Variant#associated_media` associations
- `Variant#gallery_media` prefers `associated_media` over direct `images`
- `Product#media` association (`viewable_type: 'Spree::Product'`)
- `POST /admin/products/:id/media` defaults to `viewable_type: 'Spree::Product'`
- `PATCH /admin/products/:id/media/:id { variant_ids: [...] }` — `Asset#variant_ids=` setter with same-product guard
- `POST /admin/direct_uploads` — pre-signs Active Storage blob

---

## Phase 3: Admin SPA UI (⚠️ In Progress)

- Product detail page → Media tab: drag-and-drop upload (`rectSortingStrategy` grid), focal-point picker, alt text editor
- Variant detail tab → "Select from product gallery" multi-select dialog
- ⚠️ **Missing**: `use-product-media.ts` dedicated hook (currently embedded in `$productId.tsx`)

---

## Phase 4: 6.0 Pending

- `Spree::Asset` → `Spree::Media`; table `spree_assets` → `spree_media`
- Remove `Spree::Image` subclass
- Remove `viewable_id`/`viewable_type` from Admin API responses
- Drop `Product#variant_images` and `Product#variant_images_without_master`
- Master removal Phase 2 runs data migration for any merchant who didn't run the opt-in rake

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Breaking API change (`images` → `media`) in 5.4 | Clean, unambiguous API naming; no aliased noise in perpetuity | An alias (`expand=images` still working) would require maintaining two code paths through 6.0 |
| Polymorphic `viewable` on Asset | Both Product and Variant can own media | Separate tables would duplicate the storage logic and require dual endpoints |
