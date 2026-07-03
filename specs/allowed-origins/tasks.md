---

description: "Task list for Allowed Origins (CORS) — fully shipped"
---

# Tasks: Allowed Origins (CORS)

**Status**: Fully shipped

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core model | `spree/core/app/models/spree/allowed_origin.rb` |
| Admin controller | `spree/api/app/controllers/spree/api/v3/admin/allowed_origins_controller.rb` |
| Admin serializer | `spree/api/app/serializers/spree/api/v3/admin/allowed_origin_serializer.rb` |
| Dashboard route | `packages/dashboard/src/routes/_authenticated/$storeId/settings/allowed-origins.tsx` |
| Dashboard hook | `packages/dashboard/src/hooks/use-allowed-origins.ts` |
| E2E spec | `packages/dashboard/e2e/allowed-origins.spec.ts` |

---

## Phase 1: Core + API + SPA ✅

- [x] T001 `spree/core/app/models/spree/allowed_origin.rb` — `has_prefix_id :ao`; `include Spree::SingleStoreResource`; `origin` string NOT NULL; format validation (http/https, no path); `self.parse_origin(url)` → `{scheme, host, port}`; `matches?(url)` with loopback exemption
- [x] T002 `spree/api/app/serializers/spree/api/v3/admin/allowed_origin_serializer.rb` — `ao_` prefix; origin, timestamps
- [x] T003 `spree/api/app/controllers/spree/api/v3/admin/allowed_origins_controller.rb` — full CRUD; `current_store.allowed_origins` scope
- [x] T004 `packages/dashboard/src/routes/_authenticated/$storeId/settings/allowed-origins.tsx` — list + add/delete inline
- [x] T005 `packages/dashboard/src/hooks/use-allowed-origins.ts` — TanStack Query wrappers
- [x] T006 `packages/dashboard/src/tables/allowed-origins.tsx`
- [x] T007 Add i18n keys under `admin.allowed_origins.*` in all locale files
- [x] T008 `packages/dashboard/e2e/allowed-origins.spec.ts` — CRUD; invalid origin rejected

**Checkpoint**: full allowed origins management; validation; E2E ✅

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| CORS middleware wiring not visible in source | Medium | `AllowedOrigin.matches?` is the lookup interface; how Rack/Rails CORS middleware calls it is not documented in this model — verify in `config/initializers/` or middleware stack |
