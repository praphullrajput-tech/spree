---
status: migrated
---

# Spec: Allowed Origins (CORS)

**Feature**: Per-store allowlist of HTTP origins permitted to make cross-origin requests to the Store API

---

## Overview

`Spree::AllowedOrigin` stores the list of allowed origins for a store's CORS policy. Each record represents one HTTP origin (scheme + host + optional port). The model validates origin format (http/https only; no path/query/fragment), parses it into components, and provides a `matches?(url)` method. Loopback hosts are exempt from port-check strictness. The Admin SPA provides a settings page for managing the list.

---

## User Scenarios

### US1 — Merchant adds a storefront origin
Given the Settings → Allowed Origins page,
When the merchant adds `https://mystore.com`,
Then that origin is permitted to make cross-origin requests to `GET /api/v3/store/*` endpoints.

### US2 — Merchant adds a localhost development origin
Given a developer testing locally,
When the merchant adds `http://localhost:3000`,
Then loopback exemptions ensure the origin matches regardless of port matching rules.

### US3 — Merchant removes a stale origin
Given an origin `https://old.mystore.com` that is no longer in use,
When the merchant deletes it,
Then cross-origin requests from that origin are rejected.

### US4 — Invalid origin is rejected
Given a merchant entering `https://mystore.com/shop` (with a path),
When they submit,
Then the API returns a 422 with a validation error explaining origins must not include a path.

---

## Functional Requirements

### FR-001 — AllowedOrigin model
`Spree::AllowedOrigin` with prefix `ao_`. `include Spree::SingleStoreResource`. Columns: `origin` (string, NOT NULL), `store_id`. Validation: must be a valid HTTP(S) origin (no path except `/`, no query, no fragment). `self.parse_origin(url)` → `{ scheme, host, port }`. `matches?(url)` — returns true if scheme+host+port match, with loopback hosts (`localhost`, `127.0.0.1`, `::1`, `0.0.0.0`) exempt from port check.

### FR-002 — Admin API
`Admin::AllowedOriginsController` — full CRUD scoped to `current_store`. Permitted: `origin`. Serializer: `origin`, `store_id`, timestamps.

### FR-003 — Admin SPA
`settings/allowed-origins.tsx` — list with add/delete. Hooks: `use-allowed-origins.ts`. Table: `allowed-origins.tsx`. E2E: `allowed-origins.spec.ts`.

---

## Success Criteria

- [ ] `GET /api/v3/admin/allowed_origins` returns store-scoped list
- [ ] `POST` creates a new origin; validates format
- [ ] `DELETE` removes an origin
- [ ] SPA settings page lists, adds, and deletes origins
- [ ] `matches?('https://mystore.com')` returns true for matching origin

---

## Out of Scope

- CORS middleware wiring (how AllowedOrigin records are read by Rack/Rails CORS middleware is not part of this model's scope)
- Wildcard origins (`*.mystore.com` patterns)
