---

description: "Task list for Tax Rates & Categories — tax categories fully shipped; tax rates models-only; 6.0 TaxProvider replaces system"
---

# Tasks: Tax Rates & Categories

**Status**: Tax categories fully shipped; tax rates models-only (no v3 API, no SPA); 6.0 TaxProvider replaces system

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/settings/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Tax Categories — Core + API + SPA ✅

### Model

- [x] T001 `spree/core/app/models/spree/tax_category.rb` — `has_prefix_id :taxcat`; `acts_as_paranoid`; `self.default` class method; name, description, `is_default` boolean; uniqueness validation on name

### Tax Rate Model (models-only)

- [x] T002 `spree/core/app/models/spree/tax_rate.rb` — `has_prefix_id :tax`; `acts_as_paranoid`; `CalculatedAdjustments`; `AdjustmentSource`; `include Spree::Metafields`; `included_in_price` boolean; `show_rate_in_label` boolean; belongs_to zone, tax_category; `amount` percentage; calculator association

### Serializer

- [x] T003 `spree/api/app/serializers/spree/api/v3/admin/tax_category_serializer.rb` — `taxcat_` prefix ID; name, description, is_default, deleted_at, timestamps

### Controller

- [x] T004 `spree/api/app/controllers/spree/api/v3/admin/tax_categories_controller.rb` — full CRUD; store-scoped

### Specs

- [x] T005 `spree/core/spec/models/spree/tax_category_spec.rb` — `self.default`; name uniqueness; paranoid
- [x] T006 `spree/core/spec/models/spree/tax_rate_spec.rb` — `included_in_price` behavior; calculator delegation; zone association
- [x] T007 `spree/api/spec/integration/spree/api/v3/admin/tax_categories_spec.rb` — CRUD; default category

### Type Pipeline

- [x] T008 `bundle exec rake typelizer:generate` — `AdminTaxCategory` type generated
- [x] T009 `cd packages/sdk && pnpm generate:zod`
- [x] T010 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T011 `packages/dashboard/src/routes/_authenticated/$storeId/settings/tax-categories.tsx` — list, create, edit, delete; is_default toggle
- [x] T012 Add i18n keys under `admin.tax_categories.*` in all locale files

### E2E

- [x] T013 `packages/dashboard/e2e/tax-categories.spec.ts` — CRUD; set default; delete with confirmation
- [x] T014 Run `pnpm test:e2e` ✅

**Checkpoint**: Tax categories fully shipped with SPA + E2E; tax rates have model + tests only ✅

---

## Phase 2: Tax Rates — v3 API + SPA (PENDING / LOW PRIORITY)

Given that `6.0-tax-provider.md` replaces `TaxRate` + `Zone`, this phase may be skipped.

- [ ] T015 `spree/api/app/serializers/spree/api/v3/admin/tax_rate_serializer.rb` — `tax_` prefix ID; amount, included_in_price, zone_id, tax_category_id, calculator type/amount, timestamps
- [ ] T016 `spree/api/app/controllers/spree/api/v3/admin/tax_rates_controller.rb` — full CRUD; store-scoped
- [ ] T017 `spree/api/spec/integration/spree/api/v3/admin/tax_rates_spec.rb` — CRUD; calculator options
- [ ] T018 Type pipeline rerun after T015
- [ ] T019 `packages/dashboard/src/routes/_authenticated/$storeId/settings/tax-rates.tsx` — list, create/edit with zone picker + tax category picker + calculator selector (FlatRate, default)
- [ ] T020 `packages/dashboard/e2e/tax-rates.spec.ts` — CRUD; zone + category assignment

---

## Phase 3: 6.0 — TaxProvider (PENDING)

Per `6.0-tax-provider.md`:

- [ ] T021 `Spree::TaxProvider` STI base — per-market provider strategy replaces `TaxRate.adjust` + Calculator
- [ ] T022 `Spree::TaxRate` — drop `zone_id`; add direct `country_id` + `state_id` FKs
- [ ] T023 Drop `Spree::Zone` model (tax context only; DeliveryZone is a separate model in `6.0-fulfillment-and-delivery.md`)
- [ ] T024 Drop `Spree::Calculator` indirection from tax rates — rates store `amount` directly
- [ ] T025 Admin SPA: TaxProvider configuration per market

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No v3 Admin API for tax rates | High | T015–T020; legacy admin is the only way to manage rates in 5.x SPA stores — blocking for merchants |
| Zone management has no v3 API or SPA | High | Blocked by same gap; zones can only be managed in legacy admin |
| Phase 2 may be skipped in favor of 6.0 TaxProvider | Design | Decision needed: invest in Phase 2 or go direct to 6.0 TaxProvider |
