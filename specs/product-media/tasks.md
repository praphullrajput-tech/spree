---

description: "Task list for Product Media — 5.4/5.5 complete, SPA UI in progress"
---

# Tasks: Product Media

**Status**: 5.4 + 5.5 backend complete; SPA Media tab in progress; 6.0 rename pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Store serializers | `spree/api/app/serializers/spree/api/v3/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/products/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Backend Foundation — 5.4 ✅ (PR #13778)

- [x] T001 Create migration `*_add_media_columns_to_spree_assets.rb` — add `media_type string null: false default: 'image'`, `focal_point_x decimal`, `focal_point_y decimal`, `external_video_url string`; backfill `media_type = 'image'` on all existing records
- [x] T002 Update `spree/core/app/models/spree/asset.rb` — merge `Spree::Image` logic; validate `media_type` inclusion in `['image', 'video', 'external_video']`; validate `focal_point_x/y` in 0.0–1.0 range; `gallery_media` accessor
- [x] T003 Update `spree/core/app/models/spree/image.rb` — thin backward-compat subclass; sets `media_type: 'image'`; no added logic

**Checkpoint**: existing image tests still pass ✅

---

## Phase 2: Backend API — 5.4 ✅

- [x] T004 [P] [US3] Create Store serializer `spree/api/app/serializers/spree/api/v3/media_serializer.rb` — replaces `ImageSerializer`; `media_type`, `position`, `alt`, `focal_point_x/y`, `external_video_url`, `product_id` (prefixed), image URL variants; NO `viewable_id/type`
- [x] T005 [P] [US3] Create Admin serializer `spree/api/app/serializers/spree/api/v3/admin/media_serializer.rb` — extends Store; adds `viewable_id` (prefixed), `viewable_type`, `download_url`, `metadata`, timestamps
- [x] T006 [US1] Create Admin controller `spree/api/app/controllers/spree/api/v3/admin/media_controller.rb` — polymorphic upload (image URL, direct upload signed_id, or external URL); product/variant scoping; `PATCH` supports `variant_ids` via `Asset#variant_ids=`
- [x] T007 [US1] Create `spree/api/app/controllers/spree/api/v3/admin/direct_uploads_controller.rb` — pre-sign Active Storage blob; return `signed_id`
- [x] T008 [US3] Update product + variant serializers to use `expand=media` (replace `expand=images`)
- [x] T009 [US3] Update routes: `resources :media` nested under `products`; add `resources :direct_uploads`
- [x] T010 Run `bundle exec rake rswag:specs:swaggerize`

**Checkpoint**: Store API returns `"media"` key ✅; `expand=images` no longer works ✅

---

## Phase 3: Type Generation Pipeline — 5.4 ✅

- [x] T011 `cd spree/api && bundle exec rake typelizer:generate` — `StoreMedia` type generated; `StoreImage` removed
- [x] T012 `cd packages/sdk && pnpm generate:zod`
- [x] T013 `pnpm typecheck`
- [x] T014 Changeset for `@spree/sdk` (0.11.0) and `@spree/admin-sdk`

---

## Phase 4: Backend — 5.5 VariantMedia ✅

- [x] T015 Create migration `*_create_spree_variant_media.rb` — `variant_id reference null: false`, `media_id integer null: false` (FK to `spree_assets`); unique index on `[variant_id, media_id]`; NO `position` column
- [x] T016 Create model `spree/core/app/models/spree/variant_media.rb` — `belongs_to :variant`, `belongs_to :asset` (FK: `media_id`); validates asset belongs to variant's product; `after_create/destroy` triggers thumbnail refresh
- [x] T017 Update `Spree::Variant` — add `has_many :variant_media`, `has_many :associated_media, through: :variant_media, source: :asset`; update `gallery_media` to prefer `associated_media`
- [x] T018 Update `Spree::Product` — add `has_many :media, as: :viewable`; `gallery_media` falls back to `variant_images` when product-level media is absent
- [x] T019 Update `Spree::Asset` — add `variant_ids=` setter: resolves prefixed IDs, enforces same-product, uses `has_many :through` setter; add `has_many :variant_media`; update `should_touch_product_variants?` for `Spree::Product` branch
- [x] T020 Update Admin controller — `POST /products/:id/media` defaults to `viewable_type: 'Spree::Product'`

---

## Phase 5: Frontend — SPA Media Tab (⚠️ IN PROGRESS)

- [ ] T021 [US1] Extract `packages/dashboard/src/hooks/use-product-media.ts` — TanStack Query wrappers: list, create (upload), update (alt/focal_point/position/variant_ids), delete; separate from product hook
- [ ] T022 [US1] Implement Media tab within `packages/dashboard/src/routes/_authenticated/$storeId/products/$productId.tsx` — drag-and-drop grid (`rectSortingStrategy`); `PointerSensor(activationConstraint: { distance: 5 })` + `KeyboardSensor`; on drag end: `updateMedia(id, { position })`
- [ ] T023 [US1] Focal point picker — numeric `x`/`y` inputs (0.0–1.0); visual preview if available
- [ ] T024 [US1] Alt text input — inline edit per media item
- [ ] T025 [US2] Variant media assignment — "Select from product gallery" multi-select dialog on variant detail tab; PATCH `variant_ids` on selected assets
- [ ] T026 [US1] Direct upload integration — `POST /direct_uploads` → signed_id → `POST /media { signed_id }`
- [ ] T027 [US1] Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.products.media.*`
- [ ] T028 [US1] Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

**Checkpoint**: `pnpm typecheck && pnpm lint` pass; product media tab renders, upload works, reorder persists

---

## Phase 6: E2E ✅ (partial)

- [x] T029 `packages/dashboard/e2e/products-new-media.spec.ts` — product creation with media upload
- [x] T030 `packages/dashboard/e2e/products-edit-media-variants.spec.ts` — product edit with media + variant assignment
- [ ] T031 Add E2E coverage for focal-point picker and alt text editing (once SPA tab complete)

---

## Phase 7: 6.0 — Asset → Media Rename (PENDING)

- [ ] T032 Migration: rename `spree_assets` → `spree_media`; update `viewable_type` column values (`'Spree::Asset'` → `'Spree::Media'` where applicable)
- [ ] T033 Rename `Spree::Asset` → `Spree::Media`; drop `Spree::Image` subclass
- [ ] T034 Remove `viewable_id`/`viewable_type` from Admin API responses
- [ ] T035 Drop `Product#variant_images` and `Product#variant_images_without_master` accessors
- [ ] T036 Run `spree:migrate_master_images_to_product_media` as part of master removal Phase 2

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No dedicated `use-product-media.ts` hook — media operations embedded in `$productId.tsx` | High | T021 above — extract as dedicated hook before SPA media tab UI is complete |
| SPA Media tab (drag-to-reorder, focal-point, alt text, variant assignment) not yet implemented | High | T022–T028 above — in active development per plan doc Phase 4 |
| No focal point visual picker — currently numeric inputs only | Low | Can be enhanced post-launch; numeric inputs satisfy functional requirement |
| Hosted video upload not supported — only external URLs | Low | Deferred per plan doc "Open Questions"; `external_video_url` covers YouTube/Vimeo |
