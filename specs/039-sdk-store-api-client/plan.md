# Implementation Plan: @spree/sdk — Store API Client

**Branch**: `039-sdk-store-api-client` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/039-sdk-store-api-client/spec.md`

**Note**: Brownfield migration — this plan documents the implementation as it already exists, for spec-kit traceability, not as a forward design.

## Summary

`@spree/sdk` is the official TypeScript client for the Spree Store API v3, used by third-party headless storefronts and the Next.js storefront reference implementation. It exposes a flat, fully-typed resource surface (`client.products`, `client.carts`, `client.orders`, …) built on a shared low-level request layer (`@spree/sdk-core`) that handles auth headers (publishable key or JWT), retry/backoff, and Ransack-style param transformation. Generated TypeScript types and Zod schemas track the Store API's Alba serializers via a repo-wide type-generation pipeline.

## Technical Context

**Language/Version**: TypeScript (Node >=18 / browser), built with Tsup (CJS + ESM), tested with Vitest

**Primary Dependencies**: `@spree/sdk-core` (shared HTTP/retry/error layer), `zod` (peer dep, schema validation), `msw` (test-only HTTP mocking)

**Storage**: N/A — stateless HTTP client; no local persistence beyond in-memory `LocaleDefaults`

**Testing**: Vitest unit tests (`packages/sdk/tests/*.test.ts`, MSW-mocked) + a separate integration config (`vitest.integration.config.ts`) for live-API smoke tests

**Target Platform**: Any JS runtime with `fetch` (native Node >=18, browsers) or a supplied `fetch` polyfill; published as dual CJS/ESM with `types`, `zod`, and `webhooks` subpath exports

**Project Type**: Monorepo TypeScript package — `packages/sdk` (this feature) depending on `packages/sdk-core` (shared, not owned by this feature)

**Performance Goals**: N/A — thin HTTP client; performance is bounded by the Store API itself and the configured retry/backoff envelope (default: 2 retries, 300ms base delay, 10s cap)

**Constraints**: Must not hand-edit `src/types/generated/` or `src/zod/generated/` — both are pipeline output; `pnpm generate:zod` must be re-run (or the Lefthook pre-commit hook triggered) after any Store API serializer change

**Scale/Scope**: One resource class (`StoreClient`) covering ~20 resource groups (auth, products, categories, carts, orders, customer, addresses, payments, payment sessions, wishlists, gift cards, store credits, credit cards, newsletter subscribers, policies, markets, countries, currencies, invitations, digital links) per `packages/sdk/src/store-client.ts` (983 lines)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Pass. This feature lives entirely in `packages/sdk`, depending on `packages/sdk-core` through its published exports (`createRequestFn`, `resolveRetryConfig`, `SpreeError`, shared types) — no reach-across into `spree/api` internals or `packages/admin-sdk`.
- **II. Admin API Is the Only Frontend Data Source**: N/A — this is the Store API client, not the admin dashboard. `packages/dashboard` does not consume `@spree/sdk`.
- **III. Read/Write Field Symmetry**: N/A to enforce here (the SDK doesn't define serializers), but the SDK's generated types are a downstream check on it — if `spree/api` violates read/write symmetry, the generated Zod schema and hand-written resource method signatures will visibly diverge.
- **IV. Test-Backed**: Pass. Vitest suite (`packages/sdk/tests/`) covers auth, cart, categories, client construction, customer, error handling, markets, newsletter subscribers, orders, params transformation, password resets, payment sessions/setup sessions, payments, policies, products, retry behavior, webhooks, and wishlists — one file per concern, MSW-mocked.
- **V. Translations and Prefixed IDs**: Partial. No i18next surface (this is a backend-agnostic TS client, not `packages/dashboard`). Prefixed IDs: the SDK passes through whatever the Store API returns/accepts (`prod_...`, `or_...`, etc.) verbatim — it does not itself mint or strip prefixes, so this principle is satisfied by construction, not by SDK-side logic.
- **VI. `docs/plans/` for Architectural Changes**: N/A — no `docs/plans/` entry targets `@spree/sdk` directly; it is the consuming implementation of whatever Store API changes those plans describe (e.g. `5.4-store-api-naming-standardization.md`, `6.0-admin-api.md`'s Store-API-adjacent conventions).

No violations to track.

## Project Structure

### Documentation (this feature)

```text
specs/039-sdk-store-api-client/
├── plan.md              # This file
├── spec.md              # Feature specification (already migrated)
└── tasks.md             # Task breakdown (already migrated, all [x])
```

### Source Code (repository root)

```text
# packages/sdk — Store API TypeScript client
packages/sdk/
├── src/
│   ├── client.ts                 # createClient() factory, ClientConfig/Client interfaces
│   ├── store-client.ts           # StoreClient — all resource groups (auth, products, carts, orders, ...)
│   ├── index.ts                  # public package entry point
│   ├── webhooks.ts                # webhook signature verification (separate subpath export)
│   ├── types/generated/          # one .ts file per Store API resource, generated from Alba serializers
│   └── zod/generated/            # one .ts Zod schema per resource, generated from the TS types
├── scripts/generate-zod.ts        # `pnpm generate:zod` — regenerates zod/generated/ from types/generated/
├── tests/
│   ├── helpers.ts                 # createTestClient() with fixed baseUrl/publishableKey
│   ├── mocks/                     # MSW request handlers
│   ├── *.test.ts                  # one file per resource/concern (auth, cart, retry, error-handling, ...)
│   └── integration/                # live-API smoke tests (vitest.integration.config.ts)
├── package.json                   # scripts: build (tsup), test (vitest), generate:zod, typecheck, lint (biome)
└── tsconfig.examples.json          # typechecks README/example snippets separately

# packages/sdk-core — shared HTTP layer (dependency, not owned by this feature)
packages/sdk-core/src/
├── request.ts                     # createRequestFn(), SpreeError, retry/backoff (calculateDelay)
├── helpers.ts                     # resolveRetryConfig(), getParams()
├── params.ts                       # transformListParams() — Ransack query shape
└── types.ts                        # LocaleDefaults, ErrorResponse, ListParams/ListResponse, AddressParams, etc.
```

**Structure Decision**: Frontend-only, single package plus its shared dependency: `packages/sdk` (owned surface — client factory, resource methods, generated types/Zod, tests) depends on `packages/sdk-core` (shared HTTP/retry/error primitives, also consumed by `packages/admin-sdk`). No backend (`spree/api`), no `packages/dashboard*` changes — this feature is a pure API consumer.

## Complexity Tracking

*No constitution violations — table not needed.*
