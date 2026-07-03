# Implementation Plan: Allowed Origins (CORS)

**Branch**: `main` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped

---

## Summary

`Spree::AllowedOrigin` stores a per-store list of permitted HTTP origins for CORS. The model validates origin format, parses into components, and provides `matches?` for middleware lookup. The Admin API and SPA are fully shipped.

---

## Key Decisions

1. **Origins are stored as full strings and parsed on read.** `self.parse_origin(url)` breaks the origin into `{scheme, host, port}` for matching. Storing the raw string preserves the merchant's input and makes debugging easier than storing pre-parsed components.

2. **Loopback hosts are exempt from port-check.** `localhost`, `127.0.0.1`, `::1`, `0.0.0.0` are treated as loopback and port is not considered when matching. This prevents developers from having to add a new origin entry for every port they use locally.

3. **Validation rejects non-origin URLs.** Paths, query strings, and fragments are not allowed. `https://mystore.com` is valid; `https://mystore.com/shop` is not. This matches the browser's definition of an "origin".

4. **`SingleStoreResource`** — origins are fully store-scoped. One store cannot see or affect another store's CORS policy.

---

## Constitution Check

- [x] **Prefixed IDs**: `ao_`
- [x] **API-First**: Controller before SPA
- [x] **Security**: CanCanCan; `current_store.allowed_origins` scope
- [x] **Namespace**: `Spree::AllowedOrigin`

---

## Project Structure

```text
spree/core/app/models/spree/allowed_origin.rb
spree/api/app/controllers/spree/api/v3/admin/allowed_origins_controller.rb
spree/api/app/serializers/spree/api/v3/admin/allowed_origin_serializer.rb
packages/dashboard/src/routes/_authenticated/$storeId/settings/allowed-origins.tsx
packages/dashboard/src/hooks/use-allowed-origins.ts
packages/dashboard/src/tables/allowed-origins.tsx
packages/dashboard/e2e/allowed-origins.spec.ts
```

---

## Complexity Tracking

No significant violations — this is a simple allowlist CRUD feature.
