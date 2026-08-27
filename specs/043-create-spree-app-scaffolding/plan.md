# Implementation Plan: create-spree-app — Project Scaffolding

**Branch**: `043-create-spree-app-scaffolding` | **Date**: 2026-08-25 | **Spec**: `specs/043-create-spree-app-scaffolding/spec.md`

**Input**: Feature specification from `specs/043-create-spree-app-scaffolding/spec.md`

**Note**: This plan is reverse-engineered (brownfield migration) — it documents the as-built design rather than proposing new work. No `research.md`/`data-model.md`/`contracts/`/`quickstart.md` were generated; the shipped code and `docs/plans/5.4-spree-starter-and-create-spree-app.md` serve as the equivalent artifacts.

## Summary

`packages/create-spree-app` is a `commander`-based CLI (`npx create-spree-app [directory]`) that scaffolds a full-stack Spree project: it clones `spree/spree-starter` into `backend/` and (optionally) `spree/storefront` into `apps/storefront/`, generates root project files (`docker-compose.yml`/`.dev.yml` adapted for the nested `backend/` layout, `.env`, `package.json`, `README.md`, `.gitignore`, `CLAUDE.md`/`AGENTS.md`, `.github/dependabot.yml`), relocates and rewrites the starter's CI workflows so their Ruby steps target `backend/`, installs dependencies, and — unless `--no-start` — hands off to `npx spree init` to boot Docker and seed data. It is the `create-spree-app` half of `docs/plans/5.4-spree-starter-and-create-spree-app.md` (that plan's Phase 2); `spree eject`/`spree init`/etc. themselves live in the separate `@spree/cli` package and are out of scope here.

## Technical Context

**Language/Version**: TypeScript (Node >=20), ESM (`"type": "module"`), built with `tsup`.

**Primary Dependencies**: `commander` (CLI parsing), `@clack/prompts` (interactive prompts), `execa` (git clone / package-manager-install / `npx spree init` subprocess execution), `get-port` (port reallocation), `picocolors` (terminal styling).

**Storage**: N/A — this package does not persist data itself; it clones repos and writes template files to disk. The generated project's own storage (PostgreSQL via the cloned `spree-starter`) is out of scope.

**Testing**: Vitest — `packages/create-spree-app/tests/{backend,scaffold,templates,utils}.test.ts`.

**Target Platform**: Node CLI, invoked via `npx create-spree-app` or as a step inside `@spree/cli`'s own project-creation flow; output is a project consumed by Docker Compose + the generated `backend/` (Rails) and optional `apps/storefront/` (Next.js).

**Project Type**: Monorepo — single TypeScript package (`packages/create-spree-app`). No `spree/*` gem changes (it consumes published/cloned Spree artifacts, doesn't modify them) and no `packages/dashboard*` changes.

**Performance Goals**: Dominated by network I/O (two shallow git clones + package manager installs); no CPU-bound work of note. Not a documented performance-sensitive path.

**Constraints**: Must produce a project usable both with the default prebuilt Docker image (`docker-compose.yml`) and, after `spree eject` (implemented elsewhere, in `@spree/cli`), building from the local `backend/` (`docker-compose.dev.yml`) — the compose-file path rewrite in `scaffold.ts` is what makes the latter possible without further edits. Must not leave partial output on disk if a pre-flight check (non-empty directory, Docker not running) fails.

**Scale/Scope**: Single-purpose scaffolding CLI; ~7 source files + `templates/` (6 files) + 4 test files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Entirely within `packages/create-spree-app`. It depends on `@spree/cli` only as a *generated-project runtime dependency* (written into the scaffolded `package.json`), not as a build-time import — no cross-package reach. Pass.
- **II. Admin API Is the Only Frontend Data Source**: N/A — no admin SPA code here; the generated project's admin is whatever ships inside the cloned `spree-starter`/prebuilt Docker image.
- **III. Read/Write Field Symmetry**: N/A — no Alba serializers or `spree/api` controllers in this feature.
- **IV. Test-Backed**: Vitest specs exist for the four modules with meaningful logic — `backend.test.ts` (CI workflow rewrite, `SKIP_BACKEND_PATHS`), `scaffold.test.ts` (orchestration/compose-file rewrite), `templates.test.ts` (generated file contents), `utils.test.ts` (package manager detection, secret generation). Pass.
- **V. Translations and Prefixed IDs**: N/A — CLI terminal output, not admin SPA UI copy; no API resource IDs are minted by this feature.
- **VI. `docs/plans/` for Architectural Changes**: Already covered — `docs/plans/5.4-spree-starter-and-create-spree-app.md` is the architectural record (status: Done); this migration documents its as-built `create-spree-app` half. One divergence (env var naming) was found and is flagged in spec.md's Migration Notes rather than silently reconciled by this migration. Pass, with a noted follow-up.

Any violation must appear in Complexity Tracking below with justification. None found.

## Project Structure

### Documentation (this feature)

```text
specs/043-create-spree-app-scaffolding/
├── plan.md              # This file
├── spec.md              # Feature specification (migrated)
└── tasks.md             # Task checklist (migrated, all items already shipped)
```

No `research.md`, `data-model.md`, `contracts/`, or `quickstart.md` — this is a reverse-engineered spec for already-built code; `docs/plans/5.4-spree-starter-and-create-spree-app.md` serves as the original design record (Phase 2: "Update create-spree-app").

### Source Code (repository root)

```text
# packages/create-spree-app — project scaffolding CLI
packages/create-spree-app/
├── src/
│   ├── index.ts                    # commander CLI entry — flags, port resolution, error handling
│   ├── prompts.ts                  # runPrompts() — @clack/prompts for any option not passed as a flag
│   ├── scaffold.ts                 # scaffold() — orchestrates the full generation pipeline
│   ├── backend.ts                  # downloadBackend/prepareBackendTemplate/adaptWorkflowForNestedBackend
│   ├── storefront.ts               # downloadStorefront/installRootDeps/installStorefrontDeps/writeStorefrontEnv
│   ├── constants.ts                # BACKEND_REPO, STOREFRONT_REPO, default port/admin creds
│   ├── types.ts                    # ScaffoldOptions, PackageManager
│   ├── utils.ts                    # detectPackageManager, isDockerRunning, generateSecretKeyBase, installCommand
│   └── templates/
│       ├── env.ts                  # envContent() (root .env), storefrontEnvContent() (.env.local)
│       ├── package-json.ts         # rootPackageJsonContent() — @spree/cli scripts surface
│       ├── readme.ts               # readmeContent()
│       ├── gitignore.ts            # gitignoreContent()
│       ├── claude-md.ts            # rootClaudeMdContent(), agentsMdContent()
│       └── dependabot.ts           # dependabotContent()
└── tests/
    ├── backend.test.ts             # SKIP_BACKEND_PATHS, adaptWorkflowForNestedBackend cases
    ├── scaffold.test.ts            # full orchestration, compose-file path rewrite
    ├── templates.test.ts           # generated file content assertions
    └── utils.test.ts               # package manager detection, secret generation
```

**Structure Decision**: Single-package feature, entirely within `packages/create-spree-app`. No `spree/*` gem changes, no `packages/dashboard*` changes — this package's only cross-package touchpoint is writing `@spree/cli` as a dependency into the *generated project's* `package.json` (a runtime/npm-registry relationship, not a monorepo import).

## Complexity Tracking

> No constitution violations identified — table intentionally omitted.
