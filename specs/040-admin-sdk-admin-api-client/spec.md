# Feature Specification: @spree/admin-sdk — Admin API Client

**Feature Branch**: `040-admin-sdk-admin-api-client`

**Created**: 2026-08-25

**Status**: migrated

**Input**: User description: "@spree/admin-sdk — Admin API Client. Same patterns as @spree/sdk but for the Admin API. Supports both secret key (server-to-server) and JWT (admin SPA) authentication. Published under the `next` dist-tag during the Spree 6.0 Developer Preview."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Server-to-server integration with a secret key (Priority: P1)

A developer building an external app or integration (inventory sync, ERP bridge, reporting tool) needs to call the Spree Admin API from a backend service with no human user session. They create a client with a secret API key and call resource methods (`client.products.list()`, `client.orders.update()`) exactly as they would with the Store API client, without hand-rolling `fetch` calls or auth headers.

**Why this priority**: This is the primary reason `@spree/admin-sdk` exists — it is the only supported way for third-party apps to talk to the Admin API programmatically.

**Independent Test**: Instantiate `createAdminClient({ baseUrl, secretKey })` and call any resource method; verify the request carries `X-Spree-Api-Key` and returns typed, paginated data.

**Acceptance Scenarios**:

1. **Given** a valid secret key scoped for `read_products`, **When** the developer calls `client.products.list()`, **Then** the SDK sends `X-Spree-Api-Key` and returns a typed `PaginatedResponse<AdminProduct>`.
2. **Given** a secret key without the required write scope, **When** the developer calls a mutating method, **Then** the SDK surfaces the resulting 403 as a typed `SpreeError` (code, status, details) rather than throwing a raw fetch error.

---

### User Story 2 - Admin SPA session via JWT with automatic refresh (Priority: P1)

The `@spree/dashboard` React SPA itself is a consumer of this SDK: it authenticates a human admin user via JWT (short-lived access token in memory, refresh token in an httpOnly cookie) and needs the SDK to transparently retry a request once after a 401 by invoking an app-supplied refresh callback.

**Why this priority**: Equal priority to P1 above — the SDK underpins both the dashboard app itself and third-party integrations; the JWT path is what makes the dashboard's own auth flow (see `docs/plans/5.5-admin-auth-cookie-refresh.md`) work.

**Independent Test**: Create a client with `jwtToken` set, register `onUnauthorized`, force a 401, and verify the handler fires and the original request is retried exactly once on success.

**Acceptance Scenarios**:

1. **Given** a client configured with `jwtToken`, **When** a request returns 401 and `onUnauthorized` resolves `true`, **Then** the SDK retries the original request once with the (presumably refreshed) token.
2. **Given** the same setup but the 401 occurs on an `/auth/*` endpoint, **When** the request fails, **Then** the SDK does not invoke the unauthorized handler (avoids refresh loops on the auth endpoints themselves).
3. **Given** `onUnauthorized` resolves `false`, **When** a 401 occurs, **Then** the original `SpreeError` propagates to the caller.

---

### User Story 3 - Discoverable, typed resource surface generated from the API (Priority: P2)

A developer exploring the SDK in their editor expects autocomplete and types for every Admin API v3 resource (products, orders, customers, channels, custom fields, API keys, webhooks, etc.) without needing to read backend source, and expects those types to stay in sync with the actual API as it evolves.

**Why this priority**: Developer experience and long-term type accuracy differentiate a maintained SDK from a hand-rolled HTTP wrapper; drift between SDK types and the real API is the main failure mode for API clients.

**Independent Test**: Run `pnpm generate:admin-client` after an OpenAPI spec change and confirm `src/admin-client.ts` regenerates with the new/changed resource methods and parameter types, with no manual edits required.

**Acceptance Scenarios**:

1. **Given** `docs/api-reference/admin.yaml` defines a new endpoint, **When** `pnpm generate:admin-client` runs, **Then** `AdminClient` gains a corresponding namespaced method (e.g. `client.webhookEndpoints.create(...)`) with typed params.
2. **Given** an existing resource's serializer changes, **When** the type-generation pipeline runs (`typelizer:generate` → generated types consumed here), **Then** the admin-sdk's response types reflect the change without hand-editing generated files.

---

### Edge Cases

- What happens when both `secretKey` and `jwtToken` are supplied? The client config is silently exclusive (secret key wins) — no runtime validation error at construction time.
- How does the client behave when `storeId` changes mid-session (multi-store admin)? `setStore()` updates the `X-Spree-Store-Id` header for subsequent requests without recreating the client.
- What happens on a 401 loop (refreshed token also rejected)? The retry happens at most once per request; a second 401 propagates as `SpreeError` rather than looping.
- What happens when a preference/config field is a masked secret (e.g. payment method credentials) on read? `isMaskedSecret()` / `PREFERENCE_MASK_TOKEN` in `params.ts` let callers detect masked values and avoid re-submitting them unchanged.
- What happens across CORS boundaries for the refresh-token cookie? `credentials` defaults to `'include'` so the httpOnly refresh cookie flows on `/api/v3/admin/auth/*`; callers embedding the SDK in a context where cookies should not flow can override it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The SDK MUST provide a `createAdminClient(config)` factory returning a `Client` with namespaced resource methods for every Admin API v3 resource.
- **FR-002**: The SDK MUST support two mutually-exclusive auth modes per client: `secretKey` (sent as `X-Spree-Api-Key`) and `jwtToken` (sent as `Authorization: Bearer`).
- **FR-003**: The SDK MUST expose `setToken()`, `setStore()`, and `onUnauthorized()` on the returned client for session mutation without recreating the client.
- **FR-004**: The SDK MUST retry a request exactly once after a 401 when an `onUnauthorized` handler is registered and resolves `true`, except for requests to `/auth/*` paths.
- **FR-005**: The SDK MUST expose `X-Spree-Store-Id` header injection for multi-store admin routing via `setStore()`.
- **FR-006**: The resource client surface (`AdminClient` in `admin-client.ts`) MUST be generated from the Admin API's OpenAPI spec (`docs/api-reference/admin.yaml`) via `scripts/generate-admin-client.ts`, not hand-maintained.
- **FR-007**: Response and parameter types MUST be sourced from the shared Typelizer-generated types pipeline (consistent with `packages/sdk`), so serializer changes propagate without manual type edits.
- **FR-008**: The SDK MUST surface HTTP/validation errors as a typed `SpreeError` (code, status, details) rather than raw fetch rejections.
- **FR-009**: The SDK MUST default `credentials: 'include'` for admin auth/refresh cookie flows, overridable per client config.
- **FR-010**: The package MUST be published under the `next` dist-tag while in Developer Preview status, distinct from the stable `packages/sdk` release channel.

### Key Entities

- **Client / AdminClient**: The constructed SDK instance exposing every Admin API v3 resource as a namespaced sub-client (e.g. `client.products`, `client.customFields`, `client.apiKeys`).
- **AdminClientConfig**: Construction options — `baseUrl`, `secretKey`, `jwtToken`, `storeId`, `fetch`, `retry`, `credentials`.
- **AuthTokens / MeResponse / PermissionRule**: Shapes returned by the admin auth/`me` endpoints, consumed by the dashboard SPA to bootstrap a CanCanCan-derived permission model client-side.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/api` (Store/Admin API v3) | Yes | Source of truth: the OpenAPI spec (`docs/api-reference/admin.yaml`) and Typelizer-generated types this package's codegen consumes. No changes made *by* this feature; this feature depends on that spec staying current. |
| `packages/dashboard` (admin SPA) | Yes | Primary first-party consumer — all admin SPA API calls go through this package. |
| `packages/admin-sdk` | Yes | The package itself: `src/client.ts` (auth/session wrapper), `src/admin-client.ts` (generated resource surface), `src/params.ts` (generated + hand-written param types), `scripts/generate-admin-client.ts` (codegen), `tests/` (Vitest + MSW). |
| `packages/sdk-core` | Yes | Shared HTTP layer (`createRequestFn`, `SpreeError`, retry logic) this package builds on. |
| `docs/plans/` | No | Already covered by existing plans (`5.5-admin-auth-cookie-refresh.md`, `5.5-admin-api-key-scopes.md`); no new architectural change introduced by this migration entry. |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints**: None — this package is a client generated against existing/evolving Admin API v3 endpoints, not a source of new endpoints.
- **Serializer fields (read)**: Mirrors whatever `spree/api` Admin serializers expose; types are regenerated via the Typelizer pipeline, never hand-adjusted to diverge from the API.
- **Auth**: Dual mode — Admin API secret key + scopes (server-to-server integrations) **or** Admin JWT + CanCanCan (the admin SPA's own logged-in session). Both converge on the same generated resource methods; the SDK does not change behavior per resource based on auth mode, only the header it sends.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can authenticate and call any Admin API v3 resource in TypeScript, with full autocomplete, without reading `spree/api` backend source.
- **SC-002**: 401 responses during an active admin session are transparently recovered (refresh + one retry) without the caller writing retry logic.
- **SC-003**: Regenerating the client after an Admin API spec change requires zero manual edits to `admin-client.ts` or generated types.
- **SC-004**: All resource test suites in `packages/admin-sdk/tests/` (25+ resource areas: products, orders, customers, channels, custom fields, API keys, webhooks, etc.) pass against mocked responses (MSW).

## Assumptions

- The Admin API OpenAPI spec (`docs/api-reference/admin.yaml`) is kept current via the existing `rswag:specs:swaggerize` pipeline; this SDK's codegen trusts that spec as ground truth.
- Consumers embedding the secret-key mode are trusted server-to-server contexts; the SDK does not attempt to protect the secret key client-side (it must never ship to a browser bundle).
- The package remains in Developer Preview (`next` dist-tag, no stable semver guarantees) until explicitly promoted, per `CLAUDE.md`.
- `packages/dashboard`'s own auth flow (memory access token + httpOnly refresh cookie) is the reference JWT-mode integration; other JWT consumers are expected to follow the same `onUnauthorized`-driven refresh pattern.

## Migration Notes

- **Dual auth mode is structural, not incidental.** `AdminClientConfig` treats `secretKey` and `jwtToken` as mutually exclusive inputs (`client.ts` lines ~5–24): secret keys authenticate server-to-server apps/integrations via `X-Spree-Api-Key` and are authorized by scopes (`5.5-admin-api-key-scopes.md`); JWTs authenticate the logged-in human admin (including the `@spree/dashboard` SPA itself) via `Authorization: Bearer` and are authorized by CanCanCan abilities server-side. The SDK does not branch resource behavior on which mode is active — only the outgoing header changes — so this is invisible to most resource-method callers but load-bearing for `onUnauthorized`, which only makes sense in JWT mode (secret keys don't get refreshed).
- **The codegen script is the actual source of the resource surface.** `packages/admin-sdk/scripts/generate-admin-client.ts` reads `docs/api-reference/admin.yaml` (via a dependency-free inline YAML parser, since the script deliberately avoids adding a YAML library dependency) and writes `src/admin-client.ts`. This means `admin-client.ts` should be treated as generated output — same convention as `packages/sdk/src/types/generated/` — even though it isn't under a `generated/` directory. Hand-edits to `admin-client.ts` will be silently overwritten on the next `pnpm generate:admin-client` run.
- **"Developer Preview" status is a real constraint, not boilerplate.** Per `package.json` (`version: 0.5.0`) and root `CLAUDE.md`, this package is published under the `next` dist-tag, distinct from `packages/sdk`'s stable channel. Breaking changes are expected pre-1.0; any spec/plan referencing this package should not assume semver stability guarantees.
- **Gap identified**: no `docs/plans/` entry exists that specifically governs `packages/admin-sdk` as its own architectural surface (it is only referenced indirectly via `5.5-admin-auth-cookie-refresh.md` and `5.5-admin-api-key-scopes.md`, which govern the auth mechanisms it consumes, not the SDK package itself). If the SDK's resource-surface conventions (namespacing, codegen boundary, error typing) are ever changed structurally, that would qualify as a new `docs/plans/` entry per Constitution Principle VI.
- **Gap identified**: this spec is reverse-engineered from source; no original user-facing requirements doc or RFC was found for `packages/admin-sdk` distinct from the `packages/sdk` (Store API) design it mirrors.
