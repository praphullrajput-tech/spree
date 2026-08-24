# Spree Commerce Constitution

## Preamble

This constitution governs how spec-kit (`/speckit.*`) features are planned and
built in this repository. It is a **thin governance layer**, not a
restatement of project conventions — the authoritative source for coding
conventions, architecture, and workflow detail is
[`CLAUDE.md`](../../CLAUDE.md) (symlinked as `AGENTS.md`). Where this
document and `CLAUDE.md` overlap, `CLAUDE.md` is the source of truth; this
document adds the spec-kit-specific gates and gives them citations back into
`CLAUDE.md`.

## Core Principles

### I. Module Boundaries Are Load-Bearing

Spree is a monorepo split into independently-versioned Ruby gems and
TypeScript packages. A feature spec/plan MUST identify which module(s) it
touches and MUST NOT blur the boundary between them:

- Backend: `spree/core` (models/services/business logic), `spree/api`
  (Store & Admin REST API v3), `spree/admin` (legacy Rails admin, being
  phased out — do not add new features here), `spree/emails` (deprecated in
  6.0, avoid new work)
- Frontend: `packages/dashboard` (routes/app shell), `packages/dashboard-ui`
  (headless design-system primitives — no provider/hook imports),
  `packages/dashboard-core` (registries, providers, plugin API),
  `packages/sdk` / `packages/admin-sdk` (generated + hand-written API
  clients), `packages/sdk-core` (shared HTTP layer)

Cross-module coupling must go through the documented extension points
(Dependencies registry, table/nav/slot registries, Admin API — see
`CLAUDE.md` → "Dependencies System" and "Package Split") — never by reaching
across a gem/package boundary directly.

### II. The Admin API Is the Only Frontend Data Source

Per `CLAUDE.md` → "When implementing a new admin feature": `packages/dashboard`
MUST NOT reach into Rails models or server-rendered HTML. If an endpoint or
attribute is missing, add it to `spree/api` first (serializer + controller +
type-generation pipeline), then consume it from the SPA. A plan that adds UI
before its backing API endpoint is incomplete.

### III. Read/Write Field Symmetry (NON-NEGOTIABLE)

Whatever an Alba serializer exposes on read is exactly what the
corresponding controller's `permitted_params` must accept on write — no
client-side field-name translation. Legacy-column bridges belong on the
model (`label=` aliasing `presentation=`), never as a controller or frontend
mapper. See `CLAUDE.md` → "API Controllers" and "Forms" (`Don't add form↔API
mappers to paper over field renames`).

### IV. Test-Backed, Pragmatically

Every plan MUST specify its test approach using the project's actual
frameworks — RSpec (backend, per-gem `spec/`), Vitest (frontend unit,
colocated `*.test.ts`), Playwright (`packages/dashboard/e2e`, UI-only
assertions per `CLAUDE.md` → "Admin SPA E2E"). Do not invent a testing
approach the project doesn't use (no snapshot-testing framework, no Cypress,
no `.rspec`-config assumptions beyond what each gem defines). Tests for
standard Rails validations or framework behavior are NOT required — only
custom logic and edge cases.

### V. Translations and Prefixed IDs Are Not Optional

Any user-visible string added to `packages/dashboard` or
`packages/dashboard-core` MUST go through i18next (`en.json` in both
packages, updated together). Any new resource ID exposed by an API endpoint
MUST be a prefixed ID (`prod_...`, `variant_...`), never a raw database ID.
These are structural requirements, not style preferences — see `CLAUDE.md`
→ "Translations" and "Prefixed IDs".

### VI. Architectural Changes Go Through `docs/plans/`

This repo already runs an ADR process independent of spec-kit:
significant architectural changes require a plan in `docs/plans/` using
`docs/plans/_template.md`, checked against the active/pending plans listed
in `CLAUDE.md` for conflicts before implementation. A spec-kit feature that
qualifies as "significant architectural change" (new model, new API
surface, cross-cutting rename) MUST reference or create the corresponding
`docs/plans/` entry — spec-kit specs do not replace this process, they sit
alongside it. If a `docs/plans/6.0-*.md` or `5.x-*.md` file already governs
the area being touched, its "Constraints on Current Work" section binds the
feature even if the feature isn't implementing that plan.

## Quality Gates

A feature is not ready for `/speckit-implement` completion until:

- **Backend**: `bundle exec rspec` passes for every touched gem; new
  Ransack-exposed attributes/associations/scopes are explicitly
  allowlisted (`whitelisted_ransackable_*`); migrations follow
  `CLAUDE.md` → "Migrations" (no FKs, no defaults, explicit `null: false`,
  cross-DB-safe JSON columns).
- **Frontend**: `pnpm typecheck` and `pnpm lint` pass at the workspace
  root; `pnpm test` (Vitest) passes for touched packages; Playwright e2e
  added/updated for new dashboard user flows under `packages/dashboard/e2e`.
- **API changes**: if any Alba serializer changed, the type-generation
  pipeline (`bundle exec rake typelizer:generate` → `pnpm generate:zod` →
  integration specs → `rake rswag:specs:swaggerize` → SDK tests) has been
  run — the Lefthook pre-commit hook covers steps 1–2 automatically but
  steps 3–5 still require a manual run before pushing.
- **Commit hygiene**: commits touching multiple logical changes are split
  or squashed with `--fixup`/autosquash per `CLAUDE.md` → "General rules".

## Governance

This constitution supersedes ad-hoc practice for spec-kit-driven work, but
is subordinate to `CLAUDE.md` on any point of detail — when they conflict,
treat it as a bug in this file and fix the constitution, don't silently
follow whichever is more convenient. `/speckit-plan`'s "Constitution Check"
gate MUST cite the specific principle(s) above (by numeral) that a plan
satisfies or violates; violations require an entry in that plan's
Complexity Tracking table. Amendments to this file should be small and
should not duplicate content that already lives in `CLAUDE.md` — if a rule
belongs to general project conduct rather than spec-kit governance, it goes
in `CLAUDE.md` instead.

**Version**: 1.0.0 | **Ratified**: 2026-08-18 | **Last Amended**: 2026-08-18
