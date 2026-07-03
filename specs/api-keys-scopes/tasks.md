---

description: "Task list for API Keys & Scopes — fully shipped in 5.5; no dedicated E2E tests"
---

# Tasks: API Keys & Scopes

**Status**: Fully shipped in 5.5; no dedicated E2E tests

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core model | `spree/core/app/models/spree/api_key.rb` |
| Admin serializer | `spree/api/app/serializers/spree/api/v3/admin/api_key_serializer.rb` |
| Admin controller | `spree/api/app/controllers/spree/api/v3/admin/api_keys_controller.rb` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard route | `packages/dashboard/src/routes/_authenticated/$storeId/settings/api-keys.tsx` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core + API + SPA ✅

### Model

- [x] T001 `spree/core/app/models/spree/api_key.rb` — `has_prefix_id :key`; `KEY_TYPES = %w[publishable secret]`; `PREFIXES = { publishable: 'pk_', secret: 'sk_' }`; `TOKEN_LENGTH = 24`; `SCOPES = [...]` (29 scopes); `Spree::SingleStoreResource`; `acts_as_paranoid` (revoke = soft delete); `scopes` JSONB array with allowlist validation; token generation on create; token shown once (hashed after creation); `skip_scope_check` flag for `:current` action

### Serializer

- [x] T002 `spree/api/app/serializers/spree/api/v3/admin/api_key_serializer.rb` — `key_` prefix ID; `key_type`, `name`, `scopes` array, `token_prefix` (pk_/sk_ only — never full token after create), `revoked_at`, timestamps; `token` attribute present only in create response

### Controller

- [x] T003 `spree/api/app/controllers/spree/api/v3/admin/api_keys_controller.rb` — full CRUD + `revoke` action; scope amplification check: caller cannot grant scopes not in their own set; `current` action returns caller's own key metadata without requiring `read_api_keys` scope; store-scoped

### Specs

- [x] T004 `spree/core/spec/models/spree/api_key_spec.rb` — token generation; scope allowlist validation; `KEY_TYPES`; token prefix per type
- [x] T005 `spree/api/spec/integration/spree/api/v3/admin/api_keys_spec.rb` — CRUD; revoke; scope amplification rejection; current endpoint

### Type Pipeline

- [x] T006 `bundle exec rake typelizer:generate` — `AdminApiKey` type generated
- [x] T007 `cd packages/sdk && pnpm generate:zod`
- [x] T008 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T009 `packages/dashboard/src/routes/_authenticated/$storeId/settings/api-keys.tsx` — list keys, create dialog (scope picker with all 29 scopes grouped, token shown once in post-create dialog), revoke action, key type badge
- [x] T010 Add i18n keys under `admin.api_keys.*` and `admin.scopes.*` in all locale files

**Checkpoint**: full API key management with scope picker; token-once UX; scope amplification prevention ✅

---

## Phase 2: E2E Coverage (PENDING)

- [ ] T011 `packages/dashboard/e2e/api-keys.spec.ts` — create publishable key; create secret key with selected scopes; verify token shown once in dialog; revoke key; scope amplification rejection (attempt to add scope not on current key)
- [ ] T012 Run `pnpm test:e2e`

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No dedicated E2E tests | Medium | T011–T012; API key management is a security surface — E2E coverage validates the token-once UX works correctly |
| 29 scopes are hardcoded in `SCOPES` constant | Low | New features must add new scopes manually; no automated discovery from routes; acceptable at current scale |
