# Feature Specification: create-spree-app — Project Scaffolding

**Feature Branch**: `043-create-spree-app-scaffolding`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing code (brownfield migration) — no original feature request survives; behavior below is inferred from `packages/create-spree-app` (backend.ts, storefront.ts, scaffold.ts, prompts.ts, index.ts, templates/) and `docs/plans/5.4-spree-starter-and-create-spree-app.md`, which describes the architectural decision this package implements.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scaffold a full-stack Spree project in one command (Priority: P1)

A developer runs `npx create-spree-app my-store` (or is later guided there via `@spree/cli`). The CLI prompts for storefront inclusion, sample data, and whether to start Docker now, then clones `spree/spree-starter` into `backend/`, clones `spree/storefront` into `apps/storefront/` (if selected), generates root project files (`.env`, `package.json`, `README.md`, `.gitignore`, `CLAUDE.md`, `AGENTS.md`, `.github/dependabot.yml`, `docker-compose.yml`/`docker-compose.dev.yml` adapted for the nested `backend/` layout), installs root dependencies (`@spree/cli`), and — unless `--no-start` — runs `npx spree init` to boot Docker services and seed the database.

**Why this priority**: This is the entire purpose of the package — turning "I want to try Spree" into a running local project with a single command, matching the "quick-start to real development" goal in `docs/plans/5.4-spree-starter-and-create-spree-app.md`.

**Independent Test**: Run `npx create-spree-app ./my-store --no-storefront --no-start` in an empty directory → a `my-store/backend/` directory exists (spree-starter clone, no `.git/`), root `docker-compose.yml`/`.env`/`package.json`/`README.md` exist, and `package.json` declares `@spree/cli` as a dependency with `spree dev`/`spree eject`/etc. scripts.

**Acceptance Scenarios**:

1. **Given** an empty or non-existent target directory, **When** `npx create-spree-app <dir>` runs to completion, **Then** `<dir>/backend/` contains a git-metadata-free clone of `spree/spree-starter` and `<dir>/package.json`, `.env`, `docker-compose.yml`, `docker-compose.dev.yml`, `README.md`, `.gitignore`, `CLAUDE.md`, `AGENTS.md`, `.github/dependabot.yml` all exist at the project root.
2. **Given** the storefront prompt/flag is affirmative, **When** scaffolding completes, **Then** `<dir>/apps/storefront/` contains a git-metadata-free clone of `spree/storefront` with dependencies installed and `.env.local` written with `SPREE_API_URL`/`SPREE_PUBLISHABLE_KEY`.
3. **Given** the target directory already exists and is non-empty, **When** the command runs, **Then** it cancels with an error naming the directory, before any file is written.
4. **Given** `--no-start` is passed, **When** scaffolding completes, **Then** no `npx spree init` is invoked and the CLI prints manual next-steps (`npx spree dev`, admin credentials, `npx spree eject`) instead.

---

### User Story 2 - Generated project's backend is customizable via eject (Priority: P2)

The generated project runs against a prebuilt Docker image by default (`docker-compose.yml`), but the developer can drop into full backend customization at any time by running `npx spree eject`, which swaps to building from the local `backend/` directory (`docker-compose.dev.yml`) — without re-scaffolding the project.

**Why this priority**: Per `docs/plans/5.4-spree-starter-and-create-spree-app.md` problem statement #3/#4, most real users eventually need to add a gem, override a controller, or add a migration; the scaffolding must set up that path from day one even though the eject command itself lives in `@spree/cli`, not this package.

**Independent Test**: After scaffolding, inspect `docker-compose.dev.yml` — its `x-app` build context/bind-mount both point at `./backend` (rewritten from the starter's own `.`/`.:/rails`, since in the starter repo the compose file lives in the Rails app root, but here the app lives under `backend/`).

**Acceptance Scenarios**:

1. **Given** a freshly scaffolded project, **When** `docker-compose.dev.yml` is inspected, **Then** its build `context` is `./backend` and its source bind-mount is `./backend:/rails` (not `.`/`.:/rails`).
2. **Given** the backend clone step completed, **When** the generated project's own `docker-compose.yml`/`docker-compose.dev.yml` are compared to the ones the starter repo ships, **Then** the starter's copies inside `backend/` have been deleted (only the root, path-adjusted copies remain) so the CLI never targets a stale compose file if invoked from `backend/`.

---

### User Story 3 - CI workflow relocates cleanly into the nested layout (Priority: P3)

`spree/spree-starter` ships its own `.github/workflows/*.yml` authored for a repo where the Rails app *is* the root. Once cloned into the wrapper project's `backend/` subdirectory, those workflows would break (wrong working directory for `ruby/setup-ruby`, `bundle`, `bin/rails`). Scaffolding relocates and rewrites them to the project root, targeting `backend/`.

**Why this priority**: Without this, a freshly scaffolded project's CI is silently broken (green checkmark on a job that never ran the intended steps, or a hard failure finding `Gemfile`/`.ruby-version`) — lower priority than P1/P2 because it only affects CI, not local dev, but still part of what makes the generated project usable "out of the box."

**Independent Test**: Scaffold a project, inspect `.github/workflows/*.yml` at the project root — any workflow using `ruby/setup-ruby` has a job-level `defaults: run: working-directory: backend` and the `ruby/setup-ruby` step itself has `with: working-directory: backend`; non-Ruby workflows are untouched.

**Acceptance Scenarios**:

1. **Given** the starter's CI workflow uses `ruby/setup-ruby`, **When** `adaptWorkflowForNestedBackend` processes it, **Then** a `defaults: run: working-directory: backend` block is inserted at the job's indentation (anchored on the first `runs-on:` line) and the `ruby/setup-ruby` step gets its own `with: working-directory: backend`.
2. **Given** a workflow that does not reference `ruby/setup-ruby` (e.g., a purely Docker-based workflow), **When** processed, **Then** its content is returned unchanged.
3. **Given** the starter's `release.yml` (publishes the official `ghcr.io/spree/spree` image — not meaningful for a user's own project) and root `README.md` (the wrapper supplies its own), **When** scaffolding runs, **Then** both are deleted from the cloned `backend/` (`SKIP_BACKEND_PATHS`) rather than relocated.
4. **Given** the starter's `.github/dependabot.yml` (scoped to the standalone starter repo), **When** scaffolding completes, **Then** it is not present under `backend/.github/` — the whole `backend/.github/` directory is removed after workflows are relocated, and the wrapper's own root `.github/dependabot.yml` (covering `/`, `/backend`, and the storefront) is written instead.

---

### Edge Cases

- Target directory exists but is empty: allowed, scaffolding proceeds (only a *non-empty* existing directory is rejected).
- `--no-start` requested but Docker isn't running: no pre-flight Docker check occurs (the check only runs when `start` is true), so scaffolding still completes — the generated project is left for the user to start manually.
- `start: true` requested but Docker isn't running: pre-flight check fails fast (`isDockerRunning()`) and the whole command cancels *before* any file is written, so no partial project is left on disk from a Docker-availability failure.
- A workflow file matches `ruby/setup-ruby` but has no visible `runs-on:` line (malformed): the `runs-on:`-anchored regex replace is a no-op for that line, but the `with:` block after `ruby/setup-ruby` is still rewritten — the two rewrites are independent regex passes, not both-or-nothing.
- Preferred port already in use: `create-spree-app` (via `get-port`) silently reallocates to the next free port in `[preferred, preferred+100)` and warns the user, rather than failing.
- Package manager not explicitly flagged: detected from `npm_config_user_agent` (defaults to `npm` if undetectable), not prompted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST clone `spree/spree-starter` (`BACKEND_REPO`) into `<projectDir>/backend` with `--depth 1` and strip its `.git/` directory, producing a git-metadata-free copy.
- **FR-002**: System MUST remove starter-only files that don't belong in a generated project (`SKIP_BACKEND_PATHS`: `README.md`, `.github/workflows/release.yml`) from the cloned `backend/`.
- **FR-003**: System MUST relocate the starter's remaining `.github/workflows/*.yml` files to the wrapper project's root `.github/workflows/`, rewriting any workflow that references `ruby/setup-ruby` to run its steps against `backend/` (job-level `defaults: run: working-directory: backend` plus a `with: working-directory: backend` on the `ruby/setup-ruby` step itself); non-Ruby workflows pass through unchanged.
- **FR-004**: System MUST delete the starter's entire `backend/.github/` directory after relocating workflows (its only other content, a starter-scoped `dependabot.yml`, would otherwise duplicate/conflict with the wrapper's own root `.github/dependabot.yml`).
- **FR-005**: System MUST copy the starter's `docker-compose.yml` verbatim to the project root, and MUST copy `docker-compose.dev.yml` with its build `context` rewritten from `.` to `./backend` and its bind-mount rewritten from `.:/rails` to `./backend:/rails`, then delete both compose files from `backend/` so the CLI never targets the stale in-place copies.
- **FR-006**: System MUST generate root project files: `.env` (with a freshly generated 128-hex-char `SECRET_KEY_BASE` via `crypto.randomBytes(64)` and the resolved port), `package.json` (declares `@spree/cli` + `@spree/docs` deps and the `spree dev`/`stop`/`eject`/`logs`/`seed`/`console`/`api`/`auth`/etc. scripts), `README.md`, `.gitignore`, `CLAUDE.md`, `AGENTS.md`, and `.github/dependabot.yml`.
- **FR-007**: System MUST install root dependencies (`@spree/cli`) using the detected or user-specified package manager (`npm`/`yarn`/`pnpm`) before optionally proceeding to storefront setup.
- **FR-008**: System MUST, when the storefront option is enabled (default `true`), clone `spree/storefront` (`STOREFRONT_REPO`) into `<projectDir>/apps/storefront`, strip its `.git/`, write `.env.local` (`SPREE_API_URL`, `SPREE_PUBLISHABLE_KEY` placeholder), and install its dependencies.
- **FR-009**: System MUST prompt interactively (via `@clack/prompts`) for any option not supplied as a CLI flag: target directory, storefront inclusion, sample data inclusion, and whether to start Docker now — each prompt is skippable via `--no-storefront`/`--no-sample-data`/`--no-start`/positional directory argument.
- **FR-010**: System MUST reject scaffolding into an existing, non-empty directory before writing any files; an existing empty directory is acceptable.
- **FR-011**: System MUST, when `start` is true, verify Docker is running before writing any files, and cancel the whole command (no partial output) if it is not.
- **FR-012**: System MUST, when `start` is true, invoke `npx spree init` (passing `--no-sample-data` if sample data was declined) after all files/dependencies are in place, to boot Docker services and seed the database; when `start` is false, it MUST instead print manual next-steps (backend dev command, storefront dev command if applicable, admin URL/credentials, `spree eject` hint, agent-skills hint).
- **FR-013**: System MUST reallocate to the next free port (via `get-port`, scanning `[preferred, preferred+100)`) and warn the user when the requested/default port is already in use, rather than failing.

### Key Entities

- **`ScaffoldOptions`**: `directory`, `storefront` (boolean), `sampleData` (boolean), `start` (boolean), `packageManager` (`'npm' | 'yarn' | 'pnpm'`), `port` (number) — the fully-resolved set of choices (from flags and/or prompts) driving one scaffold run.
- **Generated project root**: `backend/` (spree-starter clone, customizable after `spree eject`), `apps/storefront/` (optional Next.js storefront clone), plus root-level `docker-compose.yml`/`docker-compose.dev.yml`/`.env`/`package.json`/`README.md`/`.gitignore`/`CLAUDE.md`/`AGENTS.md`/`.github/{workflows,dependabot.yml}`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `packages/create-spree-app` | Yes | Entire package: `backend.ts` (starter clone + CI relocation), `storefront.ts` (storefront clone + env), `scaffold.ts` (orchestration), `prompts.ts`, `index.ts` (CLI entry), `utils.ts`, `templates/*.ts` (generated file contents) |
| `packages/cli` | Yes (consumer, not modified here) | Generated project's `package.json` scripts (`spree dev`, `spree eject`, `spree init`, etc.) all shell out to `@spree/cli`, which this package installs as a dependency but does not implement |
| `spree/core` / `spree/api` | No | This feature scaffolds a *consumer* of Spree gems (via the cloned `spree-starter`'s Gemfile), it does not modify the gems themselves |
| `packages/dashboard` | No | Not touched — generated projects use the prebuilt Docker image's bundled admin until 6.0 adds a separate `apps/admin/` |
| `docs/plans/` | Yes (already governs this area) | `docs/plans/5.4-spree-starter-and-create-spree-app.md` — this feature is that plan's as-built state for the `create-spree-app` half (Phase 2 in the plan's Migration Path) |

### API Contract *(include if feature touches spree/api)*

N/A — this feature is a project-scaffolding CLI; it does not add or change any `spree/api` endpoint. It generates a project that later talks to the Store/Admin API v3 once booted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `npx create-spree-app <dir>` (defaults, Docker running) produces a project where `cd <dir> && npx spree dev` boots a working Spree backend reachable at `http://localhost:<port>/admin` with the documented seed credentials.
- **SC-002**: 100% of relocated CI workflows referencing `ruby/setup-ruby` run their Ruby steps against `backend/`, not the project root (verified by the `working-directory: backend` rewrite being present on both the job defaults and the `ruby/setup-ruby` step).
- **SC-003**: No file is written to disk when either pre-flight check fails (non-empty target directory, or Docker required-but-not-running) — scaffolding is all-or-nothing with respect to those two gates.
- **SC-004**: A user who runs `npx spree eject` on a freshly scaffolded project ends up building from their own edited `backend/` without needing to re-run `create-spree-app` or hand-edit `docker-compose.dev.yml`'s context/mount paths (already correct at generation time).

## Assumptions

- `spree/spree-starter` and `spree/storefront` are assumed to always be reachable public GitHub repos at the URLs in `constants.ts`; no offline/vendored fallback exists.
- The starter repo's own `docker-compose.yml`/`docker-compose.dev.yml` are assumed to always exist at its root with the exact `context: .` / `- .:/rails` strings the string-replace in `scaffold.ts` targets — a structural change to the starter's compose files without a corresponding create-spree-app update would silently fail to rewrite the path (no validation that the replace actually matched).
- `spree eject` (referenced in generated `README.md`/`package.json` scripts and the no-Docker-start success message) is assumed to be implemented in `@spree/cli`, per `docs/plans/5.4-spree-starter-and-create-spree-app.md` Phase 3 — out of scope for this package, which only sets up the pre-eject/post-eject compose files.
- The 128-hex-char `SECRET_KEY_BASE` and `.env`'s `SPREE_PORT`/`SPREE_VERSION_TAG` keys are assumed sufficient for local/dev use; production secret rotation is out of scope.

## Migration Notes

Gaps and discrepancies surfaced during reverse-engineering, relative to `docs/plans/5.4-spree-starter-and-create-spree-app.md`:

1. **Env var naming diverges from the plan's own stated constraint.** The plan's "Constraints on Current Work" section explicitly says: *"Environment variable names must match `docs/developer/deployment/environment_variables.mdx`... don't use `SPREE_PORT` — use `PORT`."* The shipped `templates/env.ts` (`envContent`) writes `SPREE_PORT=${port}` and `SPREE_VERSION_TAG=latest`, not the `PORT`/`SECRET_KEY_BASE`-only `.env` the plan's "`.env` (generated by create-spree-app)" design section shows. This is a direct deviation from an explicit, still-active constraint in the plan doc — flagged for reconciliation rather than silently accepted as the new source of truth.
2. **`spree eject`'s existence in `@spree/cli` was not verified in this migration.** This spec documents create-spree-app's half (the compose files being eject-ready) per the plan's Phase 2/3 split; whether `packages/cli/src/commands/eject.ts` matches the plan's sketch is out of scope here and belongs to a `packages/cli` migration.
3. **Root `package.json`'s script surface is broader than the plan anticipated.** The plan's Phase 4 root-`package.json` sketch (for the *monorepo*, not generated projects) lists `server:setup`/`server:dev`/etc.; the actual generated-project `package.json` (`templates/package-json.ts`) exposes a different, larger set (`dev`, `stop`, `down`, `update`, `eject`, `logs`, `logs:worker`, `seed`, `load-sample-data`, `console`, `api`, `auth`, `api-key`) that isn't documented anywhere in the plan — all of it delegates to `@spree/cli` subcommands not detailed in this plan doc.
4. **`@spree/docs` dependency is unexplained.** Generated `package.json` depends on `@spree/docs@latest` alongside `@spree/cli` — no reference to this package appears in `docs/plans/5.4-spree-starter-and-create-spree-app.md`; likely added later for local doc/CLI-help serving, but undocumented.
5. **No automated verification that the compose-file string replace matched.** `scaffold.ts`'s `.replace('context: .', 'context: ./backend')` etc. silently no-ops if the starter's compose file structure changes upstream — worth a follow-up assertion/test rather than a design change, since this migration only documents current behavior.
