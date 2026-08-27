---

description: "Task list template for feature implementation"
---

# Tasks: create-spree-app — Project Scaffolding

**Input**: Design documents from `specs/043-create-spree-app-scaffolding/`

**Prerequisites**: plan.md, spec.md

**Tests**: Included — Vitest specs already exist for every module with meaningful logic and are treated as required, not optional.

**Organization**: Reverse-engineered (brownfield migration) — every task below documents already-shipped work. All tasks are marked complete; this file is the historical record of what was built, organized to match the spec's user stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Different files, no dependencies
- **[Story]**: Which user story (spec.md) this task maps to
- File paths are the real shipped locations, not placeholders

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `packages/create-spree-app` builds: `cd packages/create-spree-app && pnpm build` (tsup, CJS+ESM)
- [x] T002 [P] Confirm test suite baseline: `cd packages/create-spree-app && pnpm test` (Vitest)
- [x] T003 [P] Confirm typecheck/lint baseline: `cd packages/create-spree-app && pnpm typecheck && pnpm lint`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared constants, types, and utilities every generation step depends on

- [x] T004 Define `ScaffoldOptions`/`PackageManager` types — `packages/create-spree-app/src/types.ts`
- [x] T005 [P] Define `BACKEND_REPO`/`STOREFRONT_REPO`/default port/admin credential constants — `packages/create-spree-app/src/constants.ts`
- [x] T006 [P] Implement `detectPackageManager`, `isDockerRunning`, `generateSecretKeyBase`, `installCommand`, `runCommand` — `packages/create-spree-app/src/utils.ts`

**Checkpoint**: Shared types/constants/utils exist; the clone and orchestration steps can now be built on top.

---

## Phase 3: User Story 1 - Scaffold a full-stack Spree project in one command (Priority: P1)

**Goal**: `npx create-spree-app <dir>` produces a working project with `backend/`, optional `apps/storefront/`, and all root project files, then optionally boots it.

**Independent Test**: `npx create-spree-app ./my-store --no-storefront --no-start` in an empty directory produces `backend/` (git-metadata-free spree-starter clone) and root `docker-compose.yml`/`.env`/`package.json`/`README.md`, with `package.json` declaring `@spree/cli`.

### Tests for User Story 1

- [x] T007 [P] [US1] `scaffold()` orchestration spec (non-empty-directory rejection, Docker pre-flight, file generation, install invocation) — `packages/create-spree-app/tests/scaffold.test.ts`
- [x] T008 [P] [US1] Template content specs (`.env`, `package.json`, `README.md`, `.gitignore`, `CLAUDE.md`/`AGENTS.md`, dependabot) — `packages/create-spree-app/tests/templates.test.ts`
- [x] T009 [P] [US1] Package-manager detection / secret generation specs — `packages/create-spree-app/tests/utils.test.ts`

### Implementation for User Story 1

- [x] T010 [US1] `downloadBackend()` — shallow clone `spree/spree-starter` into `<projectDir>/backend`, strip `.git/` — `packages/create-spree-app/src/backend.ts`
- [x] T011 [US1] `downloadStorefront()`/`installStorefrontDeps()`/`writeStorefrontEnv()` — optional storefront clone + `.env.local` — `packages/create-spree-app/src/storefront.ts` (depends on T010 for project layout)
- [x] T012 [US1] `runPrompts()` — interactive prompts for directory/storefront/sampleData/start, each skippable via CLI flag — `packages/create-spree-app/src/prompts.ts`
- [x] T013 [US1] `envContent()`, `storefrontEnvContent()`, `rootPackageJsonContent()`, `readmeContent()`, `gitignoreContent()`, `rootClaudeMdContent()`/`agentsMdContent()`, `dependabotContent()` — `packages/create-spree-app/src/templates/*.ts`
- [x] T014 [US1] `scaffold()` orchestration: pre-flight checks → backend clone → root file generation → root deps install → optional storefront → optional `npx spree init` handoff or manual next-steps printout — `packages/create-spree-app/src/scaffold.ts` (depends on T010-T013)
- [x] T015 [US1] CLI entry: `commander` flags, port resolution via `get-port`, error/cancellation handling — `packages/create-spree-app/src/index.ts` (depends on T012, T014)

**Checkpoint**: US1 independently functional — full scaffold pipeline produces a working project end-to-end.

---

## Phase 4: User Story 2 - Generated project's backend is customizable via eject (Priority: P2)

**Goal**: `docker-compose.dev.yml` is pre-adjusted at generation time so `spree eject` (implemented in `@spree/cli`) works without further edits.

**Independent Test**: Inspect a freshly scaffolded `docker-compose.dev.yml` — build `context` is `./backend`, bind-mount is `./backend:/rails`; the starter's own compose files under `backend/` are gone.

### Implementation for User Story 2

- [x] T016 [US2] Copy `backend/docker-compose.yml` verbatim to project root; copy `backend/docker-compose.dev.yml` to project root rewriting `context: .` → `context: ./backend` and `- .:/rails` → `- ./backend:/rails` — `packages/create-spree-app/src/scaffold.ts`
- [x] T017 [US2] Delete both compose files from `backend/` after the rewritten root copies are written, so the CLI never targets the stale in-place copies — `packages/create-spree-app/src/scaffold.ts`

**Checkpoint**: US1 + US2 independently functional — the generated project is eject-ready without further edits.

---

## Phase 5: User Story 3 - CI workflow relocates cleanly into the nested layout (Priority: P3)

**Goal**: The starter's `.github/workflows/*.yml` are relocated to the project root and rewritten so Ruby steps target `backend/`; starter-only files are dropped instead of relocated.

**Independent Test**: Scaffold a project; any relocated workflow using `ruby/setup-ruby` has `defaults: run: working-directory: backend` at the job level and `with: working-directory: backend` on the `ruby/setup-ruby` step; non-Ruby workflows pass through unchanged; `release.yml` and starter `README.md` are absent; `backend/.github/` is gone.

### Tests for User Story 3

- [x] T018 [P] [US3] `adaptWorkflowForNestedBackend` specs (Ruby workflow rewritten, non-Ruby workflow untouched, malformed/missing `runs-on:` edge case) — `packages/create-spree-app/tests/backend.test.ts`
- [x] T019 [P] [US3] `prepareBackendTemplate`/`SKIP_BACKEND_PATHS` specs (starter `README.md` + `release.yml` removed, `backend/.github/` removed after relocation) — `packages/create-spree-app/tests/backend.test.ts`

### Implementation for User Story 3

- [x] T020 [US3] `SKIP_BACKEND_PATHS` constant + removal loop in `prepareBackendTemplate` — `packages/create-spree-app/src/backend.ts`
- [x] T021 [US3] Relocate `backend/.github/workflows/*.yml` to `<projectDir>/.github/workflows/`, running each through `adaptWorkflowForNestedBackend`; then delete `backend/.github/` entirely — `packages/create-spree-app/src/backend.ts` (depends on T020)
- [x] T022 [US3] `adaptWorkflowForNestedBackend`: regex-insert job-level `defaults: run: working-directory: backend` anchored on the first `runs-on:` line; regex-insert `with: working-directory: backend` on the `ruby/setup-ruby` step; no-op for workflows without `ruby/setup-ruby` — `packages/create-spree-app/src/backend.ts`

**Checkpoint**: US1-US3 independently functional — CI is usable in the generated project's nested layout.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T023 [P] Package metadata: `bin`, `files`, `changeset` release scripts, keywords — `packages/create-spree-app/package.json`
- [x] T024 Full package test/typecheck/lint suite green: `cd packages/create-spree-app && pnpm test && pnpm typecheck && pnpm lint`
- [x] T025 This migration: `specs/043-create-spree-app-scaffolding/{spec.md,plan.md,tasks.md}` written to close the SDD gap for already-shipped work; one divergence from `docs/plans/5.4-spree-starter-and-create-spree-app.md` (`.env`'s `SPREE_PORT` vs. the plan's mandated `PORT`) flagged in spec.md Migration Notes for a future reconciliation pass — not resolved by this migration

---

## Dependencies & Execution Order

- **Foundational (Phase 2)** — types/constants/utils are prerequisites for every subsequent phase.
- **US1 (Phase 3)** depends on Phase 2 only; it is the end-to-end pipeline that US2/US3 refine specific steps of.
- **US2 (Phase 4)** depends on US1's `scaffold()`/`downloadBackend()` existing (T010, T014) — it modifies the compose-file handling within that same pipeline.
- **US3 (Phase 5)** depends on US1's `downloadBackend()` existing (T010) — it modifies the CI-relocation handling within `prepareBackendTemplate`. Independent of US2 (different files: compose vs. `.github/workflows`).

## Notes

- This tasks.md is a **reverse-engineered historical record** — all tasks are complete because the feature is already shipped. There is no pending work tracked here; open items live in spec.md's Migration Notes instead (env var naming divergence from the governing plan doc, unverified `@spree/cli eject` implementation, undocumented `@spree/docs` dependency, undocumented broader `package.json` scripts surface, no automated guard against the starter's compose-file structure changing upstream).
