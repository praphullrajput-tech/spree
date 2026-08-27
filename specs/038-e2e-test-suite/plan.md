# Implementation Plan: Admin SPA E2E Test Suite

**Branch**: `038-e2e-test-suite` | **Date**: 2026-08-25 | **Spec**: `specs/038-e2e-test-suite/spec.md`

**Input**: Feature specification from `/specs/038-e2e-test-suite/spec.md`

**Note**: This is a reverse-engineered (brownfield) plan for already-shipped test infrastructure — Phase 0/1 research artifacts (`research.md`, `data-model.md`, `contracts/`) are not applicable; there is no unknown design space to resolve, only the existing implementation to document.

## Summary

`packages/dashboard/e2e/` implements a Playwright E2E harness that boots a real, disposable Rails test server (`spree/api/spec/dummy`, port 3010, `RAILS_ENV=test`, SQLite) and a real Vite dev server (port 5174) once per suite run, seeds base + fixture data via a Rails runner script, and runs 33 spec files serially against the rendered admin SPA. Specs drive and assert exclusively through visible UI (`getByRole`/`getByLabel` + `toBeVisible` polling), with two documented, narrow exceptions for API-level waits. Shared interaction helpers (login, index-page readiness, row menus, bulk actions, address forms) live in `e2e/helpers.ts`; path constants in `e2e/paths.ts`; lifecycle in `e2e/global-setup.ts` / `e2e/global-teardown.ts`.

## Technical Context

**Language/Version**: TypeScript (Playwright test runner, admin SPA under test) — frontend-only feature; no Ruby application code is added, though the harness shells out to the existing `spree/api` dummy Rails app as its backend fixture

**Primary Dependencies**: `@playwright/test`, the admin SPA's own stack (TanStack Router/Query, React Hook Form + Zod, shadcn/ui) as the system under test, `spree/api/spec/dummy` (Rails 7.2 dummy app) as the backend fixture, `bundle exec spec/dummy/bin/rails runner`/`rails server` invoked as child processes

**Storage**: SQLite3 (`spree/api/spec/dummy/db/spree_test.sqlite3`) — wiped and reseeded on every `globalSetup()` run; no persistent storage owned by the E2E harness itself beyond the transient `.credentials.json` / `.rails.pid` files in `packages/dashboard/e2e/`

**Testing**: Playwright (`packages/dashboard/e2e`), UI-only assertions per constitution Principle IV — this feature *is* the test suite, so "testing" and "the feature" are the same artifact

**Target Platform**: Local developer machine / CI runner with a working Ruby/Bundler environment for `spree/api`'s dummy app (independent of the Docker-based `pnpm server:*` day-to-day dev workflow) plus Node/pnpm for the Vite/Playwright side

**Project Type**: Monorepo — TypeScript package `packages/dashboard` only (its `e2e/` subdirectory), invoking the `spree/api` Ruby gem's dummy app as an external test fixture process, not as a code dependency

**Performance Goals**: N/A — not a runtime feature; the operative constraint is suite wall-clock time under `workers: 1` serial execution (bounded by `timeout: 30_000` per test, `webServer` boot timeout `60_000`, Rails boot poll timeout `30_000`)

**Constraints**: Must run fully isolated from a developer's own dev stack (ports 3010/5174 vs 3000/5173); must be fully serial (`fullyParallel: false, workers: 1`) because all specs share one Rails process + one SQLite file; must leave no orphaned Rails process on exit

**Scale/Scope**: 33 spec files, ~2 shared helper modules (`helpers.ts`, `products-helpers.ts`), 1 `fixtures/` subdirectory, covering products (11 files), promotions/customers/channels/markets/payment-methods/categories/custom-fields/translations (per-resource CRUD + bulk actions), auth/invitations/profile/store-settings, stock locations/transfers, tax categories, webhooks, gift cards, allowed origins

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches only `packages/dashboard` (its `e2e/` subtree). It invokes `spree/api`'s dummy Rails app as an out-of-process test fixture via `bundle exec ... rails runner/server` — this is a documented extension-point-free boundary crossing, but it is the *only* way to get a real backend for E2E purposes (no mocking layer is used, by design, per constitution Principle IV's "use the project's actual frameworks"). No gem/package code is shared or imported across the boundary; the only coupling is HTTP (Vite proxy → Rails on :3010) and a JSON credentials file.
- **II. Admin API Is the Only Frontend Data Source**: N/A to this feature directly — the harness doesn't add SPA features, but it upholds this principle for every spec: the SPA under test talks only to the real Admin API v3 (via the Vite proxy), never to Rails models or server-rendered HTML.
- **III. Read/Write Field Symmetry**: N/A — no serializers or `permitted_params` are added by this feature.
- **IV. Test-Backed**: This feature *is* the Playwright layer named in Principle IV. No RSpec/Vitest additions apply here (though the harness depends on the `spree/api` dummy app's existing schema/seeds).
- **V. Translations and Prefixed IDs**: N/A — no new user-visible strings or new resource IDs are introduced; the suite exercises existing SPA copy (already i18next-backed) and existing prefixed IDs (`store_id` read from seed output is already a prefixed ID, e.g. `store_...`).
- **VI. `docs/plans/` for Architectural Changes**: N/A — this is test infrastructure, not an architectural change to a gem/package's data model or API surface; root `CLAUDE.md` → "Admin SPA E2E (Playwright)" already documents the convention this plan reverse-engineers, so no new `docs/plans/` entry is created.

No violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/038-e2e-test-suite/
├── plan.md              # This file
└── tasks.md             # Task list (reverse-engineered — all tasks already completed)
```

No `research.md`, `data-model.md`, or `contracts/` — brownfield migration of already-shipped test infrastructure with no open design questions.

### Source Code (repository root)

```text
# packages/dashboard — E2E harness lives entirely under e2e/
packages/dashboard/
├── playwright.config.ts        # Ports, webServer (Vite), globalSetup/globalTeardown wiring, serial execution
└── e2e/
    ├── global-setup.ts         # Wipes + reseeds SQLite, boots Rails on :3010, writes .credentials.json / .rails.pid
    ├── global-teardown.ts      # Kills the Rails process by recorded PID
    ├── paths.ts                # E2E_DIR / CREDENTIALS_FILE / RAILS_PID_FILE constants
    ├── helpers.ts               # login, gotoIndex, openRowMenu, clickBulkAction, rowButton, fillAddressForm, fixture-name constants
    ├── products-helpers.ts     # Products-domain-specific spec helpers
    ├── fixtures/                # Static fixture assets (e.g. media uploads) used by specs
    └── *.spec.ts                # 33 spec files — one per resource/flow (see spec.md Migration Notes for full list)
```

**Structure Decision**: Frontend-only, entirely within `packages/dashboard/e2e/` — no other module in the Module Impact table is modified. `spree/api`'s dummy app is consumed as an external process fixture, not as a code dependency, so it is not listed as a touched module.

## Complexity Tracking

*No violations — table intentionally empty.*
