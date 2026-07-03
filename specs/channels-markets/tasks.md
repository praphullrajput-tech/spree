---

description: "Task list for Channels & Markets — Phase 1 shipped in 5.5; Phase 2 Catalog/Company pending in 6.0"
---

# Tasks: Channels & Markets

**Status**: Phase 1 fully shipped in 5.5; Phase 2 (Catalog + B2B) pending in 6.0

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Dashboard route | `packages/dashboard/src/routes/_authenticated/$storeId/settings/channels.tsx` |
| Dashboard hooks | `packages/dashboard/src/hooks/use-channels.ts` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core + API + SPA ✅

### Models & Migrations

- [x] T001 `spree/core/app/models/spree/channel.rb` — `has_prefix_id :ch`; `store_id` NOT NULL; `name`, `code` unique per store; `default` boolean; `active`; `OrderRouting::HasStrategyPreference`; `after_create :ensure_default_order_routing_rules`; `before_save :demote_other_defaults`; `add_products(ids, published_at:, unpublished_at:)` via `upsert_all`; `remove_products(ids)`
- [x] T002 `spree/core/app/models/spree/product_publication.rb` — `has_prefix_id :pp`; `product_id`, `channel_id`; `published_at`, `unpublished_at`; unique index `(product_id, channel_id)`
- [x] T003 `spree/core/app/models/spree/product/channels.rb` — `has_many :product_publications`, `has_many :channels through: :product_publications`; custom setter; `publish_to!`, `unpublish_from!`, `published_to_channel?`
- [x] T004 Migrations: `create_spree_channels`, `create_spree_product_publications`, `add_default_to_spree_channels`

### Serializers

- [x] T005 `spree/api/app/serializers/spree/api/v3/admin/channel_serializer.rb` — `ch_` prefix; name, code, active, default, preferred_order_routing_strategy, timestamps

### Controllers

- [x] T006 `spree/api/app/controllers/spree/api/v3/admin/channels_controller.rb` — full CRUD; `add_products` (POST); `remove_products` (POST)
- [x] T007 `spree/api/app/controllers/spree/api/v3/admin/products_controller.rb` — `bulk_add_to_channels`, `bulk_remove_from_channels` bulk actions

### Type Pipeline

- [x] T008 `bundle exec rake typelizer:generate` — `AdminChannel` type
- [x] T009 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T010 `packages/dashboard/src/routes/_authenticated/$storeId/settings/channels.tsx` — list; create/edit sheet; routing strategy selector
- [x] T011 `packages/dashboard/src/hooks/use-channels.ts` — TanStack Query wrappers
- [x] T012 `packages/dashboard/src/tables/channels.tsx` — default badge, active toggle
- [x] T013 Add i18n keys under `admin.channels.*` in all locale files

### E2E

- [x] T014 `packages/dashboard/e2e/channels.spec.ts` — CRUD
- [x] T015 `packages/dashboard/e2e/channels-settings.spec.ts` — code auto-derive; edit; default promotion
- [x] T016 Run `pnpm test:e2e` ✅

**Checkpoint**: channel CRUD; product publications; bulk product assign; routing strategy; E2E ✅

---

## Phase 2: 6.0 — Catalog + Company/B2B (PENDING)

Per `6.0-channels-catalogs-b2b.md`:

- [ ] T017 `Spree::Catalog` model — `cat_` prefix; optional `price_list_id`; `has_many :catalog_products`
- [ ] T018 `Spree::CatalogAssignment` — polymorphic join (Channel/CustomerGroup/CompanyLocation/Market)
- [ ] T019 `Spree::Company` — `comp_` prefix; B2B organization
- [ ] T020 `Spree::CompanyLocation` — `cloc_` prefix; `preferred_stock_location_id`
- [ ] T021 `Spree::CompanyContact` — `cc_` prefix; links User to Company
- [ ] T022 `Spree::Products::ForContext` — visibility resolution logic
- [ ] T023 Admin API: Catalog CRUD + assignment; Company hierarchy CRUD
- [ ] T024 SPA: Catalog management; Company management

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No per-channel product publication scheduling UI | Low | Model supports `published_at`/`unpublished_at`; SPA shows simple publish/unpublish |
| Catalog + Company pending | Medium | Required for B2B use cases; tracked in `6.0-channels-catalogs-b2b.md` |
