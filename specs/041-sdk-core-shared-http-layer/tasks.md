---

description: "Task list template for feature implementation"
---

# Tasks: @spree/sdk-core — Shared HTTP Layer

**Input**: Design documents from `specs/041-sdk-core-shared-http-layer/`

**Prerequisites**: plan.md, spec.md

**Note**: This is a reverse-engineered (brownfield) task list. The feature is already fully implemented and shipped; every task below documents completed work discovered in `packages/sdk-core/src/`, not planned work. All tasks are checked off.

**Tests**: Existing coverage is indirect, via the consuming `packages/sdk` package's Vitest suite — see US2/US3/US4 test tasks below.

**Organization**: Tasks are grouped by user story from spec.md.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the touched module builds/tests cleanly

- [x] T001 [P] `packages/sdk-core` builds cleanly: `cd packages/sdk-core && pnpm build` (tsup, dual CJS/ESM output)
- [x] T002 [P] `packages/sdk-core` typechecks: `cd packages/sdk-core && pnpm typecheck`
- [x] T003 [P] `packages/sdk-core` lints clean: `cd packages/sdk-core && pnpm lint` (Biome, extends root `biome.json`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core shared types and config surfaces that every user story builds on

- [x] T004 [packages/sdk-core] Define shared response/param types in `packages/sdk-core/src/types.ts` (`LocaleDefaults`, `PaginationMeta`, `ListResponse`, `PaginatedResponse`, `ErrorResponse`, `ListParams`, `AddressParams`, `EmailPasswordLogin`/`ProviderLogin`/`LoginCredentials`)
- [x] T005 [packages/sdk-core] Define request-layer config types in `packages/sdk-core/src/request.ts` (`RetryConfig`, `RequestOptions`, `InternalRequestOptions`, `RequestConfig`, `AuthConfig`, `RequestFn`)
- [x] T006 [packages/sdk-core] Publish the public barrel in `packages/sdk-core/src/index.ts` re-exporting `createRequestFn`, `SpreeError`, `transformListParams`, `getParams`, `resolveRetryConfig`, and all shared types
- [x] T007 [packages/sdk-core] Wire `package.json` as private (`"private": true`), dual CJS/ESM `exports` map, zero runtime dependencies, `tsup`-based build

**Checkpoint**: Foundation in place — user story work below builds directly on these types/exports.

---

## Phase 3: User Story 1 - Build a scope-bound request function with one call (Priority: P1) 🎯 MVP

**Goal**: A bound `RequestFn` per API scope (Store/Admin) with URL/header assembly handled centrally.

**Independent Test**: `createRequestFn(config, basePath, auth, defaults)` invoked against a mocked `fetch`; assert URL/headers/body.

### Implementation for User Story 1

- [x] T008 [US1] `createRequestFn()` factory in `packages/sdk-core/src/request.ts` (L115) returning a `RequestFn` bound to `basePath` + `AuthConfig`
- [x] T009 [US1] URL building with `basePath` + call-site `path` concatenation and browser-origin fallback (`packages/sdk-core/src/request.ts` L134-L144), throwing `TypeError` when neither `baseUrl` nor `window.location` is available
- [x] T010 [US1] Query-param serialization from `options.params`, including repeated-key array encoding (`packages/sdk-core/src/request.ts` L145-L157)
- [x] T011 [US1] Header assembly: `Content-Type`, scope auth header, `Authorization: Bearer`, `x-spree-token`, `x-spree-locale`, `x-spree-currency`, `x-spree-country`, `x-spree-channel`, with per-request overrides of client-level `LocaleDefaults` (`packages/sdk-core/src/request.ts` L129-L190)
- [x] T012 [US1] Consumers wired in `packages/sdk/src/client.ts` and `packages/admin-sdk/src/` — both call `createRequestFn` rather than re-implementing fetch plumbing

**Checkpoint**: US1 fully implemented and consumed by both SDKs.

---

## Phase 4: User Story 2 - Get consistent, typed errors across both SDKs (Priority: P1)

**Goal**: One typed `SpreeError` shape for every non-2xx response from either SDK.

**Independent Test**: Mock a non-2xx JSON error response; assert rejection is a `SpreeError` with matching `code`/`status`/`details`.

### Tests for User Story 2

- [x] T013 [P] [US2] Vitest coverage in `packages/sdk/tests/error-handling.test.ts` (exercises `SpreeError` behavior indirectly through `@spree/sdk`)

### Implementation for User Story 2

- [x] T014 [US2] `SpreeError` class in `packages/sdk-core/src/request.ts` (L40) — `code`, `status`, `details` constructed from `ErrorResponse`
- [x] T015 [US2] Non-OK, non-retryable response handling: parse `ErrorResponse` body and throw `SpreeError` (`packages/sdk-core/src/request.ts` L230-L231)
- [x] T016 [US2] `204`/bodiless-`202` short-circuit to `undefined` instead of JSON parsing (`packages/sdk-core/src/request.ts` L234-L246)
- [x] T017 [US2] `SpreeError` re-exported from `packages/sdk-core/src/index.ts` for both consuming SDKs to catch/re-throw uniformly

**Checkpoint**: US2 fully implemented; error shape identical across `@spree/sdk` and `@spree/admin-sdk`.

---

## Phase 5: User Story 3 - Automatic, safe retries for transient failures (Priority: P2)

**Goal**: Exponential-backoff retry with idempotency-safety, `Retry-After` support, opt-out via `retryConfig: false`.

**Independent Test**: Mock `fetchFn` failing N times then succeeding; assert retry count, backoff, and final success.

### Tests for User Story 3

- [x] T018 [P] [US3] Vitest coverage in `packages/sdk/tests/retry.test.ts`

### Implementation for User Story 3

- [x] T019 [US3] `resolveRetryConfig()` defaults (`maxRetries: 2`, `retryOnStatus: [429,500,502,503,504]`, `baseDelay: 300`, `maxDelay: 10000`, `retryOnNetworkError: true`) in `packages/sdk-core/src/helpers.ts` (L22-L33)
- [x] T020 [US3] `calculateDelay()` exponential backoff + jitter, capped at `maxDelay` (`packages/sdk-core/src/request.ts` L60-L64)
- [x] T021 [US3] `generateIdempotencyKey()` (`spree-sdk-retry-<uuid>`) auto-generated for mutating requests when retries enabled and caller supplied none (`packages/sdk-core/src/request.ts` L70-L72, L195-L196)
- [x] T022 [US3] `shouldRetryOnStatus()` / `shouldRetryOnNetworkError()` idempotency-aware retry gating — only `429` retried for non-idempotent requests without an idempotency key (`packages/sdk-core/src/request.ts` L74-L94)
- [x] T023 [US3] `Retry-After` header honored (capped at `maxDelay`) ahead of computed backoff delay (`packages/sdk-core/src/request.ts` L222-L225)
- [x] T024 [US3] `retryConfig: false` fully disables retry attempts (checked at every retry decision point in `packages/sdk-core/src/request.ts`)

**Checkpoint**: US3 fully implemented; retry semantics identical across both SDKs.

---

## Phase 6: User Story 4 - Translate flat SDK list params into Ransack query params (Priority: P2)

**Goal**: `transformListParams()` converts flat filter keys to `q[...]` wire format; pagination/expand/sort/fields pass through.

**Independent Test**: `transformListParams({ page: 1, name_cont: 'foo', tag_id_in: [1,2] })` → `{ page: 1, 'q[name_cont]': 'foo', 'q[tag_id_in][]': [1,2] }`.

### Tests for User Story 4

- [x] T025 [P] [US4] Vitest coverage in `packages/sdk/tests/params.test.ts`

### Implementation for User Story 4

- [x] T026 [US4] `PASSTHROUGH_KEYS` set (`page`, `limit`, `expand`, `sort`, `fields`) with array-join passthrough in `packages/sdk-core/src/params.ts` (L4, L21-L27)
- [x] T027 [US4] Backward-compat passthrough for already-`q[...]`-wrapped keys (`packages/sdk-core/src/params.ts` L30-L33)
- [x] T028 [US4] Scalar → `q[key]` and array → `q[key][]` wrapping (`packages/sdk-core/src/params.ts` L36-L41)
- [x] T029 [US4] `getParams()` helper for `expand`/`fields` comma-join serialization in `packages/sdk-core/src/helpers.ts` (L2-L11)
- [x] T030 [US4] `transformListParams` and `getParams` re-exported from `packages/sdk-core/src/index.ts` for use by both SDKs' `.list()` methods

**Checkpoint**: All four user stories implemented and in production use by `@spree/sdk` and `@spree/admin-sdk`.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T031 Package documented in root `CLAUDE.md` monorepo structure table and referenced in the spec-kit constitution's Module Boundaries principle (Principle I)
- [ ] T032 [Gap] No dedicated `packages/sdk-core/tests/` suite exists — coverage is indirect via `packages/sdk/tests/`. Not blocking (constitution Principle IV pragmatism), but a candidate for a future hardening pass if `sdk-core` gains logic not already exercised transitively.
- [ ] T033 [Gap] No `docs/plans/` entry names `sdk-core` directly — it is documented only via CLAUDE.md's structure table and the constitution. Acceptable per constitution Principle VI (no new architectural change here), but a future contract change to this package (e.g. `SpreeError` shape) should evaluate whether it now qualifies.

---

## Dependencies & Execution Order

All phases above are already complete (brownfield migration — this file is a historical record, not a forward plan). T032/T033 are open gap-tracking items, not blockers.
