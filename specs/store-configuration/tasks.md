---

description: "Task list for Store Configuration — fully shipped including SPA and E2E"
---

# Tasks: Store Configuration

**Status**: Fully shipped

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core model | `spree/core/app/models/spree/store.rb` |
| Store concerns | `spree/core/app/models/spree/stores/` |
| Admin serializer | `spree/api/app/serializers/spree/api/v3/admin/store_serializer.rb` |
| Admin controller | `spree/api/app/controllers/spree/api/v3/admin/store_controller.rb` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard route | `packages/dashboard/src/routes/_authenticated/$storeId/settings/store.tsx` |
| E2E spec | `packages/dashboard/e2e/store-settings.spec.ts` |

---

## Phase 1: Core + API + SPA ✅

### Model

- [x] T001 `spree/core/app/models/spree/store.rb` — `has_prefix_id :store`; `acts_as_paranoid`; `friendly_id :code`; `include TranslatableResource`; `include Spree::Metafields`; `include Spree::Metadata`; `include Stores::Setup`; `include Stores::Markets`; `include Stores::Channels`; `include UserManagement`; `include OrderRouting::HasStrategyPreference`; dedicated columns: `default_currency`, `default_locale`, `timezone`; `preferences` serialized column
- [x] T002 `spree/core/app/models/spree/stores/setup.rb` — name, URL, mail settings, logo, favicon
- [x] T003 `spree/core/app/models/spree/stores/markets.rb` — `supported_currencies`, `default_currency`; multi-currency configuration
- [x] T004 `spree/core/app/models/spree/stores/channels.rb` — default channel assignment; channel strategy preference

### Serializer

- [x] T005 `spree/api/app/serializers/spree/api/v3/admin/store_serializer.rb` — all store configuration fields; `store_` prefix ID; logo URL, social links, SEO fields, locale/currency/timezone, metafields, timestamps

### Controller

- [x] T006 `spree/api/app/controllers/spree/api/v3/admin/store_controller.rb` — `show` + `update` only (no index/create/destroy); scoped to `Spree::Current.store`

### Specs

- [x] T007 `spree/core/spec/models/spree/store_spec.rb` — preferences; `supported_currencies` validation; `default_locale` fallback
- [x] T008 `spree/api/spec/integration/spree/api/v3/admin/store_spec.rb` — show; update; 403 on update for non-admin

### Type Pipeline

- [x] T009 `bundle exec rake typelizer:generate`
- [x] T010 `cd packages/sdk && pnpm generate:zod`
- [x] T011 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T012 `packages/dashboard/src/routes/_authenticated/$storeId/settings/store.tsx` — store settings form: name, URL, mail from, timezone, currency, locales, logo upload, favicon upload, social links, SEO defaults
- [x] T013 Add i18n keys under `admin.store.*` and `admin.settings.*` in all locale files

### E2E

- [x] T014 `packages/dashboard/e2e/store-settings.spec.ts` — update name; update currency; update timezone; logo upload; save with validation error
- [x] T015 Run `pnpm test:e2e` ✅

**Checkpoint**: full store configuration via SPA with E2E coverage; no create/delete in API ✅

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No `POST /stores` in Admin API | By Design | Stores created via CLI only; multi-store management via `spree_multi_store` extension |
