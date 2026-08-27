---
description: "Task list for @spree/cli — Docker-based Project Management CLI (brownfield migration, already shipped)"
---

# Tasks: @spree/cli — Docker-based Project Management CLI

**Input**: Design documents from `specs/042-cli-tooling/`

**Prerequisites**: plan.md, spec.md

**Tests**: Existing Vitest suite under `packages/cli/` (already shipped; not
re-derived task-by-task here per the "sample, don't read every file"
migration instruction).

**Organization**: Tasks are grouped by command group, mirroring
`packages/cli/src/commands/`. All tasks are marked `[x]` — this is a
reverse-engineered record of an already-built feature, not a forward plan.

## Path Conventions

- CLI commands: `packages/cli/src/commands/*.ts`
- Shared Admin API helpers: `packages/cli/src/api/*.ts`
- Shared infra: `packages/cli/src/{config,context,docker,constants,types}.ts`
- Consumed library: `packages/admin-sdk/` (not modified by this feature)
- Docs: `docs/developer/cli/{quickstart,admin-api}.mdx`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the touched module builds/tests cleanly

- [x] T001 Baseline: `cd packages/cli && pnpm typecheck && pnpm lint` passes
- [x] T002 [P] Baseline: `cd packages/cli && pnpm test` (Vitest) passes
- [x] T003 [P] Confirm `packages/cli` depends on `@spree/admin-sdk` via
      `workspace:^` in `packages/cli/package.json`

**Checkpoint**: Package builds and typechecks cleanly.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure every command group builds on

- [x] T004 Project detection + monorepo-edge guard in
      `packages/cli/src/context.ts` — `detectProject()` (re-roots from a
      stale `create-spree-app` `backend/` wrapper dir),
      `hasMonorepoSpreePath()` (SPREE_PATH guard), `isEjectedProject()`,
      `readPortFromEnv()`
- [x] T005 Docker Compose wrapper in `packages/cli/src/docker.ts` —
      `dockerCompose()`, `primeBundleVolume()` (avoids the cold-volume
      copy-up race between `web`/`worker`), `rakeTask()`, admin asset
      build/watch helpers
- [x] T006 Four-layer credential resolution + persistence in
      `packages/cli/src/config.ts` — `resolveCredentials()` (flags → env →
      project auto-mint → profile), `mintProjectCredentials()`,
      `readConfig()`/`writeConfig()` (`~/.config/spree/config.json`, 0600),
      `readProjectCredentials()`/`writeProjectCredentials()`
      (`.spree/credentials.json`, 0600 + auto-`.gitignore` catch-all)
- [x] T007 Admin API request-body parsing in `packages/cli/src/api/body.ts`
      — `readBody()` (inline JSON / `@file` / stdin `-`, with the `NO_BODY`
      sentinel distinguishing "not given" from a literal `null`)
- [x] T008 Admin API output + error handling in
      `packages/cli/src/api/output.ts` — `printResult()` (JSON/`--format
      table`, TTY-aware coloring), `colorizeJson()`, `handleApiError()`
      (exit 1 for API errors + scope-remediation hint, exit 2 for
      usage/connectivity errors)
- [x] T009 Credential/server reachability check in
      `packages/cli/src/api/ping.ts` — `pingCredentials()`,
      `formatPingStatus()`, `isPingFailure()` (shared by `spree api status`
      and `spree auth status`)

**Checkpoint**: Shared infra ready — every command group below builds on it.

---

## Phase 3: User Story 1 - Boot and operate the Docker dev stack (P1) 🎯 MVP

**Goal**: Full project lifecycle from scaffold to running stack to teardown

**Independent Test**: `spree dev` boots the stack with printed URLs/creds;
`Ctrl+C` stops logs while DBs stay warm; `spree stop` tears down fully; a
`SPREE_PATH`-set project refuses `dev`/`build` with a redirect to
`pnpm server:*`.

### Implementation for User Story 1

- [x] T010 [P] [US1] `spree init` in `packages/cli/src/commands/init.ts` —
      first-run: start Docker, seed DB, generate API key, optional sample
      data (`--no-sample-data`, `--no-open`)
- [x] T011 [US1] `spree dev` in `packages/cli/src/commands/dev.ts` —
      SPREE_PATH guard, bundle-volume priming, foreground `docker compose
      up` with SIGINT ignored so Compose owns shutdown, admin/store URL
      banner (depends on T004, T005)
- [x] T012 [P] [US1] `spree stop` in `packages/cli/src/commands/stop.ts`
- [x] T013 [P] [US1] `spree restart` in `packages/cli/src/commands/restart.ts`
      — recreate `web`+`worker` in place, same image/volumes
- [x] T014 [P] [US1] `spree update` in `packages/cli/src/commands/update.ts`
      — pull latest image, recreate containers, migrations run on startup
- [x] T015 [US1] `spree build` in `packages/cli/src/commands/build.ts` —
      SPREE_PATH guard, requires `spree eject` first (checks for `build:`
      section), `--reset-bundle` (confirm unless `--yes`), `--yes` for CI
      (depends on T004)
- [x] T016 [US1] `spree eject` in `packages/cli/src/commands/eject.ts` —
      switch from prebuilt image to `backend/`-based build-from-source
      compose
- [x] T017 [US1] `spree upgrade` in `packages/cli/src/commands/upgrade.ts` —
      `bundle update` → pending migrations → version-specific backfills;
      `--plan` (DRY_RUN=1), `--to <version>`, `--step <id>`, `--yes`;
      SPREE_PATH guard (depends on T004)
- [x] T018 [P] [US1] `spree logs [worker]` in
      `packages/cli/src/commands/logs.ts`
- [x] T019 [P] [US1] `spree console` in `packages/cli/src/commands/console.ts`
      — Rails console inside the container
- [x] T020 [P] [US1] `spree open` in `packages/cli/src/commands/open.ts` —
      open the admin dashboard in the default browser

**Checkpoint**: Full dev-stack lifecycle functional and independently
testable.

---

## Phase 4: User Story 2 - Call the Admin API generically (P1)

**Goal**: `spree api get|post|patch|delete` against any Admin API v3
endpoint with zero-config local credentials

**Independent Test**: `spree api get /products` inside a project with no
prior credentials auto-mints a read-only key and prints JSON results;
`-q`/`--sort`/`--page`/`--limit`/`--fields`/`--expand` all forward correctly;
write verbs accept `-d` in all three forms and carry `Idempotency-Key`.

### Implementation for User Story 2

- [x] T021 [US2] `spree api get|post|patch|delete <path>` in
      `packages/cli/src/commands/api.ts` — Ransack query building, sort/
      page/limit/fields/expand flags, request-body wiring via `readBody()`
      (T007), automatic `Idempotency-Key` on mutations, result printing via
      `printResult()`/`handleApiError()` (T008), credential resolution via
      `resolveCredentials()` (T006) (depends on T006, T007, T008)
- [x] T022 [US2] TTY-aware JSON coloring vs. compact piped output — covered
      by `printResult()` in `packages/cli/src/api/output.ts` (T008)
- [x] T023 [US2] Scope-denial remediation hint (`spree api-key create
      --scopes <required_scope>`) — covered by `handleApiError()` in
      `packages/cli/src/api/output.ts` (T008)

**Checkpoint**: `spree api` fully functional against local and remote
stores independent of discovery/credential-management commands below.

---

## Phase 5: User Story 3 - Discover endpoints and schemas offline (P2)

**Goal**: `spree api endpoints`/`spree api schema`/`spree completion`/`spree
api status` — all offline except `status`'s reachability ping

**Independent Test**: With the dev stack down, `spree api endpoints
--resource orders` and `spree api schema "POST /orders"` still return data
from the bundled OpenAPI spec snapshot.

### Implementation for User Story 3

- [x] T024 [US3] `spree api endpoints [--resource|--search]` in
      `packages/cli/src/commands/api.ts` — method/path/required-scope
      listing from the bundled OpenAPI spec
- [x] T025 [US3] `spree api schema "<METHOD> <path>"` in
      `packages/cli/src/commands/api.ts` — parameters + request/response
      schema from the bundled spec
- [x] T026 [US3] `spree api status` in `packages/cli/src/commands/api.ts` —
      resolved credential source/base URL/token prefix + reachability via
      `pingCredentials()` (T009)
- [x] T027 [P] [US3] `spree completion {zsh,bash,fish}` in
      `packages/cli/src/commands/completion.ts` — resource paths, Ransack
      predicate stems, scope names, all from the bundled spec

**Checkpoint**: Full offline discovery surface independently testable with
no server running.

---

## Phase 6: User Story 4 - Manage credentials across local/remote stores (P2)

**Goal**: `spree api-key {create,list,revoke}` + `spree auth
{login,status,logout}`

**Independent Test**: Create a scoped secret key locally; log in a `prod`
profile with the key entered only via prompt; confirm `spree api get
/orders --profile prod` targets the remote host with that key.

### Implementation for User Story 4

- [x] T028 [US4] `spree api-key create [--name] [--type] [--scopes]` in
      `packages/cli/src/commands/api-key.ts` — interactive prompts when
      flags omitted, calls into the project's Rake bridge via
      `rakeTable()`/`rakeTask()` (depends on T004, T005)
- [x] T029 [P] [US4] `spree api-key list` in
      `packages/cli/src/commands/api-key.ts`
- [x] T030 [P] [US4] `spree api-key revoke <id>` in
      `packages/cli/src/commands/api-key.ts`
- [x] T031 [US4] `spree auth login --profile <name> --base-url <url>` in
      `packages/cli/src/commands/auth.ts` — secret key via interactive
      prompt only (never a flag), persisted to
      `~/.config/spree/config.json` (T006)
- [x] T032 [P] [US4] `spree auth status` in `packages/cli/src/commands/auth.ts`
      — lists profiles with token prefixes + reachability via
      `pingCredentials()`/`formatPingStatus()` (T009)
- [x] T033 [P] [US4] `spree auth logout --profile <name>` in
      `packages/cli/src/commands/auth.ts`
- [x] T034 [P] [US4] `spree user create [--email] [--password]` in
      `packages/cli/src/commands/user.ts` — create an admin user
      interactively or via flags

**Checkpoint**: Credential lifecycle fully manageable independent of which
command consumes the credentials.

---

## Phase 7: User Story 5 - Dev-workflow passthrough commands (P3)

**Goal**: Generators, migrations, console/routes/db helpers, and raw
passthrough (`exec`/`rails`/`bundle`/`rake`/`task`)

**Independent Test**: `spree generate model Brand name:string` runs
`spree:model`; `spree migrate` installs + runs pending migrations; `spree
routes -g products` filters Rails routes; `spree exec ls -la` reaches the
container verbatim.

### Implementation for User Story 5

- [x] T035 [US5] `spree generate <name> [args...]` in
      `packages/cli/src/commands/generate.ts` — `spree:` auto-prefix
      inference (skips Rails built-ins and already-namespaced names)
- [x] T036 [US5] `spree migrate[:status|:rollback]` in
      `packages/cli/src/commands/migrate.ts` — install pending Spree gem
      migrations + `db:migrate`; status/rollback map to
      `db:migrate:status`/`db:rollback`
- [x] T037 [US5] `spree db:reset [--yes]` / `spree db:console` in
      `packages/cli/src/commands/db.ts` — destructive reset with
      confirmation gate, SPREE_PATH guard on `reset` (depends on T004)
- [x] T038 [US5] `spree routes [rails-flags...]` in
      `packages/cli/src/commands/routes.ts` — passthrough to `bin/rails
      routes`
- [x] T039 [P] [US5] `spree exec <cmd...>` in
      `packages/cli/src/commands/exec.ts` — arbitrary passthrough inside
      `web`
- [x] T040 [P] [US5] `spree rails <cmd...>` in
      `packages/cli/src/commands/rails.ts` — `bin/rails` passthrough (`c`
      aliases `console`, `routes` aliases `spree routes`)
- [x] T041 [P] [US5] `spree bundle <cmd...>` in
      `packages/cli/src/commands/bundle.ts` — `bundle` passthrough into the
      `bundle_cache` volume
- [x] T042 [P] [US5] `spree rake <cmd...>` in
      `packages/cli/src/commands/rake.ts` — Rake task passthrough
- [x] T043 [P] [US5] `spree task <name...>` in
      `packages/cli/src/commands/task.ts` — shortcut for `bin/rails <task>`
- [x] T044 [US5] `spree seed` in `packages/cli/src/commands/seed.ts` and
      `spree sample-data` in `packages/cli/src/commands/sample-data.ts` —
      thin wrappers; underlying seed/sample-data model covered by
      `specs/026-sample-data-seeds` (not re-specified here)

**Checkpoint**: All documented `spree` subcommands from
`docs/developer/cli/quickstart.mdx` accounted for.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T045 [P] Docs cross-checked against implementation:
      `docs/developer/cli/quickstart.mdx`,
      `docs/developer/cli/admin-api.mdx`
- [x] T046 Full package suite: `cd packages/cli && pnpm typecheck && pnpm
      lint && pnpm test`
- [x] T047 Confirm `docs/plans/5.5-admin-api-cli.md` reflects the shipped
      `spree api` design (scopes on `spree:cli:create_api_key`, promotions
      scopes) — no drift between plan and implementation found during this
      migration pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (`context.ts`,
  `docker.ts`) — no dependency on other stories
- **User Story 2 (Phase 4)**: Depends on Foundational (`config.ts`,
  `api/body.ts`, `api/output.ts`) — independent of US1/US3/US4/US5
- **User Story 3 (Phase 5)**: Depends on Foundational + reuses US2's
  `commands/api.ts` module (same file, additive subcommands) but is
  independently testable (works with the server down)
- **User Story 4 (Phase 6)**: Depends on Foundational (`config.ts`,
  `docker.ts` for the Rake bridge) — independent of US1/US2/US3/US5
- **User Story 5 (Phase 7)**: Depends on Foundational (`context.ts`,
  `docker.ts`) — independent of US1-US4
- **Polish (Phase 8)**: Depends on all stories being complete

### Parallel Opportunities

- All `[P]`-marked tasks within a phase touch different command files and
  can be worked/reviewed independently
- Phases 3-7 (US1-US5) have no cross-story file dependencies once Phase 2
  is complete — the only shared touch point is `commands/api.ts` between
  Phase 4 (US2) and Phase 5 (US3), which is additive rather than
  conflicting

## Notes

- This tasks.md reflects an already-shipped feature (brownfield migration
  per `/speckit.brownfield.migrate`) — all tasks are checked off as a
  historical record, not a forward-looking plan.
- No new tasks should be added here to build new functionality; use a new
  spec-kit feature branch for CLI enhancements going forward, referencing
  this spec for existing behavior.
