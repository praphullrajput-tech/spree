# Implementation Plan: @spree/admin-sdk — Admin API Client

**Branch**: `040-admin-sdk-admin-api-client` | **Date**: 2026-08-25 | **Spec**: `specs/040-admin-sdk-admin-api-client/spec.md`

**Input**: Feature specification from `/specs/040-admin-sdk-admin-api-client/spec.md`

**Note**: This is a brownfield migration entry — the feature is already implemented. This plan documents the as-built architecture rather than proposing new work.

## Summary

`@spree/admin-sdk` is a TypeScript client for the Spree Admin API v3, mirroring the resource-oriented pattern of `@spree/sdk` (Store API). It supports two mutually-exclusive auth modes — secret API key (server-to-server, `X-Spree-Api-Key`) and JWT (admin SPA sessions, `Authorization: Bearer` with automatic 401-retry via an app-supplied refresh callback). The resource surface (`AdminClient` in `src/admin-client.ts`) is generated from the Admin API's OpenAPI spec by `scripts/generate-admin-client.ts`; response/param types flow from the shared Typelizer pipeline. The package is published under the `next` dist-tag while in Developer Preview.

## Technical Context

**Language/Version**: TypeScript (Node >=18), consumed by both a Vite-built React SPA (`packages/dashboard`) and arbitrary Node/browser server-to-server clients.

**Primary Dependencies**: `@spree/sdk-core` (shared `createRequestFn`, `SpreeError`, retry logic, Ransack param transforms); `tsup` (build); `tsx` (codegen script runtime); `vitest` + `msw` (tests); `yaml` (devDependency, though the codegen script itself uses a dependency-free inline YAML parser to avoid a runtime dependency in the shipped package).

**Storage**: N/A — this package makes HTTP calls only; no local persistence.

**Testing**: Vitest + MSW (Mock Service Worker) for HTTP mocking, mirroring `packages/sdk`'s test conventions. Tests live in `packages/admin-sdk/tests/` (25+ resource-area files: `products.test.ts`, `orders.test.ts`, `customers.test.ts`, `channels.test.ts`, `custom-fields.test.ts`, `api-keys.test.ts`, `webhook-endpoints.test.ts`, `auth.test.ts`, etc.) plus `helpers.test.ts` and `read-only-resources.test.ts` for cross-cutting behavior.

**Target Platform**: Published npm package (`next` dist-tag), consumed by `packages/dashboard` (browser) and by third-party Node/browser integrations.

**Project Type**: Monorepo TypeScript package — `packages/admin-sdk`, depending on `packages/sdk-core`.

**Performance Goals**: N/A beyond standard HTTP client overhead; retry/backoff behavior inherited from `@spree/sdk-core`'s `resolveRetryConfig`.

**Constraints**: Secret-key mode must never be embedded in browser-shipped code (server-to-server only, per spec Assumptions). JWT-mode 401 retry must happen at most once per request and must never fire on `/auth/*` paths (avoids refresh loops).

**Scale/Scope**: Full Admin API v3 resource surface — dozens of resources (products, variants, orders, customers, customer groups, channels, custom fields/definitions, API keys, admin users, allowed origins, gift cards, invitations, markets, option types, payment methods, price lists, promotions, stock, store settings, tax categories, webhook endpoints, exports, and more per `src/types/generated/`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Pass. Touches only `packages/admin-sdk` and its declared dependency `packages/sdk-core`; consumed by `packages/dashboard` through the documented SDK boundary (dashboard hooks wrap SDK calls, never bypass it), not a direct reach-across.
- **II. Admin API Is the Only Frontend Data Source**: Pass (reinforces it). This package *is* the frontend's sanctioned path to the Admin API — its existence is what makes Principle II enforceable for `packages/dashboard`.
- **III. Read/Write Field Symmetry**: N/A directly — this package does not define serializers; it consumes whatever `spree/api` Admin serializers expose via the Typelizer pipeline. Symmetry is enforced upstream in `spree/api`.
- **IV. Test-Backed**: Pass. Vitest + MSW suite in `packages/admin-sdk/tests/` covers every resource area; `pnpm typecheck` covers both `src/` and `examples/` (`tsconfig.examples.json`).
- **V. Translations and Prefixed IDs**: N/A for translations (no user-visible strings in an SDK package). Prefixed IDs: the SDK passes through whatever ID format the Admin API serializers return (prefixed per Principle V, enforced at the `spree/api` layer) — no raw-ID handling added here.
- **VI. `docs/plans/` for Architectural Changes**: N/A for this migration entry (no new architectural change being introduced) — see spec.md Migration Notes for the identified gap (no dedicated `docs/plans/` entry for the SDK package itself; only its auth mechanisms are covered by `5.5-admin-auth-cookie-refresh.md` / `5.5-admin-api-key-scopes.md`).

## Project Structure

### Documentation (this feature)

```text
specs/040-admin-sdk-admin-api-client/
├── plan.md              # This file
├── spec.md              # Feature specification (migrated)
└── tasks.md             # Task breakdown (migrated, all marked complete)
```

### Source Code (repository root)

```text
packages/admin-sdk/
├── src/
│   ├── client.ts                  # createAdminClient() — auth mode wiring, session mutation, 401 retry
│   ├── admin-client.ts            # AdminClient — generated namespaced resource surface (~2450 lines)
│   ├── params.ts                  # Generated + hand-written request param types, masked-secret helpers
│   ├── index.ts                   # Package entry point
│   └── types/
│       ├── index.ts
│       └── generated/             # Typelizer-generated response types (Address, Product, Order, ...)
├── scripts/
│   └── generate-admin-client.ts   # Codegen: docs/api-reference/admin.yaml -> src/admin-client.ts
├── tests/
│   ├── helpers.ts, setup.ts        # createTestClient()/createUnauthenticatedClient(), paginated() fixture
│   ├── mocks/                      # MSW request handlers
│   └── *.test.ts                   # One file per resource area (25+ files)
├── examples/                       # Type-checked usage examples (tsconfig.examples.json)
└── package.json                    # "next" dist-tag, Developer Preview

# Upstream dependency (not modified by this package):
docs/api-reference/admin.yaml       # OpenAPI spec the codegen script reads
spree/api/                          # Source of the serializers/controllers the spec describes

# Shared HTTP layer (not modified by this package):
packages/sdk-core/                  # createRequestFn, SpreeError, retry, Ransack param transform

# First-party consumer:
packages/dashboard/src/hooks/       # Wraps admin-sdk calls (use-orders.ts, use-products.ts, ...)
```

**Structure Decision**: Single-package scope — `packages/admin-sdk`, depending on `packages/sdk-core`. No `spree/api`, `spree/core`, or `packages/dashboard-ui`/`dashboard-core` changes are part of this feature; `packages/dashboard` is a consumer, not something this feature modifies directly.

## Complexity Tracking

*No constitution violations identified — table intentionally omitted.*
