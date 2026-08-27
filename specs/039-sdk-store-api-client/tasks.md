---
description: "Task list — brownfield migration of @spree/sdk — Store API Client (already implemented)"
---

# Tasks: @spree/sdk — Store API Client

**Input**: Design documents from `specs/039-sdk-store-api-client/`

**Note**: This feature is already fully implemented in the codebase. Every task below is marked `[x]` (done) and documents what was built and where, for spec-kit traceability purposes — not as a forward work plan.

**Organization**: Tasks are grouped by actual component (client construction, sdk-core dependency, resource groups, generated types/schemas, tests) rather than by user story, since implementation predates this spec-kit adoption.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Package scaffolding: `packages/sdk/package.json` — dual CJS/ESM build via Tsup, subpath exports (`.`, `./types`, `./zod`, `./webhooks`), peer deps on `typescript`/`zod` (both optional)
- [x] T002 Baseline frontend: `pnpm typecheck` (`tsc --noEmit`) and `pnpm lint` (Biome over `src tests`) pass at the package and workspace root
- [x] T003 Test tooling: Vitest configured for unit tests (`vitest run`) and a separate integration config (`vitest.integration.config.ts`) for live-API smoke tests; MSW for HTTP mocking in unit tests

**Checkpoint**: Package builds, typechecks, lints, and has a working test harness.

---

## Phase 2: Foundational (Shared Request Layer — `packages/sdk-core`)

- [x] T004 `[sdk-core]` `createRequestFn()` in `packages/sdk-core/src/request.ts` — builds the base request pipeline (base URL, auth header resolution, JSON body/response handling)
- [x] T005 `[sdk-core]` `SpreeError` class (`request.ts:40-52`) — typed error (`code: string`, `status: number`, `details?: Record<string, string[]>`) constructed from the API's `ErrorResponse` envelope
- [x] T006 `[sdk-core]` Auth header resolution — `X-Spree-API-Key` (publishable key, set at client construction) vs. `Authorization: Bearer <token>` (JWT, passed per-request via `options.token`, `request.ts:169`)
- [x] T007 `[sdk-core]` Retry/backoff — `resolveRetryConfig()` (`helpers.ts:22-33`, defaults: `maxRetries: 2`, `retryOnStatus: [429,500,502,503,504]`, `baseDelay: 300`, `maxDelay: 10000`, `retryOnNetworkError: true`) and `calculateDelay()` exponential backoff + jitter (`request.ts:60-64`); `retry: false` disables entirely
- [x] T008 `[sdk-core]` `transformListParams()` (`params.ts`) — converts SDK list params into the Ransack `q[...]` query-string shape the Store API expects
- [x] T009 `[sdk-core]` Shared types (`types.ts`) — `LocaleDefaults`, `ErrorResponse`, `ListParams`/`ListResponse`, `AddressParams`, `EmailPasswordLogin`, etc., re-exported from `packages/sdk-core/src/index.ts`

**Checkpoint**: Shared HTTP/retry/error/param-transform layer in place — both `@spree/sdk` and `@spree/admin-sdk` build on this.

---

## Phase 3: User Story 1 - Guest browse-to-purchase (Priority: P1) 🎯 MVP

**Goal**: Guest developer/storefront can list products/categories and drive a cart through checkout using only a publishable key.

**Independent Test**: `createClient({ baseUrl, publishableKey })` → `client.products.list()` → `client.carts.create()` → `client.carts.lineItems.create(...)` → address/delivery/payment calls, all succeeding without a JWT.

### Implementation for User Story 1

- [x] T010 `[US1]` `createClient(config: ClientConfig)` factory in `packages/sdk/src/client.ts` — resolves `baseUrl`, `publishableKey`, optional custom `fetch`, retry config, and `LocaleDefaults`; builds `requestFn` via `createRequestFn(requestConfig, '/api/v3/store', { headerName: 'x-spree-api-key', headerValue: config.publishableKey }, defaults)`
- [x] T011 `[US1]` `StoreClient` class in `packages/sdk/src/store-client.ts` (983 lines) — flat resource groups: `products`, `categories`, `carts` (+ nested `lineItems`), `orders`, `addresses`, `countries`, `currencies`, `markets`, `policies`
- [x] T012 `[US1]` `client.products.list/get/filters` — `filters` bypasses `transformListParams` (not a Ransack listing endpoint) and passes params through directly
- [x] T013 `[US1]` `client.request<T>(method, path, options)` — low-level escape hatch exposed on `StoreClient` for calling endpoints not yet wrapped by a typed method
- [x] T014 `[P]` `[US1]` Generated types for guest-flow resources: `packages/sdk/src/types/generated/{Cart,LineItem,Product,Category,Address,Country,Currency}.ts`
- [x] T015 `[P]` `[US1]` Tests: `packages/sdk/tests/{products,categories,cart,client,params}.test.ts` (MSW-mocked)

**Checkpoint**: Guest browse → cart → checkout flow fully functional and independently testable.

---

## Phase 4: User Story 2 - Authenticated customer account (Priority: P2)

**Goal**: Returning customer authenticates via JWT and manages account/order history.

**Independent Test**: `client.auth.login(credentials)` returns `AuthTokens`; `options.token` on `client.orders.list()`/`client.customer.get()` scopes to that customer; `client.auth.refresh`/`client.auth.logout` manage the token lifecycle.

### Implementation for User Story 2

- [x] T016 `[US2]` `client.auth.{login,refresh,logout}` in `store-client.ts` (`~L76-91`) — `refresh` needs no `Authorization` header (uses `refresh_token` in body per Store API convention); `logout` revokes the refresh token
- [x] T017 `[US2]` `client.customer`, `client.creditCards`, `client.storeCredits`, `client.giftCards`, `client.wishlists` (+ `wishlistItems`), `client.invitations`, `client.digitalLinks` — all accept `options.token` for JWT-authenticated calls (`store-client.ts:341,580,612-613,880`)
- [x] T018 `[US2]` `client.passwordResets` — `requestPasswordReset`/`resetPassword` flow, no auth required
- [x] T019 `[P]` `[US2]` Generated types: `packages/sdk/src/types/generated/{Customer,CreditCard,StoreCredit,GiftCard,GiftCardBatch,Wishlist,Invitation,DigitalLink,AuthTokens... (via Auth-related type exports)}.ts`
- [x] T020 `[P]` `[US2]` Tests: `packages/sdk/tests/{auth,customer,password-resets,wishlists}.test.ts`

**Checkpoint**: Authenticated customer flows (login, refresh, logout, account data) fully functional and independently testable.

---

## Phase 5: User Story 3 - Resilient network handling and typed errors (Priority: P3)

**Goal**: Automatic retry with backoff on transient failures; all API failures surface as typed `SpreeError`.

**Independent Test**: MSW mock returns `503` then `200` — SDK resolves without caller retry logic (`retry.test.ts`); MSW mock returns `422` with `error.details` — caller catches `SpreeError` with populated `code`/`status`/`details` (`error-handling.test.ts`).

### Implementation for User Story 3

- [x] T021 `[US3]` Retry loop wired into `createRequestFn()` — retries on configured statuses/network errors up to `maxRetries`, using `calculateDelay()` exponential backoff + jitter
- [x] T022 `[US3]` `SpreeError` thrown for every non-2xx response, replacing raw `Response`/generic `Error` rejects
- [x] T023 `[P]` `[US3]` Tests: `packages/sdk/tests/retry.test.ts`, `packages/sdk/tests/error-handling.test.ts`

**Checkpoint**: Retry/backoff and error-typing behavior verified independently of any specific resource.

---

## Phase 6: Payments, Markets, Webhooks (Supporting Resource Groups)

- [x] T024 `[P]` `client.payments`, `client.paymentSessions`, `client.paymentSetupSessions` — `CreatePaymentParams`, `CompletePaymentSessionParams`, `CompletePaymentSetupSessionParams` types; tests in `payments.test.ts`, `payment-sessions.test.ts`, `payment-setup-sessions.test.ts`
- [x] T025 `[P]` `client.markets` — `Market` resource; tests in `markets.test.ts`
- [x] T026 `[P]` `client.newsletterSubscribers` — `NewsletterSubscriber` resource; tests in `newsletter-subscribers.test.ts`
- [x] T027 `[P]` `packages/sdk/src/webhooks.ts` — webhook signature verification, separate `./webhooks` subpath export; tests in `webhooks.test.ts`

---

## Phase 7: Generated Types & Zod Pipeline

- [x] T028 `[spree/api → sdk]` `bundle exec rake typelizer:generate` (in `spree/api`) generates TypeScript types from Alba serializers into `packages/sdk/src/types/generated/`
- [x] T029 `[sdk]` `pnpm generate:zod` (`scripts/generate-zod.ts`) generates Zod schemas in `packages/sdk/src/zod/generated/` from the TS types
- [x] T030 Lefthook pre-commit hook (`lefthook.yml`) auto-regenerates types + Zod schemas when `spree/api/app/serializers/**/*.rb` changes and re-stages output — steps 3-5 of the pipeline (integration tests, OpenAPI regen, SDK tests) remain manual

**Checkpoint**: Generated output stays in sync with the Store API's Alba serializers by construction.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T031 `[P]` `packages/sdk/tests/setup.ts` — shared Vitest/MSW setup across all unit test files
- [x] T032 `[P]` `packages/sdk/tests/integration/` — live-API smoke tests via `vitest.integration.config.ts` / `pnpm test:integration`
- [x] T033 `[P]` `tsconfig.examples.json` + `examples:typecheck` script — typechecks README/example code snippets so documentation doesn't silently rot
- [x] T034 Full package suite: `cd packages/sdk && pnpm typecheck && pnpm lint && pnpm test` passes
- [x] T035 Changesets configured (`.changeset/` + `changeset`/`version`/`release` scripts) for independent package versioning

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2, `sdk-core`)**: Must precede all resource-group work — every `StoreClient` method routes through `createRequestFn`/`SpreeError`/retry/param-transform.
- **User Stories (Phases 3-5)**: Independently testable once Phase 2 is in place; in practice all three shipped together as one cohesive package.
- **Supporting resources (Phase 6)** and **generated pipeline (Phase 7)**: Layer on top of Phases 2-5; Phase 7 is a continuous, standing pipeline rather than a one-time task.
- **Polish (Phase 8)**: Cross-cutting, depends on all prior phases.

### Parallel Opportunities

- All `[P]`-marked generated-type and test-file tasks within a phase touch independent files and were (and can be) worked on in parallel.
- Phase 6's resource groups (payments, markets, newsletter subscribers, webhooks) are mutually independent.

## Notes

- This is a brownfield migration: all tasks are retrospective documentation of shipped code, not a forward implementation plan.
- Future additions to `@spree/sdk` (new Store API resources) should append new `[US#]`-tagged tasks under the relevant phase rather than rewriting this history.
