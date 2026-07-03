# Implementation Plan: API Keys & Scopes

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped in 5.5; no dedicated E2E tests

---

## Summary

`Spree::ApiKey` provides Shopify-style API key management for server-to-server integrations. Two key types: `publishable` (pk_…, Store API, read-only) and `secret` (sk_…, Admin API, scope-gated). 29 `read_*`/`write_*` scopes gate which Admin API endpoints a secret key can access. The controller includes a scope amplification check: a caller cannot grant scopes beyond their own. The `revoke` action soft-deletes the key. The Admin SPA has a full key management page.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Token storage** | Hashed; prefix (pk_/sk_) stored plain for display |
| **Scope** | Fully shipped (5.5) |

---

## Key Decisions

1. **Shopify-style `read_*`/`write_*` scopes.** Each scope follows the pattern `{read,write}_{resource}`. Write implies read for the same resource. 29 scopes cover all current Admin API resources. New resources add new scopes.

2. **Scope amplification prevention.** A caller (whether JWT admin or another secret key) cannot create a key with scopes they don't have. This is checked in the controller, not a model validator, because it requires knowledge of the caller's identity.

3. **Token shown once.** The full `sk_…` or `pk_…` token is only returned in the `create` response. Subsequent GETs return only the token prefix (for identification). This matches Stripe/Shopify behavior.

4. **`revoke` is a soft-delete.** The `revoke` action calls `key.destroy` (paranoid). A revoked key returns 401 on all subsequent requests. It can be inspected in the admin but not re-activated — create a new key instead.

5. **`skip_scope_check` for `:current`.** A key can inspect its own metadata (name, scopes, created_at) without the `read_api_keys` scope. This allows integration tooling to self-introspect.

6. **JSONB `scopes` array.** Scopes are stored as a JSONB array; validated against the `SCOPES` allowlist at the model level. The serializer returns the array; the controller accepts it on create/update.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Read/Write Symmetry**: `name`, `scopes` accepted on write; `token` returned once on create only
- [x] **Prefixed IDs**: `key_…` model ID; token prefixed `pk_…` or `sk_…`
- [x] **Serializer Hierarchy**: `Admin::ApiKeySerializer`
- [x] **Type Pipeline**: Typelizer + Zod regen done
- [x] **Security**: CanCanCan; scope amplification check; store-scoped
- [x] **Namespace**: `Spree::ApiKey`
- [x] **Plan Conflicts**: `5.5-admin-api-key-scopes.md` — fully shipped

---

## Project Structure

```text
# Backend — model (✅ shipped)
spree/core/app/models/spree/api_key.rb                              ← key_ prefix, KEY_TYPES, SCOPES (29), TOKEN_LENGTH

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/api_key_serializer.rb

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/api_keys_controller.rb  ← revoke action, scope amplification check

# Frontend (✅ shipped)
packages/dashboard/src/routes/_authenticated/$storeId/settings/api-keys.tsx
```

---

## Phase 1: Core + API + SPA (✅ Complete)

- `Spree::ApiKey` with KEY_TYPES, SCOPES, token generation
- Admin API: CRUD + revoke + current + scope amplification check
- Admin SPA: API keys settings page (31 KB — comprehensive scope picker)
- Shipped in 5.5

---

## Complexity Tracking

No significant violations — the scope system is a flat allowlist check, not a permission hierarchy.
