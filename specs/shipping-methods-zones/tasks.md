---

description: "Task list for Shipping Methods & Zones — models + legacy admin shipped; v3 API + SPA entirely pending; 6.0 rename pending"
---

# Tasks: Shipping Methods & Zones

**Status**: Phase 1 (models + legacy admin) fully shipped; Phase 2 (v3 API + SPA) entirely PENDING; Phase 3 (6.0 renames) PENDING

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Calculators | `spree/core/app/models/spree/calculator/shipping/` |
| Migrations | `spree/core/db/migrate/` |
| Legacy admin | `spree/admin/app/controllers/spree/admin/` + `spree/admin/app/views/spree/admin/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/settings/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Models + Legacy Admin ✅

### Models

- [x] T001 `spree/core/app/models/spree/shipping_method.rb` — `has_prefix_id :dm`; paranoid; `CalculatedAdjustments`; `include Spree::DisplayOn`; `acts_as_list`; `has_many :zones` via `ShippingMethodZone`; `has_many :shipping_categories` via `ShippingMethodCategory`; `has_many :shipping_rates`; `name`, `admin_name`, `code`, `tracking_url`, `tax_category_id`
- [x] T002 `spree/core/app/models/spree/shipping_category.rb` — `has_prefix_id :scat`; `name`; `has_many :shipping_method_categories`
- [x] T003 `spree/core/app/models/spree/shipping_method_category.rb` — `has_prefix_id :smcat`; join table; `belongs_to :shipping_method`, `belongs_to :shipping_category`
- [x] T004 `spree/core/app/models/spree/zone.rb` — `has_prefix_id :zone`; paranoid; `include Spree::UniqueName`; `default_tax boolean`; `zone_members_count`; `kind` (country/state); `has_many :zone_members`; `has_many :shipping_methods` via `ShippingMethodZone`
- [x] T005 `spree/core/app/models/spree/zone_member.rb` — polymorphic `zoneable` (Country or State); `belongs_to :zone`; counter_cache on zone
- [x] T006 `spree/core/app/models/spree/shipping_method_zone.rb` — join table; unique index on `(shipping_method_id, zone_id)`
- [x] T007 `spree/core/app/models/spree/shipping_rate.rb` — `has_prefix_id :dr`; `belongs_to :shipment`; `belongs_to :shipping_method`; `belongs_to :tax_rate` (optional); `cost decimal`; `selected boolean`; paranoid

### Calculators

- [x] T008 `spree/core/app/models/spree/calculator/shipping/flat_rate.rb`
- [x] T009 `spree/core/app/models/spree/calculator/shipping/per_item.rb`
- [x] T010 `spree/core/app/models/spree/calculator/shipping/flat_percent_item_total.rb`
- [x] T011 `spree/core/app/models/spree/calculator/shipping/flexi_rate.rb`
- [x] T012 `spree/core/app/models/spree/calculator/shipping/price_sack.rb`
- [x] T013 `spree/core/app/models/spree/calculator/shipping/digital_delivery.rb`

### Legacy Admin

- [x] T014 `spree/admin/app/controllers/spree/admin/shipping_methods_controller.rb` — CRUD with `load_data`, `set_default_values`, Turbo Stream support
- [x] T015 `spree/admin/app/controllers/spree/admin/zones_controller.rb` — CRUD with location_after_save, country/state picker, nested zone_members
- [x] T016 `spree/admin/app/views/spree/admin/shipping_methods/` — ERB form views (calculator picker, zone + category multi-select)
- [x] T017 `spree/admin/app/views/spree/admin/zones/` — ERB form views (country/state member picker)

**Checkpoint**: shipping methods and zones fully manageable via legacy Rails admin; checkout rate estimation uses `ShippingMethod` + calculators correctly ✅

---

## Phase 2: v3 API + SPA (PENDING)

### Serializers

- [ ] T018 [P] Create `spree/api/app/serializers/spree/api/v3/admin/shipping_method_serializer.rb` — `id` (dm_…), `name`, `admin_name`, `storefront_visible`, `code`, `tracking_url`, `calculator_type`, `calculator_preferences`, `zone_ids`, `shipping_category_ids`, `created_at`, `updated_at`, `deleted_at`
- [ ] T019 [P] Create `spree/api/app/serializers/spree/api/v3/admin/zone_serializer.rb` — `id` (zone_…), `name`, `description`, `default_tax`, `kind`, `members` (embedded: `[{ id, type, name }]`), `zone_members_count`, `created_at`, `updated_at`

### Controllers

- [ ] T020 [US1] Create `spree/api/app/controllers/spree/api/v3/admin/shipping_methods_controller.rb` — full CRUD; `scope` filtered to `current_store`; `collection_includes`: zones, shipping_categories, calculator
- [ ] T021 [US2] Create `spree/api/app/controllers/spree/api/v3/admin/zones_controller.rb` — full CRUD; `collection_includes`: zone_members

### Routes

- [ ] T022 Routes: `resources :shipping_methods` with `member { post :reposition }`; `resources :zones`

### Integration Specs

- [ ] T023 Write `spree/api/spec/integration/spree/api/v3/admin/shipping_methods_spec.rb` — CRUD; inactive method excluded from checkout rates; store scoping
- [ ] T024 Write `spree/api/spec/integration/spree/api/v3/admin/zones_spec.rb` — CRUD; zone members returned inline; default_tax update
- [ ] T025 Run `bundle exec rake rswag:specs:swaggerize`

### Type Pipeline

- [ ] T026 `bundle exec rake typelizer:generate` — `AdminShippingMethod`, `AdminZone` types generated
- [ ] T027 `cd packages/sdk && pnpm generate:zod`

### Frontend

- [ ] T028 [US1] Create `packages/dashboard/src/routes/_authenticated/$storeId/settings/shipping-methods.tsx` — list + create/edit Sheet; zone multi-select `<Combobox>`; shipping category multi-select; calculator type `<Select>` + dynamic preferences form; drag-to-reorder (same pattern as payment methods)
- [ ] T029 [US2] Create `packages/dashboard/src/routes/_authenticated/$storeId/settings/zones.tsx` — list + create/edit Sheet; country/state member picker; `default_tax` toggle
- [ ] T030 Create `packages/dashboard/src/hooks/use-shipping-methods.ts`
- [ ] T031 Create `packages/dashboard/src/hooks/use-zones.ts`
- [ ] T032 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.shippingMethods.*` and `admin.zones.*`
- [ ] T033 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [ ] T034 `packages/dashboard/e2e/shipping-methods.spec.ts` — create flat-rate method in domestic zone → verify appears → deactivate → verify removed from checkout
- [ ] T035 `packages/dashboard/e2e/zones.spec.ts` — create zone with country members → assign to shipping method → verify checkout eligibility

---

## Phase 3: 6.0 — Renames (PENDING)

Per `6.0-fulfillment-and-delivery.md` and `6.0-tax-provider.md`:

- [ ] T036 Rename `Spree::ShippingMethod` → `Spree::DeliveryMethod`; table `spree_shipping_methods` → `spree_delivery_methods`; constant alias for backward compat
- [ ] T037 Rename `Spree::Zone` (delivery context) → `Spree::DeliveryZone`; drop `default_tax` flag (tax zones handled by `Spree::TaxProvider`)
- [ ] T038 Rename `Spree::ShippingRate` → `Spree::DeliveryRate`
- [ ] T039 Drop `Spree::ShippingCategory` — delivery providers handle eligibility via `FulfillmentProvider` strategy
- [ ] T040 `display_on` column renamed to `storefront_visible` boolean per `5.5-6.0-display-on-to-boolean.md`
- [ ] T041 Update all serializers, controllers, and SPA hooks to use renamed models

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No v3 Admin API for shipping methods or zones | Critical | T018–T027 above; entire management surface is legacy Rails admin only |
| No Admin SPA for shipping method or zone management | Critical | T028–T035 above; merchants must use legacy admin |
| No E2E test coverage | High | T034–T035 above |
| `display_on` not yet bridged consistently (model has `Spree::DisplayOn` include) | Low | Bridge present; column rename deferred to 6.0 (T040) |
