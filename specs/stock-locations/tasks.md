---

description: "Task list for Stock Locations — fully shipped; 6.0 activity tab pending"
---

# Tasks: Stock Locations

**Status**: Fully shipped; 6.0 Activity tab pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/settings/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core Stock Location Management ✅

### Models

- [x] T001 `spree/core/app/models/spree/stock_location.rb` — `has_prefix_id :sloc`; `KINDS = %w[warehouse store fulfillment_center]`; `PICKUP_STOCK_POLICIES = %w[local any]`; `include Spree::UniqueName`; `acts_as_paranoid`; associations: `has_many :stock_items`, `has_many :variants through :stock_items`, `has_many :stock_movements through :stock_items`, `has_many :shipments`; validations: `kind presence`, `pickup_stock_policy inclusion`, `pickup_ready_in_minutes numericality`; `after_create :create_stock_items` when `propagate_all_variants?`; `whitelisted_ransackable_attributes`
- [x] T002 Factory `spree/core/lib/spree/testing_support/factories/stock_location_factory.rb` — default warehouse-kind; `pickup_enabled` trait; `inactive` trait

### Serializer

- [x] T003 Admin serializer `spree/api/app/serializers/spree/api/v3/admin/stock_location_serializer.rb` — `id` (sloc_…), `name`, `kind`, `active`, `default`, `pickup_enabled`, `pickup_stock_policy`, `pickup_ready_in_minutes`, `propagate_all_variants`, `address1`, `address2`, `city`, `state_id`, `country_id`, `zipcode`, `phone`, `deleted_at`, timestamps

### Controller

- [x] T004 `spree/api/app/controllers/spree/api/v3/admin/stock_locations_controller.rb` — full CRUD; `scope` includes soft-deleted via `with_deleted` for admin; `permitted_params`: all attributes above

### Specs

- [x] T005 `spree/core/spec/models/spree/stock_location_spec.rb` — `propagate_all_variants` callback; soft-delete preserves stock items; `pickup_stock_policy` inclusion validation; `Spree::UniqueName` scoping
- [x] T006 `spree/api/spec/integration/spree/api/v3/admin/stock_locations_spec.rb` — CRUD; soft-delete returns `deleted_at`; `kind` filter; Ransack filters

### Type Pipeline

- [x] T007 `bundle exec rake typelizer:generate` — `AdminStockLocation` type generated
- [x] T008 `cd packages/sdk && pnpm generate:zod`
- [x] T009 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T010 [US1] `packages/dashboard/src/routes/_authenticated/$storeId/settings/stock-locations.tsx` — `<ResourceTable>` with `kind` and `active` filters; create/edit `<Sheet>`; `kind` select from `KINDS`; `pickup_enabled` toggle; `pickup_stock_policy` select; `pickup_ready_in_minutes` input
- [x] T011 [US1] `packages/dashboard/src/hooks/use-stock-locations.ts` — TanStack Query wrappers for CRUD
- [x] T012 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.stockLocations.*`
- [x] T013 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [x] T014 `packages/dashboard/e2e/stock-locations.spec.ts` — create warehouse → set active → set pickup_enabled → soft-delete → verify excluded from active list
- [x] T015 Run `pnpm test:e2e` ✅

**Checkpoint**: all integration tests pass ✅; `pnpm typecheck && pnpm lint` pass ✅

---

## Phase 2: 6.0 — Activity Tab (PENDING)

Depends on `6.0-inventory-operations.md` typed stock movements.

- [ ] T016 Add Activity tab to `settings/stock-locations.tsx` detail view
- [ ] T017 Render typed stock movements scoped to location via `GET /admin/stock_locations/:id/stock_movements?q[kind_eq]=...`
- [ ] T018 Display `date · variant · qty before → after · kind · cause entity link` per movement row
- [ ] T019 Add i18n keys for activity tab labels

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No uniqueness enforcement on `default: true` at DB or model level | Low | Only one location should be default; multiple defaults cause unpredictable routing fallback. Add a model validation or uniqueness trigger if multiple defaults are observed in production |
| Activity tab (typed stock movement timeline per location) not yet built | Medium | Blocked on `6.0-inventory-operations.md` typed movement primitives — T016–T019 above |
