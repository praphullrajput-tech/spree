# Implementation Plan: @spree/cli — Docker-based Project Management CLI

**Branch**: `042-cli-tooling` | **Date**: 2026-08-25 | **Spec**: `specs/042-cli-tooling/spec.md`

**Input**: Feature specification from `specs/042-cli-tooling/spec.md`

**Note**: This plan is reverse-engineered from an already-shipped
implementation (brownfield migration), not authored ahead of a build. It
documents the existing architecture rather than proposing one.

## Summary

`@spree/cli` is a Node/TypeScript CLI (Commander-based) that gives a
developer two things from the terminal: full Docker dev-stack lifecycle
management for a `create-spree-app`-scaffolded project (`init`, `dev`,
`stop`, `restart`, `build`, `eject`, `upgrade`, plus Rails-workflow
passthroughs), and a generic, credential-self-provisioning Admin API client
(`spree api get|post|patch|delete`, `endpoints`, `schema`, `status`) built on
`@spree/admin-sdk`. Credentials resolve through four layered sources
(flags → env → project auto-mint → saved profile), persisted with
owner-only file permissions, and the API layer maps failures to two exit
codes with agent-actionable remediation hints.

## Technical Context

**Language/Version**: TypeScript (Node.js CLI, ESM), no Ruby changes
originate from this feature (it consumes `spree/core`'s
`spree:cli:create_api_key` Rake task and `spree/api`'s existing Admin API v3
surface as-is).

**Primary Dependencies**: `commander` (command parsing), `@clack/prompts`
(interactive prompts), `execa` (subprocess/`docker compose` invocation),
`picocolors` (terminal color), `console-table-printer` (`--format table`),
`@spree/admin-sdk` (Admin API HTTP client + `SpreeError`).

**Storage**: No database access from the CLI process itself. Two local
credential stores: `<project>/.spree/credentials.json` (project-scoped,
auto-minted, gitignored) and `~/.config/spree/config.json`
(`XDG_CONFIG_HOME`-aware, named profiles for remote stores).

**Testing**: Vitest, colocated under `packages/cli/` per the workspace
convention (`pnpm test` from the package). No RSpec/Playwright surface —
this package has no Ruby or admin-SPA code.

**Target Platform**: Developer workstation / CI runner with Docker + Docker
Compose installed, invoking a `create-spree-app`-scaffolded project
directory. Distributed via npm (`npm install -g @spree/cli`, `npx
@spree/cli`, or bundled automatically by `create-spree-app`).

**Project Type**: Monorepo TypeScript package — `packages/cli` only, with a
hard dependency on `packages/admin-sdk`.

**Performance Goals**: N/A — a synchronous CLI tool wrapping subprocess
calls and HTTP requests; no throughput target beyond "feels instant for
single API calls, streams logs live for `dev`."

**Constraints**: Must work fully offline for endpoint/schema
discovery/completion (bundled OpenAPI spec snapshot — no live spec fetch).
Must never write credentials world-readable (0600/0700). Must never
auto-mint a write-scoped key.

**Scale/Scope**: ~20 command modules under `packages/cli/src/commands/`,
plus a handful of shared modules (`api/`, `config.ts`, `context.ts`,
`docker.ts`, `constants.ts`, `types.ts`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Confined to `packages/cli`, consuming
  `packages/admin-sdk` through its public client/`SpreeError` exports only —
  no reach-through into `spree/api` controllers or Rails internals from
  TypeScript. The one cross-boundary call (`spree:cli:create_api_key`) goes
  through a Rake task invoked via `docker compose exec`, not a direct
  code-level import. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: N/A in the strict
  "admin SPA" sense — `packages/cli` is not `packages/dashboard`. But the
  same spirit holds: `spree api` never reaches into Rails models directly,
  it only calls the Admin API v3 over HTTP via `@spree/admin-sdk`. **Pass
  (by analogy).**
- **III. Read/Write Field Symmetry**: N/A — this feature adds no serializer
  or controller code; it passes whatever body the caller supplies straight
  through to the existing Admin API, and prints back whatever the existing
  serializer returns unmodified.
- **IV. Test-Backed**: Vitest is the only applicable framework
  (`packages/cli` has no Ruby or dashboard code). Per the Migration Notes in
  spec.md, full test coverage was not verified exhaustively during this
  brownfield pass — `pnpm test`/`pnpm typecheck`/`pnpm lint` at the
  workspace root remain the enforced gate going forward.
- **V. Translations and Prefixed IDs**: N/A for i18next (this is a terminal
  tool, not `packages/dashboard`/`packages/dashboard-core` UI). Prefixed IDs
  ARE relevant: the CLI passes resource identifiers through to the Admin API
  as opaque strings and never assumes/constructs raw numeric IDs — it
  relies entirely on the API accepting/returning prefixed IDs already.
- **VI. `docs/plans/` for Architectural Changes**: Governed by
  `docs/plans/5.5-admin-api-cli.md` ("`spree api` command group in
  `@spree/cli`... CLI-first ahead of MCP servers; core patch: `SCOPES` on
  `spree:cli:create_api_key`, promotions scopes"). This plan is a
  post-hoc record of that already-shipped design, not a new architectural
  proposal.

No violations — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/042-cli-tooling/
├── spec.md               # Feature specification (this migration)
├── plan.md               # This file
└── tasks.md              # Task breakdown (all marked [x] — already shipped)
```

### Source Code (repository root)

```text
packages/cli/
├── src/
│   ├── commands/
│   │   ├── init.ts           # spree init — first-run setup
│   │   ├── dev.ts             # spree dev — foreground stack, SPREE_PATH guard
│   │   ├── stop.ts            # spree stop
│   │   ├── restart.ts         # spree restart
│   │   ├── update.ts          # spree update — pull image, recreate
│   │   ├── build.ts           # spree build — rebuild dev image, SPREE_PATH guard
│   │   ├── eject.ts           # spree eject — switch to build-from-source
│   │   ├── upgrade.ts         # spree upgrade — bundle/migrate/backfill walk
│   │   ├── logs.ts            # spree logs [worker]
│   │   ├── console.ts         # spree console — Rails console
│   │   ├── open.ts            # spree open — open admin in browser
│   │   ├── seed.ts            # spree seed
│   │   ├── sample-data.ts     # spree sample-data (see specs/026-sample-data-seeds)
│   │   ├── user.ts            # spree user create
│   │   ├── api-key.ts         # spree api-key {create,list,revoke}
│   │   ├── api.ts             # spree api {get,post,patch,delete,endpoints,schema,status}
│   │   ├── auth.ts            # spree auth {login,status,logout}
│   │   ├── generate.ts        # spree generate — spree: prefix inference
│   │   ├── migrate.ts         # spree migrate{,:status,:rollback}
│   │   ├── db.ts               # spree db:{reset,console} — SPREE_PATH guard
│   │   ├── routes.ts           # spree routes
│   │   ├── exec.ts             # spree exec — passthrough
│   │   ├── rails.ts            # spree rails — passthrough (+ c/routes aliases)
│   │   ├── rake.ts             # spree rake — passthrough
│   │   ├── task.ts             # spree task — passthrough
│   │   └── completion.ts       # spree completion {zsh,bash,fish}
│   ├── api/
│   │   ├── body.ts             # readBody() — -d inline/@file/stdin JSON parsing
│   │   ├── output.ts           # printResult(), colorizeJson(), handleApiError()
│   │   └── ping.ts             # pingCredentials()/formatPingStatus() for `auth status`/`api status`
│   ├── config.ts               # 4-layer credential resolution, profile + project credential persistence
│   ├── context.ts               # detectProject(), hasMonorepoSpreePath(), isEjectedProject()
│   ├── docker.ts                 # dockerCompose(), primeBundleVolume(), rakeTask(), asset build/watch
│   ├── constants.ts              # DEFAULT_SPREE_PORT, DEFAULT_ADMIN_EMAIL/PASSWORD, etc.
│   └── types.ts                  # ProjectContext and shared types
└── package.json                  # deps: commander, @clack/prompts, execa, picocolors,
                                   #       console-table-printer, @spree/admin-sdk (workspace:^)

packages/admin-sdk/                # consumed as a library — no changes originate here
```

**Structure Decision**: Single-package feature — everything lives in
`packages/cli`, with `packages/admin-sdk` as a consumed (not modified)
dependency. No backend gem changes, no `packages/dashboard` changes; the
only backend touchpoint is invoking the pre-existing
`spree:cli:create_api_key` Rake task inside the target project's container.

## Complexity Tracking

*No violations — table intentionally empty.*
