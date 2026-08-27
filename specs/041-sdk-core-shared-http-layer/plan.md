# Implementation Plan: @spree/sdk-core — Shared HTTP Layer

**Branch**: `041-sdk-core-shared-http-layer` | **Date**: 2026-08-24 | **Spec**: `specs/041-sdk-core-shared-http-layer/spec.md`

**Input**: Feature specification from `specs/041-sdk-core-shared-http-layer/spec.md`

**Note**: This plan is a reverse-engineered (brownfield) record of an already-implemented feature — it documents what exists, not what to build. No implementation work follows from it.

## Summary

`@spree/sdk-core` is a private TypeScript package providing the shared HTTP/retry/error/param-transform layer consumed by both `@spree/sdk` (Store API) and `@spree/admin-sdk` (Admin API). It centralizes `createRequestFn()` (fetch wrapper + URL/header building + retry loop), `SpreeError` (typed error surfaced to both SDKs), and `transformListParams()` (flat-params → Ransack `q[...]` translation), so the two public SDKs never diverge on error shape, retry semantics, or filter-param encoding.

## Technical Context

**Language/Version**: TypeScript (Node >= 18.0.0 per `packages/sdk-core/package.json` engines)

**Primary Dependencies**: None at runtime (zero external deps in `package.json`) — relies only on the platform `fetch`, `URL`, and `crypto.randomUUID()` globals. Dev-only: `tsup` (build), `typescript`, Biome (lint/format, via root config).

**Storage**: N/A — stateless request-building layer, no persistence.

**Testing**: No dedicated `packages/sdk-core/tests/` suite exists. Behavior is exercised indirectly via `packages/sdk/tests/retry.test.ts`, `packages/sdk/tests/params.test.ts`, `packages/sdk/tests/error-handling.test.ts`, `packages/sdk/tests/client.test.ts` (Vitest + MSW, run from `packages/sdk`).

**Target Platform**: Any JS runtime the two consuming SDKs support — browser (SPA/storefront) and Node (server-to-server integrations), per its dual CJS/ESM `exports` map.

**Project Type**: Monorepo TypeScript package — `packages/sdk-core`, private (`"private": true`), not published, consumed via `workspace:*` by `packages/sdk` and `packages/admin-sdk`.

**Performance Goals**: N/A — thin synchronous request-shaping + a bounded retry loop (`maxRetries` default 2); no independent performance target beyond "adds negligible overhead over a raw `fetch` call".

**Constraints**: Must not introduce a runtime dependency (keeps both consuming SDKs' bundle size minimal); must stay side-effect-free at import time; must work identically in browser and Node (no Node-only APIs beyond globals available in both).

**Scale/Scope**: 5 source files (`request.ts`, `types.ts`, `helpers.ts`, `params.ts`, `index.ts`), no sub-packages.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches only `packages/sdk-core` (per Module Impact table in spec.md). It is itself the documented extension point/shared layer `packages/sdk` and `packages/admin-sdk` are expected to build on — per constitution Principle I's explicit listing of `packages/sdk-core` as a first-class module. No boundary crossing: it has zero imports from any other package in this monorepo. **PASS**.
- **II. Admin API Is the Only Frontend Data Source**: N/A — this package makes no admin-SPA-facing changes; it is consumed by `@spree/admin-sdk`, which itself talks to the Admin API. **N/A**.
- **III. Read/Write Field Symmetry**: N/A — no Alba serializer or controller changes; `transformListParams` reshapes query-string encoding, not field names, and `ErrorResponse`/`ListParams` types mirror the API's existing wire contract rather than defining a new one. **N/A**.
- **IV. Test-Backed**: Covered indirectly via Vitest suites in `packages/sdk/tests/` (`retry.test.ts`, `params.test.ts`, `error-handling.test.ts`). No dedicated `packages/sdk-core` test suite exists — flagged as a gap in spec.md Assumptions, not a violation requiring Complexity Tracking (this plan does not propose adding one, since it documents existing state only). **PASS** (with gap noted).
- **V. Translations and Prefixed IDs**: N/A — no user-visible strings, no resource IDs originate from this package (prefixed-ID handling lives in the consuming SDKs' serializable types, not here). **N/A**.
- **VI. `docs/plans/` for Architectural Changes**: This package predates spec-kit adoption and has no dedicated `docs/plans/` entry; it is referenced only implicitly via CLAUDE.md's monorepo structure table and the constitution's own Module Boundaries list (Principle I already documents it as a standing architectural fixture). No new architectural change is being introduced by this migration — it is a documentation-only reverse-engineering pass. **N/A** for this migration; a future feature that changes `sdk-core`'s public contract (e.g. altering `SpreeError`'s shape) would need to consider whether it qualifies as significant enough for a new `docs/plans/` entry at that time.

No violations — Complexity Tracking table omitted.

## Project Structure

### Documentation (this feature)

```text
specs/041-sdk-core-shared-http-layer/
├── plan.md              # This file
├── spec.md              # Feature specification (migrated)
└── tasks.md             # Task checklist (all closed — reverse-engineered)
```

### Source Code (repository root)

```text
# packages/sdk-core — shared HTTP/retry/error/param layer (existing, documented as-is)
packages/sdk-core/
├── package.json                # private:true, dual CJS/ESM exports, zero runtime deps
├── src/
│   ├── index.ts                 # public barrel export (createRequestFn, SpreeError, transformListParams, getParams, resolveRetryConfig, shared types)
│   ├── request.ts                # createRequestFn(), SpreeError, RetryConfig/ResolvedRetryConfig machinery, retry loop, idempotency-key generation
│   ├── types.ts                  # LocaleDefaults, ListParams, PaginatedResponse, ErrorResponse, AddressParams, LoginCredentials, etc.
│   ├── helpers.ts                 # getParams() (expand/fields serialization), resolveRetryConfig()
│   └── params.ts                  # transformListParams() — flat params → Ransack q[...] encoding
└── (no dist/ or tests/ present at time of migration — dist/ is build output, gitignored)

# Consumers (unchanged by this migration — for traceability only)
packages/sdk/src/{client.ts,store-client.ts}     # builds request() via createRequestFn, re-exports SpreeError
packages/admin-sdk/src/                            # same pattern for Admin API
packages/sdk/tests/{retry,params,error-handling,client}.test.ts   # exercises sdk-core behavior indirectly
```

**Structure Decision**: Single-module documentation pass — `packages/sdk-core` only, per spec.md's Module Impact table. No other package's source changes; `packages/sdk` and `packages/admin-sdk` are listed for traceability (they are the package's only consumers) but this plan makes no changes to them.

## Complexity Tracking

*No violations — table not applicable.*
