# Feature Specification: API Keys & Scopes

**Feature Branch**: `main` (fully shipped in 5.5; no dedicated E2E)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `5.5-admin-api-key-scopes.md`

---

## User Scenarios & Testing

### User Story 1 — Create an API Key (Priority: P1)

An admin creates a secret API key for server-to-server integration (e.g., an ERP, a mobile app backend, a third-party automation). The key is shown once at creation; it cannot be retrieved again.

**Why this priority**: Integrations require programmatic access; without API keys, all integrations must use cookie-based JWT (intended for human admin sessions, not automated systems).

**Independent Test**: Admin POSTs to `/api/v3/admin/api_keys` with `{ name: "ERP Integration", kind: "secret", scopes: ["read_orders", "write_orders"] }`. Response has `id: "key_…"` and the full `sk_…` token. Subsequent GETs return the key without the token (shown only once).

**Acceptance Scenarios**:

1. **Given** a new key request with `kind: secret`, **When** created, **Then** response includes `token: "sk_…"` (shown once only)
2. **Given** a new key request with `kind: publishable`, **When** created, **Then** `token: "pk_…"` is returned
3. **Given** a key with `scopes: ["read_orders"]`, **When** used to call `POST /admin/orders`, **Then** 403 is returned (missing write scope)
4. **Given** a key, **When** revoked, **Then** all subsequent requests with that token return 401

---

### User Story 2 — Scope Amplification Prevention (Priority: P1)

An admin cannot create a key with scopes that exceed their own permissions. This prevents privilege escalation via API keys.

**Acceptance Scenarios**:

1. **Given** an admin without `write_products` scope, **When** they try to create a key with `write_products`, **Then** 422 is returned
2. **Given** an admin with all scopes, **When** they create a key with any subset, **Then** the key is created successfully

---

### User Story 3 — List and Manage Keys (Priority: P2)

Admin lists all API keys for the current store, sees their scopes, creation date, and last-used date. Admin can revoke any key.

**Acceptance Scenarios**:

1. **Given** multiple keys, **When** listed, **Then** tokens are not returned (masked); only metadata shown
2. **Given** a key, **When** revoked, **Then** it is soft-deleted and no longer authenticates

---

### Edge Cases

- What if the token is lost? → Admin must revoke and create a new key; tokens are hashed and not retrievable
- What if a publishable key is used to call a write endpoint? → 401 (publishable keys are read-only by design)

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::ApiKey` prefix `key_`; `KEY_TYPES = %w[publishable secret]`; `PREFIXES = { publishable: "pk_", secret: "sk_" }`; `TOKEN_LENGTH = 24`
- **FR-002**: `SCOPES` — 29 Shopify-style scopes: `read_orders`, `write_orders`, `read_products`, `write_products`, `read_promotions`, `write_promotions`, `read_settings`, `write_settings`, `read_customers`, `write_customers`, `read_api_keys`, `write_api_keys`, `read_webhooks`, `write_webhooks`, and more
- **FR-003**: `scopes` stored as JSONB array column; validated against `SCOPES` allowlist
- **FR-004**: Token shown once at creation (returned in `create` response); not stored in plain text (hashed)
- **FR-005**: `revoke` member action — soft-deletes the key
- **FR-006**: Scope amplification check in controller: creating key with scopes beyond caller's own is rejected with 422
- **FR-007**: `skip_scope_check` for `:current` action (allows fetching current key's metadata)
- **FR-008**: Admin API: full CRUD + `revoke` + `current`

### Key Entities

- **ApiKey** (`Spree::ApiKey`): name, kind, scopes, token (hashed), store_id. Prefix: `key_` (token prefixed `pk_` or `sk_`).

---

## Backend Requirements

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/api_keys` | List keys (tokens masked) |
| POST | `/api/v3/admin/api_keys` | Create key (token shown once) |
| GET | `/api/v3/admin/api_keys/:id` | Show key metadata |
| PATCH | `/api/v3/admin/api_keys/:id` | Update name/scopes |
| DELETE | `/api/v3/admin/api_keys/:id` | Delete key |
| POST | `/api/v3/admin/api_keys/:id/revoke` | Revoke key |
| GET | `/api/v3/admin/api_keys/current` | Show current key's metadata |

### Serializer Fields

**Admin ApiKeySerializer**:
- `id` (key_…), `name`, `kind`, `scopes`, `store_id`, `last_used_at`, `created_at`, `updated_at`
- `token` — included only in `create` response (not on subsequent reads)

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/settings/api-keys.tsx` — list keys; create dialog with scope picker; revoke confirmation

### i18n Keys

Under `admin.apiKeys.*` in all locale files.

---

## Success Criteria

- **SC-001**: Admin can create a secret API key; token is shown once and cannot be retrieved again
- **SC-002**: Scope amplification prevention blocks privilege escalation
- **SC-003**: Revoked keys return 401 on all subsequent requests
- **SC-004**: Publishable keys authenticate Store API requests; secret keys authenticate Admin API requests

---

## Assumptions

- Tokens are stored hashed; only the prefix (pk_/sk_) is stored in plain text for display
- 29 scopes cover all resource types in the Admin API; new resources add new scopes
- Publishable keys always have read-only, store-facing scope — no `scopes` array needed
