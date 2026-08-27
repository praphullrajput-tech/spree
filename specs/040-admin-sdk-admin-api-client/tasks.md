---

description: "Task list for @spree/admin-sdk — Admin API Client (brownfield migration, already implemented)"
---

# Tasks: @spree/admin-sdk — Admin API Client

**Input**: Design documents from `/specs/040-admin-sdk-admin-api-client/`

**Prerequisites**: plan.md, spec.md

**Tests**: Included — the shipped package already has a full Vitest + MSW suite; tasks below document what exists rather than prescribing new test-first work.

**Organization**: Tasks are grouped by user story (spec.md P1/P1/P2), reflecting the as-built package. All tasks are marked complete — this is a reverse-engineered record of already-shipped work, not a forward plan.

## Path Conventions

- Package root: `packages/admin-sdk/`
- Codegen input: `docs/api-reference/admin.yaml` (owned by `spree/api`'s rswag pipeline, not this package)
- Shared HTTP layer: `packages/sdk-core/`
- Consumer: `packages/dashboard/src/hooks/`

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Scaffold `packages/admin-sdk` as a workspace package (`package.json`, `tsup` build, `tsconfig.json` + `tsconfig.examples.json`, Biome config extending root)
- [x] T002 [P] Depend on `packages/sdk-core` (workspace:*) for `createRequestFn`, `SpreeError`, `resolveRetryConfig`, shared request types
- [x] T003 [P] Wire Vitest + MSW test runner (`vitest run --passWithNoTests`, `msw` devDependency) matching `packages/sdk`'s test conventions

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 Implement `createAdminClient(config)` in `packages/admin-sdk/src/client.ts` — resolves `baseUrl`, `fetch`, `retry`, `credentials` (default `'include'`)
- [x] T005 Implement dual auth-header selection in `client.ts`'s `dynamicRequestFn` — `X-Spree-Api-Key` when `secretKey` is set, `Authorization: Bearer` (from mutable `currentToken`) otherwise
- [x] T006 Implement `X-Spree-Store-Id` header injection driven by `setStore()` for multi-store admin routing
- [x] T007 Implement 401 retry-once behavior gated on a registered `onUnauthorized` handler, excluding `/auth/*` paths
- [x] T008 Define `AdminClientConfig` and `Client` (extends `AdminClient`) interfaces with `setStore`/`setToken`/`onUnauthorized`
- [x] T009 [packages/admin-sdk] Author `scripts/generate-admin-client.ts`: dependency-free inline YAML parser for `docs/api-reference/admin.yaml`, emits `src/admin-client.ts` with namespaced resource methods (`client.products.list()`, etc.) following `packages/sdk/src/store-client.ts` conventions
- [x] T010 [packages/admin-sdk] Wire `src/params.ts` with generated + hand-written request param interfaces (create/update bodies) plus `PREFERENCE_MASK_TOKEN` / `isMaskedSecret()` helpers for masked preference fields (e.g. payment method credentials)
- [x] T011 [packages/admin-sdk] Consume Typelizer-generated response types under `src/types/generated/` (Address, Product, Order, Customer, Channel, CustomField, ApiKey, etc.)

**Checkpoint**: Client construction, dual auth, and codegen pipeline are in place — resource-level work can proceed.

---

## Phase 3: User Story 1 - Server-to-server integration with a secret key (Priority: P1)

**Goal**: A backend integration can authenticate with a secret key and call any Admin API v3 resource with full typing.

**Independent Test**: `createAdminClient({ baseUrl, secretKey })` + `client.products.list()` sends `X-Spree-Api-Key` and returns typed `PaginatedResponse<AdminProduct>`.

### Tests for User Story 1

- [x] T012 [P] [US1] `packages/admin-sdk/tests/helpers.ts` — `createTestClient()` fixture using `secretKey: 'sk_test'` against a mocked base URL
- [x] T013 [P] [US1] `packages/admin-sdk/tests/products.test.ts`, `orders.test.ts`, `customers.test.ts`, and 20+ sibling resource-area specs exercising list/get/create/update/destroy against MSW mocks
- [x] T014 [P] [US1] `packages/admin-sdk/tests/api-keys.test.ts` — covers scope-gated secret-key behavior
- [x] T015 [P] [US1] `packages/admin-sdk/tests/read-only-resources.test.ts` — asserts resources without write endpoints don't expose mutating methods

### Implementation for User Story 1

- [x] T016 [US1] Generate namespaced resource methods for every Admin API v3 resource in `admin-client.ts` (depends on T009)
- [x] T017 [US1] Ensure `SpreeError` (code, status, details) surfaces for non-2xx responses instead of raw fetch rejections (from `@spree/sdk-core`)
- [x] T018 [US1] Document secret-key server-to-server usage and scope requirements in package README/examples

**Checkpoint**: Secret-key mode is independently functional and tested.

---

## Phase 4: User Story 2 - Admin SPA session via JWT with automatic refresh (Priority: P1)

**Goal**: The `@spree/dashboard` SPA (or any JWT consumer) gets transparent 401 recovery without writing retry logic.

**Independent Test**: Client with `jwtToken` set, `onUnauthorized` registered; a forced 401 triggers the handler and retries once.

### Tests for User Story 2

- [x] T019 [P] [US2] `packages/admin-sdk/tests/auth.test.ts` — login/refresh/logout against `createUnauthenticatedClient()`
- [x] T020 [P] [US2] `packages/admin-sdk/tests/helpers.test.ts` — `onUnauthorized` retry-once semantics and `/auth/*` exclusion

### Implementation for User Story 2

- [x] T021 [US2] `setToken()` mutates `currentToken` in closure without recreating the client (depends on T004)
- [x] T022 [US2] `onUnauthorized()` registers a single handler invoked on 401, excluded for `/auth/*` paths (depends on T007)
- [x] T023 [US2] `credentials: 'include'` default so the httpOnly refresh cookie flows on `/api/v3/admin/auth/*`, overridable via `AdminClientConfig.credentials`
- [x] T024 [US2] `MeResponse` / `PermissionRule` / `AuthTokens` types exposed for the dashboard SPA to bootstrap its CanCanCan-derived permission model client-side

**Checkpoint**: JWT mode with auto-refresh is independently functional and tested; `packages/dashboard` consumes it as the reference integration.

---

## Phase 5: User Story 3 - Discoverable, typed resource surface generated from the API (Priority: P2)

**Goal**: The SDK's resource surface and types stay in sync with the Admin API without manual maintenance.

**Independent Test**: Adding an endpoint to `docs/api-reference/admin.yaml` and re-running `pnpm generate:admin-client` produces the corresponding typed method with no manual edits.

### Tests for User Story 3

- [x] T025 [P] [US3] `pnpm typecheck` (both `tsconfig.json` and `tsconfig.examples.json`) validates generated types compile and examples stay accurate
- [x] T026 [P] [US3] `packages/admin-sdk/tests/custom-fields.test.ts`, `channels.test.ts`, `webhook-endpoints.test.ts` — spot-check newer/less-common resources generated by the pipeline

### Implementation for User Story 3

- [x] T027 [US3] `scripts/generate-admin-client.ts` parses `docs/api-reference/admin.yaml` and regenerates `src/admin-client.ts` (treated as generated output, not hand-edited)
- [x] T028 [US3] Response types sourced from the shared Typelizer pipeline (`bundle exec rake typelizer:generate` upstream in `spree/api`), mirrored into `src/types/generated/`
- [x] T029 [US3] `examples/` directory demonstrates resource usage and is type-checked in CI via `tsconfig.examples.json`

**Checkpoint**: All three user stories are independently functional; full resource coverage is generated and tested.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T030 [P] Package published under the `next` dist-tag via Changesets (`.changeset/`) reflecting Developer Preview status, distinct from `packages/sdk`'s stable channel
- [x] T031 Full test suite: `cd packages/admin-sdk && pnpm test` (Vitest + MSW, 25+ resource files) passes
- [x] T032 `pnpm lint` (Biome, extending root config) and `pnpm typecheck` pass
- [x] T033 [Migration] Recorded gap in spec.md: no dedicated `docs/plans/` entry governs the SDK package's own architectural surface (only its auth mechanisms are covered elsewhere) — noted for future work, not resolved by this migration entry

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — blocks all user stories (client construction + codegen pipeline must exist before resource methods can be tested).
- **User Stories (Phase 3–5)**: All depend on Foundational. US1 and US2 (both P1) were built together since `client.ts` implements both auth modes in one module; US3 (P2, the codegen/type pipeline) underlies both but is separated here because it's independently verifiable (regenerate and diff).
- **Polish (Phase 6)**: Depends on all user stories.

### Parallel Opportunities

- All `[P]`-marked test tasks within a phase (one file per resource area) ran independently of each other.
- US1 and US2 implementation both live in `client.ts` and were developed together, not in parallel by different owners; US3's codegen script is a separate file/concern and could be worked on independently.

## Notes

- This tasks.md documents an already-shipped feature (brownfield migration) — all tasks are checked off as a record of what was built, not a forward execution plan.
- Future work building on this package (new resources, new auth modes) should generate a fresh tasks.md via `/speckit-tasks` against an updated plan.md, not append to this one.
