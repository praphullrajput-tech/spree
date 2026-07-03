---

description: "Task list for Payment Methods — fully shipped; 6.0 join-table drop + display_on rename pending"
---

# Tasks: Payment Methods

**Status**: Phase 1 (core + API + SPA) fully shipped; Phase 2 (5.6 single-store migration) fully shipped; Phase 3 (6.0 cleanup) pending

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

## Phase 1: Core + API + SPA ✅

### Models

- [x] T001 `spree/core/app/models/spree/payment_method.rb` — `has_prefix_id :pm`; STI base on `type`; `include Spree::Metafields`; `include Spree::Metadata`; `include Spree::DisplayOn` (bridge to `storefront_visible`); `acts_as_list`; `active` boolean; preferences serialized as text; `preference_schema` computed method; `Spree.payment_methods` registry seeded in `config.after_initialize`
- [x] T002 `spree/core/app/models/spree/payment_method/check.rb` — no preferences; `name` default "Check"
- [x] T003 `spree/core/app/models/spree/payment_method/store_credit.rb` — redeems from `Spree::StoreCredit` balance; no external credentials

### Migrations

- [x] T004 `spree_payment_methods` table — `type`, `name`, `active`, `position`, `display_on`, `preferences text`, `deleted_at`, timestamps

### Serializers

- [x] T005 [P] `spree/api/app/serializers/spree/api/v3/admin/payment_method_serializer.rb` — `id` (pm_…), `name`, `type`, `active`, `position`, `storefront_visible`, `preference_schema`, `store_id`, `created_at`, `updated_at`, `deleted_at`

### Controllers

- [x] T006 `spree/api/app/controllers/spree/api/v3/admin/payment_methods_controller.rb` — full CRUD; `types` action returning `Spree.payment_methods` registry; `reposition` member action; scoped to `current_store`

### Routes

- [x] T007 Routes: `resources :payment_methods` with `member { post :reposition }` and `collection { get :types }`

### Specs

- [x] T008 `spree/core/spec/models/spree/payment_method_spec.rb` — `active` scope; `acts_as_list` position; registry registration; `preference_schema` returns field definitions
- [x] T009 `spree/api/spec/integration/spree/api/v3/admin/payment_methods_spec.rb` — CRUD; `types` action; store scoping; `storefront_visible` bridge

### Type Pipeline

- [x] T010 `bundle exec rake typelizer:generate` — `AdminPaymentMethod` type generated
- [x] T011 `cd packages/sdk && pnpm generate:zod`
- [x] T012 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T013 [US1/US2] `packages/dashboard/src/routes/_authenticated/$storeId/settings/payment-methods.tsx` — list + create/edit Sheet; drag-to-reorder (dnd-kit `verticalListSortingStrategy`); type `<Select>` from registry; dynamic preferences form from `preference_schema`
- [x] T014 `packages/dashboard/src/hooks/use-payment-methods.ts` — TanStack Query wrappers for CRUD + types + reposition
- [x] T015 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.paymentMethods.*`
- [x] T016 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [x] T017 `packages/dashboard/e2e/payment-methods.spec.ts` — create method → verify appears → reorder → verify position persists
- [x] T018 Run `pnpm test:e2e` ✅

**Checkpoint**: admin can create Check + StoreCredit methods; drag-to-reorder updates position; store scoping prevents cross-store access ✅

---

## Phase 2: 5.6 — Single-Store Migration ✅

Per `5.6-6.0-single-store-promotions-payment-methods.md`:

- [x] T019 Migration: add `store_id string` FK to `spree_payment_methods`; index `store_id`
- [x] T020 `include Spree::SingleStoreResource` on `Spree::PaymentMethod`
- [x] T021 `include Spree::LegacyMultiStoreSupport unless defined?(SpreeMultiStore)` — deprecation bridge for shared records
- [x] T022 Rake task: backfill `store_id` for existing payment methods; loud deprecation per record with multiple stores
- [x] T023 Remove `ResourceController`'s `store_ids=` seam from PaymentMethods admin
- [x] T024 `spree_payment_methods_stores` join table preserved (not yet dropped; multi-store sharing moves to `spree_multi_store` extension)

**Checkpoint**: each payment method belongs to exactly one store; multi-store records migrated with deprecation warnings ✅

---

## Phase 3: 6.0 Cleanup (PENDING)

- [ ] T025 Migration: drop `spree_payment_methods_stores` join table
- [ ] T026 Migration: add `null: false` constraint to `store_id` on `spree_payment_methods`
- [ ] T027 Remove `LegacyMultiStoreSupport` bridge from `Spree::PaymentMethod`
- [ ] T028 `display_on` column renamed to `storefront_visible` boolean per `5.5-6.0-display-on-to-boolean.md`
- [ ] T029 Remove `include Spree::DisplayOn` bridge; use `storefront_visible` column directly

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| `spree_payment_methods_stores` join table still present | Low | By design in 5.6; T025 drops it in 6.0 |
| `display_on` tri-state not yet renamed to boolean column | Low | Bridge in place via `Spree::DisplayOn`; T028 completes the rename in 6.0 |
| No per-method test for gateway-specific `preference_schema` | Low | External gateway extensions should test their own schemas; core tests cover the schema mechanism |
