# Feature Specification: @spree/sdk-core — Shared HTTP Layer

**Feature Branch**: `041-sdk-core-shared-http-layer`

**Created**: 2026-08-24

**Status**: migrated

**Input**: Reverse-engineered from existing implementation at `packages/sdk-core/src/` as part of brownfield migration (`/speckit.brownfield.migrate`).

## User Scenarios & Testing *(mandatory)*

`@spree/sdk-core` is marked `"private": true` in its `package.json` — it is never installed directly by an end user or third-party integrator. Its only users are the maintainers of `@spree/sdk` (Store API client) and `@spree/admin-sdk` (Admin API client), who build request functions on top of it. The "user" in every story below is that internal developer.

### User Story 1 - Build a scope-bound request function with one call (Priority: P1)

A developer maintaining `@spree/sdk` or `@spree/admin-sdk` needs a `request()` function bound to their package's base path (`/api/v3/store` or `/api/v3/admin`) and auth header, without hand-rolling `fetch` plumbing, URL building, or header assembly in each SDK.

**Why this priority**: Without this, every resource client in both SDKs would duplicate fetch/header/URL logic — the entire reason the package exists.

**Independent Test**: Call `createRequestFn(config, basePath, auth, defaults)` and invoke the returned function with a method/path/options triple against a mocked `fetch`; assert the request URL, headers, and body match expectations.

**Acceptance Scenarios**:

1. **Given** a `RequestConfig` with `baseUrl` and a `fetchFn`, **When** `createRequestFn` is called with a `basePath` and `AuthConfig`, **Then** it returns a `RequestFn` that prefixes every call's `path` with `basePath` and injects the auth header on every request.
2. **Given** per-request `options.locale`/`currency`/`country`/`channel`, **When** a request is made, **Then** those values override the client-level `LocaleDefaults` and are sent as `x-spree-locale`/`x-spree-currency`/`x-spree-country`/`x-spree-channel` headers.
3. **Given** `options.token` or `options.spreeToken`, **When** a request is made, **Then** `Authorization: Bearer <token>` and/or `x-spree-token` headers are set respectively.

---

### User Story 2 - Get consistent, typed errors across both SDKs (Priority: P1)

A developer consuming either SDK (via an app built on `@spree/sdk`/`@spree/admin-sdk`) needs failed requests to surface as a single typed exception (`SpreeError`) with `code`, `status`, and field-level `details`, regardless of which SDK or endpoint made the call.

**Why this priority**: Consistent error shape is the contract both public SDKs promise their own consumers; it must originate from one place so Store and Admin SDKs never drift.

**Independent Test**: Mock `fetchFn` to return a non-2xx response with an `ErrorResponse` JSON body; assert the request function rejects with a `SpreeError` carrying the same `code`/`status`/`details`.

**Acceptance Scenarios**:

1. **Given** a non-OK response that is not retryable, **When** the request function processes it, **Then** it throws `SpreeError` constructed from the response body's `error.code`/`error.message`/`error.details` and the HTTP status.
2. **Given** a `204 No Content` or a bodiless `202 Accepted`, **When** the request function processes it, **Then** it resolves `undefined` instead of attempting to parse JSON.

---

### User Story 3 - Automatic, safe retries for transient failures (Priority: P2)

A developer building an SDK resource method wants transient network/server errors retried automatically (exponential backoff + jitter, `Retry-After` honored) without writing retry logic per call site, while never silently double-executing a non-idempotent mutation.

**Why this priority**: Reliability improvement layered on top of P1's request plumbing — SDKs function without it, but production traffic benefits from it.

**Independent Test**: Mock `fetchFn` to fail N times with a retryable status/network error then succeed; assert the request function retries up to `maxRetries`, delays following exponential-backoff-with-jitter (or `Retry-After` when present), and returns the eventual success.

**Acceptance Scenarios**:

1. **Given** a `GET`/`HEAD` request (or any request with an idempotency key) and a response in `retryOnStatus` (default `[429, 500, 502, 503, 504]`), **When** the request fails, **Then** it is retried up to `maxRetries` (default 2) with exponential backoff.
2. **Given** a mutating request (`POST`/`PUT`/`PATCH`/`DELETE`) with no caller-supplied idempotency key, **When** retries are enabled, **Then** the layer auto-generates a Stripe-style `Idempotency-Key` header so a retry is safe, and only retries such requests on `429`.
3. **Given** `retryConfig: false`, **When** any request fails, **Then** no retry is attempted regardless of status or error type.

---

### User Story 4 - Translate flat SDK list params into Ransack query params (Priority: P2)

A developer writing an SDK `.list()` method wants to accept flat, ergonomic filter params (`{ name_cont: 'foo' }`) and have them translated into the `q[...]` Ransack wire format the Rails backend expects, plus pass through pagination/expand/sort/fields untouched.

**Why this priority**: Keeps the public SDK surface flat and readable (per CLAUDE.md's "Flat request/response structure" convention) while still integrating with the backend's Ransack-based filtering.

**Independent Test**: Call `transformListParams({ page: 1, name_cont: 'foo', tag_id_in: [1, 2] })` and assert the output keys are `page`, `q[name_cont]`, and `q[tag_id_in][]`.

**Acceptance Scenarios**:

1. **Given** keys in `PASSTHROUGH_KEYS` (`page`, `limit`, `expand`, `sort`, `fields`), **When** transformed, **Then** they pass through unwrapped (arrays joined with commas).
2. **Given** an arbitrary scalar key, **When** transformed, **Then** it is wrapped as `q[key]`.
3. **Given** an arbitrary array-valued key, **When** transformed, **Then** it is wrapped as `q[key][]`.
4. **Given** a key already in `q[...]` form, **When** transformed, **Then** it passes through unchanged (backward compatibility).

---

### Edge Cases

- What happens when `baseUrl` is empty and there is no `window.location` (non-browser environment, e.g. SSR or Node)? The request function throws a `TypeError` rather than constructing an invalid URL.
- How does the system handle a retry loop exhausting `maxAttempts` without ever getting a `!response.ok` or throwing? The loop falls through to an explicit `throw new Error('Unexpected end of retry loop')` as a defensive unreachable-code guard.
- How does the retry delay behave when the server sends `Retry-After`? It is honored (converted from seconds to ms) and capped at `maxDelay`, taking precedence over the computed exponential-backoff delay.
- What happens for non-idempotent requests (no idempotency key) on a retryable 5xx? They are not retried — only `429` is retried for non-idempotent requests, and only becomes retryable at all if an idempotency key is present or the method is `GET`/`HEAD`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The package MUST export a `createRequestFn(config, basePath, auth, defaults?)` factory returning a `RequestFn` bound to a base path and auth header for one API scope (Store or Admin).
- **FR-002**: The returned `RequestFn` MUST build the request URL by joining `config.baseUrl` + `basePath` + call-site `path`, resolving against `window.location.origin` when `baseUrl` is empty and a `window` exists, and throwing otherwise.
- **FR-003**: The returned `RequestFn` MUST serialize `options.params` into URL query params, appending each array element as a repeated key.
- **FR-004**: The returned `RequestFn` MUST set `Content-Type: application/json`, the scope's auth header (`AuthConfig`), and conditionally `Authorization: Bearer <token>`, `x-spree-token`, `x-spree-locale`, `x-spree-currency`, `x-spree-country`, `x-spree-channel` based on options/defaults.
- **FR-005**: The package MUST export `SpreeError`, a typed `Error` subclass carrying `code`, `status`, and optional `details` parsed from the backend's `ErrorResponse` JSON shape.
- **FR-006**: The returned `RequestFn` MUST retry per a `RetryConfig` (`maxRetries`, `retryOnStatus`, `baseDelay`, `maxDelay`, `retryOnNetworkError`), using exponential backoff with jitter, honoring `Retry-After` when present, and MUST disable retries entirely when `retryConfig` is `false`.
- **FR-007**: The returned `RequestFn` MUST only retry non-idempotent (mutating) requests when they carry an idempotency key, and MUST auto-generate one (`spree-sdk-retry-<uuid>`) when retries are enabled and the caller supplied none.
- **FR-008**: The returned `RequestFn` MUST resolve `undefined` (not attempt JSON parsing) for `204 No Content` and for bodiless `202 Accepted` responses.
- **FR-009**: The package MUST export `transformListParams(params)`, converting flat filter keys to Ransack `q[...]` / `q[...][]` wire format while passing `page`/`limit`/`expand`/`sort`/`fields` through unwrapped (joining arrays with commas) and leaving already-wrapped `q[...]` keys untouched.
- **FR-010**: The package MUST export `getParams()` and `resolveRetryConfig()` helpers, and shared types (`ListParams`, `PaginatedResponse`, `ErrorResponse`, `LocaleDefaults`, `AddressParams`, `LoginCredentials`, etc.) consumed by both SDKs so response/param shapes stay identical across Store and Admin clients.
- **FR-011**: The package MUST remain `"private": true` and MUST NOT be published to a registry — it is an internal-only dependency of `@spree/sdk` and `@spree/admin-sdk` (both declare `"@spree/sdk-core": "workspace:*"`).

### Key Entities *(include if feature involves data)*

- **RequestConfig**: Per-client configuration — `baseUrl`, `fetchFn`, `retryConfig`, optional `credentials` (cross-origin cookie mode).
- **AuthConfig**: `headerName`/`headerValue` pair identifying the scope's API key header (`X-Spree-API-Key` for Store/Admin key auth).
- **RequestOptions / InternalRequestOptions**: Per-call overrides (token, spreeToken, locale, currency, country, channel, idempotencyKey, headers, body, params) layered over client-level `LocaleDefaults`.
- **SpreeError**: Typed error carrying `code`, `status`, `details` — the single error shape both SDKs surface to their own consumers.
- **RetryConfig / ResolvedRetryConfig**: Retry policy input and its defaults-applied resolved form.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | No | — |
| `spree/api` (Store/Admin API v3) | No | This package only speaks the API's existing v3 error/pagination contract, it does not change it |
| `packages/dashboard` (admin SPA) | No | Consumes `@spree/admin-sdk`, not this package directly |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Yes | Both declare `@spree/sdk-core: workspace:*` and build their `request()`/error/retry/list-param behavior on top of `createRequestFn`, `SpreeError`, `transformListParams` |
| `docs/plans/` | No | Internal shared-infrastructure package, not a user-facing architectural change; no active `docs/plans/` entry names it directly (it is referenced in CLAUDE.md's monorepo structure table and the constitution's Module Boundaries principle) |

### API Contract *(include if feature touches spree/api)*

Not applicable — `sdk-core` has no server-side surface. It mirrors the Store/Admin API v3's existing `ErrorResponse` (`{ error: { code, message, details } }`) and pagination (`PaginatedResponse`/`PaginationMeta`) shapes as TypeScript types, and translates SDK-level filter params into the Ransack query format the API already expects.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero fetch/header/URL-building/retry logic duplicated between `packages/sdk/src` and `packages/admin-sdk/src` — both call into `createRequestFn`.
- **SC-002**: Every non-2xx response from either SDK surfaces to the calling app as a `SpreeError` with the correct `code`/`status`/`details`, never a raw `fetch` rejection or unhandled JSON parse error.
- **SC-003**: Idempotent requests (`GET`/`HEAD`, or any request carrying an idempotency key) transparently recover from a transient `429`/`500`/`502`/`503`/`504` or network error within `maxRetries` attempts; non-idempotent requests without an idempotency key never retry on 5xx.
- **SC-004**: `packages/sdk/tests/retry.test.ts`, `packages/sdk/tests/params.test.ts`, and `packages/sdk/tests/error-handling.test.ts` pass, exercising this package's behavior indirectly through the public SDK.

## Assumptions

- The package is intentionally private (`"private": true` in `packages/sdk-core/package.json`) and has no external consumers beyond `@spree/sdk` and `@spree/admin-sdk` in this monorepo — "the user" throughout this spec is an internal SDK maintainer, not an end developer.
- No dedicated `packages/sdk-core/tests/` directory exists at the time of this migration; behavior is exercised indirectly via `packages/sdk/tests/*.test.ts` (`retry.test.ts`, `params.test.ts`, `error-handling.test.ts`, `client.test.ts`). This is a gap noted below, not a requirement to add tests as part of this migration.
- `crypto.randomUUID()` (used for auto-generated idempotency keys) is assumed available in every runtime the SDKs target (modern browsers, Node 18+, matching the package's `engines.node >= 18.0.0`).
