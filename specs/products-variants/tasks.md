---

description: "Task list for Products & Variants — fully shipped; 6.0 remove-master-variant + product-types pending"
---

# Tasks: Products & Variants

**Status**: Fully shipped; Phase 2 (6.0 cleanup) pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Product concerns | `spree/core/app/models/spree/product/` |
| Migrations | `spree/core/db/migrate/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/products/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core + API + SPA ✅

### Models

- [x] T001 `spree/core/app/models/spree/product.rb` — `has_prefix_id :prod`; `acts_as_paranoid`; `status` string: `draft`/`active`/`archived`; `default_variant_id` FK; `include TranslatableResource`; `include MemoizedData`; `include Spree::Metafields`; `include Spree::Metadata`; `include Spree::Webhooks`; `include Spree::Slugs`; `include Spree::Channels`; `include SearchIndexable`; `friendly_id :slug`; computed: `in_stock`, `purchasable`, `total_on_hand`
- [x] T002 `spree/core/app/models/spree/product/channels.rb` — `has_many :channels` via join; `published_to_channel?`; `publish_to!`; `unpublish_from!`
- [x] T003 `spree/core/app/models/spree/product/slugs.rb` — `friendly_id :name`; slug uniqueness scoped to store
- [x] T004 `spree/core/app/models/spree/product/webhooks.rb` — `publishes_lifecycle_events` callbacks
- [x] T005 `spree/core/app/models/spree/variant.rb` — `has_prefix_id :variant`; `include MemoizedData`; `include Spree::Metafields`; `include Spree::Metadata`; `include Searchable`; `include Spree::Webhooks`; `include DefaultPrice`; `is_master` boolean (legacy); `position`; `sku`; weight/depth/height/width; computed: `purchasable`, `in_stock`, `on_sale`, `options_text`

### Serializers

- [x] T006 [P] `spree/api/app/serializers/spree/api/v3/admin/product_serializer.rb` — extends `V3::ProductSerializer`; adds `status`, `tax_category_id`, `cost_price`, `private_metadata`, `deleted_at`, timestamps
- [x] T007 [P] `spree/api/app/serializers/spree/api/v3/admin/variant_serializer.rb` — extends `V3::VariantSerializer`; adds `cost_price`, `is_master`, `metadata`, `private_metadata`, `deleted_at`, timestamps

### Controllers

- [x] T008 `spree/api/app/controllers/spree/api/v3/admin/products_controller.rb` — full CRUD; `clone` member action; bulk: `bulk_status_update`, `add_to_categories`, `remove_from_categories`, `add_to_channels`, `remove_from_channels`
- [x] T009 `spree/api/app/controllers/spree/api/v3/admin/variants_controller.rb` — nested under products; full CRUD

### Specs

- [x] T010 `spree/core/spec/models/spree/product_spec.rb` — status transitions; `in_stock`/`purchasable` computed; slug uniqueness; `default_variant_id`
- [x] T011 `spree/core/spec/models/spree/variant_spec.rb` — price delegation; `purchasable` when stock 0; `on_sale` when compare_at_price > price
- [x] T012 `spree/api/spec/integration/spree/api/v3/admin/products_spec.rb` — CRUD; clone; bulk status update; category/channel assignments

### Type Pipeline

- [x] T013 `bundle exec rake typelizer:generate` — `AdminProduct`, `AdminVariant` types generated
- [x] T014 `cd packages/sdk && pnpm generate:zod`
- [x] T015 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T016 [US1] `packages/dashboard/src/routes/_authenticated/$storeId/products/index.tsx` — list with ResourceTable, bulk ops dialog, export, filter by status/category/channel
- [x] T017 [US1/US2] `packages/dashboard/src/routes/_authenticated/$storeId/products/$productId.tsx` — detail: variants panel, media gallery, pricing, inventory, SEO, categories, channels, metafields, translations
- [x] T018 `packages/dashboard/src/hooks/use-products.ts` — TanStack Query wrappers with pagination, sorting, Ransack search
- [x] T019 Add i18n keys under `admin.products.*` and `admin.variants.*` in all locale files

### E2E

- [x] T020 `packages/dashboard/e2e/products-pricing.spec.ts`
- [x] T021 `packages/dashboard/e2e/products-inventory.spec.ts`
- [x] T022 `packages/dashboard/e2e/products-publishing.spec.ts`
- [x] T023 `packages/dashboard/e2e/products-bulk.spec.ts`
- [x] T024 `packages/dashboard/e2e/products-variants.spec.ts`
- [x] T025 `packages/dashboard/e2e/products-translations.spec.ts`
- [x] T026 `packages/dashboard/e2e/products-media.spec.ts`
- [x] T027 Run `pnpm test:e2e` ✅

**Checkpoint**: full product + variant CRUD; bulk ops; clone; search; comprehensive E2E coverage ✅

---

## Phase 2: 6.0 Cleanup (PENDING)

Per `6.0-remove-master-variant.md`:

- [ ] T028 Migration: drop `is_master` column from `spree_variants`
- [ ] T029 Update all queries: replace `variants.where(is_master: true)` with `products.default_variant` via `default_variant_id` FK
- [ ] T030 Remove `is_master` from variant serializer; ensure `default_variant_id` on product serializer is the canonical reference

Per `6.0-product-types.md`:

- [ ] T031 Rename `Spree::Prototype` → `Spree::ProductType`; update all references
- [ ] T032 `MetafieldDefinition` schema enforcement per product type

Per `6.0-channels-catalogs-b2b.md`:

- [ ] T033 `Spree::ProductPublication` replaces `StoreProduct`; products get `belongs_to :store` (single-owner)

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| `is_master` boolean still on Variant | Low | By design in 5.x; T028–T030 removes it in 6.0 |
| Product type (Prototype) management not in SPA | Low | Tracked in `6.0-product-types.md`; legacy admin covers it in 5.x |
