# Feature Specification: @spree/sdk — Store API Client

**Feature Branch**: `039-sdk-store-api-client`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — no original user description; behavior inferred from `packages/sdk/src/client.ts`, `packages/sdk/src/store-client.ts`, `packages/sdk/src/types/generated/`, `packages/sdk/src/zod/generated/`, `packages/sdk/tests/`, `packages/sdk-core/src/{request,helpers,params,types}.ts`, and `packages/sdk/package.json`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Third-party developer or storefront browses and purchases as a guest (Priority: P1)

A third-party developer (or the Next.js storefront) instantiates the SDK with a store's publishable key and base URL, then lists/searches products and categories, builds a cart as a guest, adds/updates/removes line items, and completes checkout (addresses, delivery, payment) without ever authenticating a customer.

**Why this priority**: This is the SDK's primary purpose — enabling headless storefronts to drive the full guest browse-to-purchase flow against the Store API v3.

**Independent Test**: `createClient({ baseUrl, publishableKey })`, call `client.products.list()` and `client.categories.list()`, then `client.carts.create()` → `client.carts.lineItems.create(...)` → `client.carts.update(...)` (addresses/delivery) → a payment flow — all succeed with only the publishable key, no JWT.

**Acceptance Scenarios**:

1. **Given** a valid `publishableKey` and `baseUrl`, **When** `client.products.list(params)` is called, **Then** a `PaginatedResponse<Product>` is returned with Ransack-style params transformed via `transformListParams`.
2. **Given** a guest with no cart yet, **When** `client.carts.create()` is called, **Then** a `Cart` is returned and subsequent guest cart operations are scoped via an `X-Spree-Token` guest cart token.
3. **Given** a cart with items and addresses set, **When** the developer proceeds through `paymentSessions`/`payments` endpoints, **Then** the cart transitions toward a completed `Order`.

---

### User Story 2 - Authenticated customer manages their account and order history (Priority: P2)

A returning customer logs in via `client.auth.login(credentials)`, receives a JWT access/refresh token pair, and the SDK attaches the token (via `Authorization: Bearer` or per-call `options.token`) to subsequent requests for orders, addresses, wishlists, credit cards, and store credits.

**Why this priority**: Distinguishes guest checkout from the full customer account experience — required for order history, saved payment methods, and repeat purchases.

**Independent Test**: `client.auth.login({ email, password })` returns `AuthTokens`; passing the resulting token via `options.token` on `client.orders.list()` / `client.customer.get()` returns only that customer's records; `client.auth.refresh({ refresh_token })` rotates the token; `client.auth.logout({ refresh_token })` revokes it.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** `client.auth.login()` is called, **Then** an `AuthTokens` object (access + refresh JWT) is returned.
2. **Given** an expired access token, **When** `client.auth.refresh({ refresh_token })` is called, **Then** a new access JWT and rotated refresh token are returned without re-entering credentials.
3. **Given** a guest cart later linked to a customer, **When** a JWT is passed alongside the guest token, **Then** the guest cart/order is associated with the authenticated customer.

---

### User Story 3 - Resilient network handling and typed error responses (Priority: P3)

The SDK automatically retries transient failures (429/5xx and network errors) with exponential backoff + jitter, and surfaces API failures as a typed `SpreeError` (code, status, field-level `details`) instead of raw fetch rejections, so the consuming app can branch on error shape.

**Why this priority**: Reliability and predictable error handling are cross-cutting requirements for any production storefront integration, not a standalone user journey, but critical to the SDK being production-usable.

**Independent Test**: Mock a `503` response once then a `200` — the SDK returns the eventual success without the caller retrying manually (`retry.test.ts`); mock a `422` with an `error.details` payload — the caller catches a `SpreeError` with `.code`, `.status`, `.details` populated (`error-handling.test.ts`).

**Acceptance Scenarios**:

1. **Given** a request that fails with a retryable status (`429, 500, 502, 503, 504`) or a network error, **When** retry is enabled (default), **Then** the SDK retries up to `maxRetries` (default 2) with exponential backoff (`baseDelay` default 300ms, capped at `maxDelay` default 10000ms) plus jitter.
2. **Given** `retry: false` in `ClientConfig`, **When** a retryable failure occurs, **Then** no retry happens and the error propagates immediately.
3. **Given** a non-2xx JSON error response, **When** the request resolves, **Then** the SDK throws a `SpreeError` with `code`, `status`, and optional `details: Record<string, string[]>` populated from the API's error envelope.

---

### Edge Cases

- What happens when `publishableKey` is invalid or revoked? The Store API returns an auth error; the SDK surfaces it as a `SpreeError` rather than throwing a generic fetch error.
- How does the system handle a guest cart token (`X-Spree-Token`) that has expired or belongs to a different store? Requests scoped to that cart fail with a `SpreeError`; the caller must create a new cart.
- What happens when `client.setLocale`/`setCurrency`/`setCountry`/`setChannel` are called mid-session? Subsequent requests pick up the new default via the shared `LocaleDefaults` object; in-flight requests are unaffected.
- How are list params (Ransack `q[...]` style filters) transformed for endpoints that don't accept them (e.g. `products.filters`)? `products.filters` passes `params` through directly instead of `transformListParams`, since it is not a Ransack-backed listing endpoint.
- What happens when both a custom `fetch` implementation and retry are configured together? The custom `fetch` is used for every attempt, including retries.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The SDK MUST expose a `createClient(config: ClientConfig)` factory returning a flat client where every Store API resource is a top-level property (`client.products`, `client.carts`, `client.orders`, etc.) — no nested namespace ceremony.
- **FR-002**: The SDK MUST support two auth modes: publishable-key (guest, `X-Spree-API-Key` header, set once at `createClient` time) and JWT (per-request `options.token`, sent as `Authorization: Bearer <token>`).
- **FR-003**: The SDK MUST support guest cart continuity via an `X-Spree-Token` guest cart token, independent of JWT auth.
- **FR-004**: The SDK MUST provide `client.auth.login`, `client.auth.refresh`, and `client.auth.logout` for JWT lifecycle management, matching the Store API's refresh-token rotation model.
- **FR-005**: The SDK MUST retry idempotent requests on configurable retryable HTTP statuses and network errors, with exponential backoff + jitter, and MUST allow retry to be fully disabled via `retry: false`.
- **FR-006**: The SDK MUST surface all non-2xx API responses as a typed `SpreeError` (`code: string`, `status: number`, `details?: Record<string, string[]>`), never a raw `Response` or generic `Error`.
- **FR-007**: The SDK MUST support store-level defaults (`locale`, `currency`, `country`, `channel`) settable at construction time and mutable afterward via `setLocale`/`setCurrency`/`setCountry`/`setChannel`, applied to every subsequent request.
- **FR-008**: The SDK MUST expose a low-level escape hatch (`client.request<T>(method, path, options)`) for calling endpoints not yet wrapped by a typed resource method, using the same auth/retry/base-URL plumbing.
- **FR-009**: The SDK MUST accept a caller-supplied `fetch` implementation (for non-browser runtimes / testing) instead of hardcoding `global.fetch`.
- **FR-010**: The SDK's list-returning methods MUST transform Ransack-style filter/sort/pagination params (`transformListParams`) into the query-string shape the Store API expects.
- **FR-011**: Generated TypeScript types (`src/types/generated/`) and Zod schemas (`src/zod/generated/`) MUST stay in sync with the Store API's Alba serializers via the type-generation pipeline (not hand-edited).

### Key Entities *(include if feature involves data)*

- **Client / ClientConfig**: The SDK entry point — holds `baseUrl`, `publishableKey`, optional custom `fetch`, `retry` config, and locale/currency/country/channel defaults; produces a `Client` exposing every Store resource plus the four `set*` mutators.
- **RequestFn / RequestConfig (sdk-core)**: Shared low-level request builder — resolves headers (API key or Bearer JWT), applies `LocaleDefaults`, executes retries, and throws `SpreeError` on failure. Shared by `@spree/sdk` and `@spree/admin-sdk`.
- **SpreeError**: Typed error class (`code`, `status`, `details`) constructed from the Store API's JSON error envelope (`ErrorResponse`).
- **AuthTokens**: Access + refresh JWT pair returned by `login`/`refresh`, consumed by the caller and passed back via `options.token` on subsequent authenticated calls.
- **Generated types/Zod schemas**: One TS interface + one Zod schema per Store API resource (`Product`, `Cart`, `Order`, `Customer`, `Wishlist`, `GiftCard`, `Payment`, etc.), regenerated from Alba serializers — never hand-written.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/api` (Store API v3) | No | SDK is a pure consumer; serializer changes there trigger regeneration here, but this feature doesn't modify the API |
| `packages/sdk` | Yes | `createClient`, `StoreClient` resource methods, generated types/Zod schemas, Vitest suite |
| `packages/sdk-core` | Yes (dependency) | Shared `createRequestFn`, `SpreeError`, retry/backoff logic, Ransack param transform — consumed, not owned by this feature, but load-bearing |
| `packages/admin-sdk` | No | Separate package; shares `sdk-core` but has its own client/resource surface |
| `packages/dashboard` / `dashboard-ui` / `dashboard-core` | No | Admin SPA uses `@spree/admin-sdk`, not `@spree/sdk` |
| `docs/plans/` | No | No active `docs/plans/` entry governs `@spree/sdk` specifically; it is the implementation vehicle for whatever Store API surface the referenced plans (`6.0-admin-api.md`, `5.4-store-api-naming-standardization.md`, etc.) expose |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints**: None — `packages/sdk` tracks whatever `/api/v3/store/*` endpoints exist; it does not define them.
- **Serializer fields (read)**: Mirrors Alba serializer output 1:1 via generated types in `packages/sdk/src/types/generated/` (one file per resource, e.g. `Product.ts`, `Cart.ts`, `Order.ts`).
- **Auth**: Store API publishable key (`X-Spree-API-Key`, guest default) or customer JWT (`Authorization: Bearer`, opt-in per request via `options.token`); guest carts additionally use `X-Spree-Token`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can go from `createClient()` to a completed guest checkout (products → cart → addresses → payment) using only documented resource methods, with no raw `fetch` calls required.
- **SC-002**: 100% of non-2xx Store API responses surface to the caller as `SpreeError` with `code`/`status` populated (verified by `tests/error-handling.test.ts`).
- **SC-003**: Transient failures (429/5xx/network) are retried and resolved without caller-side retry logic in the common case (verified by `tests/retry.test.ts`).
- **SC-004**: Generated types/Zod schemas in `src/types/generated/` and `src/zod/generated/` never drift from the live Store API serializers, enforced by the Lefthook pre-commit regeneration + the manual `pnpm generate:zod` step in the type-generation pipeline.

## Assumptions

- Consumers are either third-party developers integrating a headless storefront, or the official Next.js storefront reference implementation — not the admin dashboard (which uses `@spree/admin-sdk` instead).
- `packages/sdk-core`'s request/retry/error primitives are treated as a stable dependency of this feature, not something this spec re-derives requirements for (it has its own implicit contract shared with `@spree/admin-sdk`).
- Node.js `>=18` (native `fetch`) or a browser runtime; older runtimes must supply a `fetch` polyfill via `ClientConfig.fetch`.
- The SDK does not itself enforce CORS, rate limiting, or store-level feature flags — those are Store API concerns; the SDK's job is faithfully calling the API and typing the response.
