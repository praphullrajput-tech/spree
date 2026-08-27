# Feature Specification: @spree/cli — Docker-based Project Management CLI

**Feature Branch**: `042-cli-tooling`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — `packages/cli/src/commands/*.ts`, `packages/cli/src/api/*.ts`, `packages/cli/src/config.ts`, `packages/cli/src/context.ts`, `packages/cli/src/docker.ts`, `docs/developer/cli/quickstart.mdx`, `docs/developer/cli/admin-api.mdx`.

## User Scenarios & Testing *(mandatory)*

This is developer/ops tooling, not an end-user storefront or admin feature.
The "user" is a developer managing a Spree project via the `spree` CLI —
booting the Docker dev stack, running generators/migrations, and calling the
Admin API directly from the terminal (including as the tool an AI coding
agent drives).

### User Story 1 - Boot and operate the Docker dev stack (Priority: P1)

A developer scaffolds a project with `create-spree-app` and needs to bring
the stack up, iterate on backend code, and tear it down, without hand-writing
`docker compose` invocations.

**Why this priority**: Nothing else in the CLI is reachable without a
running project — `spree dev`/`spree stop`/`spree restart` are the daily
driver commands.

**Independent Test**: In a scaffolded project directory, run `spree dev`,
confirm the admin dashboard and Store API are reachable at the printed
URLs, `Ctrl+C` stops streaming logs while databases stay warm, then
`spree stop` tears everything down.

**Acceptance Scenarios**:

1. **Given** a project directory with `docker-compose.yml`, **When** `spree dev`
   runs, **Then** the CLI primes the shared `bundle_cache` volume by bringing
   up `web` alone first (avoiding a copy-up race between `web` and `worker`),
   then runs `docker compose up` in the foreground streaming web + worker
   logs, printing the admin dashboard URL/credentials and Store API URL.
2. **Given** the stack is running, **When** the developer presses `Ctrl+C`,
   **Then** the CLI ignores `SIGINT` itself so Compose owns graceful
   shutdown of `web`/`worker`, while `postgres`/`redis`/`meilisearch` stay up
   for a fast next boot.
3. **Given** a project whose `.env` sets `SPREE_PATH` (a monorepo edge
   project), **When** `spree dev` or `spree build` is invoked, **Then** the
   command refuses and points the developer at `pnpm server:dev` /
   `pnpm server:build` instead — the project-local compose file is not the
   one actually running.
4. **Given** `spree eject` has swapped in a build-from-source compose,
   **When** `spree build` runs, **Then** the image rebuilds from
   `backend/Dockerfile`; without ejecting first, `spree build` errors since
   there is no `build:` section to rebuild.

---

### User Story 2 - Call the Admin API generically from the terminal (Priority: P1)

A developer (or an AI agent with shell access) wants to read and write store
data — products, orders, refunds — without writing a bespoke script, using
the same conventions whether working locally or against a deployed store.

**Why this priority**: `spree api` is the CLI's other pillar per the
quickstart ("Manages your project" / "Calls the Admin API") and is
explicitly designed to be agent-driven.

**Independent Test**: Inside a project with the dev stack running, execute
`spree api get /products` with zero prior configuration and confirm a
read-only key is auto-minted, persisted to `.spree/credentials.json`, and
JSON results print to stdout.

**Acceptance Scenarios**:

1. **Given** no credentials exist anywhere, **When** `spree api get /products`
   runs inside a project with the dev stack up, **Then** the CLI mints a
   `read_all`-scoped secret key via `spree:cli:create_api_key`, persists it
   to `.spree/credentials.json` (0600, gitignored via an auto-created
   catch-all `.gitignore`), and uses it for the request.
2. **Given** credentials resolve, **When** `-q key=value` Ransack predicates,
   `--sort`, `--page`, `--limit`, `--fields`, and `--expand` are passed,
   **Then** they are forwarded as query params; `--fields` always includes
   `id` even if not named.
3. **Given** a write verb (`post`/`patch`/`delete`), **When** `-d` is a
   literal JSON string, `@file.json`, or `-` (stdin), **Then** the body is
   parsed accordingly and the request carries an automatic
   `Idempotency-Key`.
4. **Given** stdout is a TTY, **When** a result prints, **Then** JSON is
   indented and syntax-colored; **given** stdout is piped/redirected,
   **then** JSON is compact and uncolored (safe for `jq`).
5. **Given** an API error response, **When** it is a scope denial, **Then**
   the CLI prints the Stripe-style error envelope to stderr, exits `1`, and
   appends a remediation hint naming the exact `spree api-key create --scopes
   <missing_scope>` command; usage/configuration failures (bad credentials,
   unreachable host) exit `2` instead.
6. **Given** `--base-url`/`--api-key` flags, `SPREE_API_KEY`/`SPREE_BASE_URL`
   env vars, project-minted credentials, and a saved `--profile` could all
   apply, **When** credentials resolve, **Then** they resolve through the
   four layers in order (flags → env → project → profile) with host and key
   always drawn from the *same* layer — a saved/minted key is never silently
   re-pointed at a host from a different layer, except via an explicit
   `--base-url`/`--api-key` flag.

---

### User Story 3 - Discover endpoints and schemas offline (Priority: P2)

A developer or agent unfamiliar with the current Admin API surface wants to
find the right endpoint and see its request/response shape without leaving
the terminal or needing network access to the spec host.

**Why this priority**: Removes the "load the entire API surface up front"
tax for agents and humans alike; makes `spree api` self-documenting.

**Independent Test**: Run `spree api endpoints --resource orders` and
`spree api schema "POST /orders"` with the dev stack down (no server
reachability needed) and confirm both return data from the CLI's bundled
OpenAPI spec snapshot.

**Acceptance Scenarios**:

1. **Given** the bundled OpenAPI spec, **When** `spree api endpoints
   --resource orders` or `--search "gift card"` runs, **Then** matching
   endpoints print with method, path, and required scope — no network call.
2. **Given** a method + path, **When** `spree api schema "POST /orders"`
   runs, **Then** the parameters and request/response schema print from the
   bundled spec.
3. **Given** shell completion is wired up (`spree completion {zsh,bash,fish}`),
   **When** the developer tab-completes a resource path or Ransack predicate
   stem, **Then** suggestions come from the same bundled spec, offline.
4. **Given** `spree api status` runs, **When** credentials resolve, **Then**
   it prints the resolved source, base URL, token prefix, and server
   reachability.

---

### User Story 4 - Manage credentials across local and remote stores (Priority: P2)

A developer needs to create/revoke API keys for a local project and save
credentials for one or more remote (staging/production) stores as named
profiles, switching between them without re-typing secrets.

**Why this priority**: Required before `spree api` is usable against
anything but the local dev stack, and before any write-scoped operation is
possible (auto-minted keys are read-only by design).

**Independent Test**: Run `spree api-key create --type secret --scopes
read_orders,write_products` against a local project, then `spree auth login
--profile prod --base-url https://store.example.com` (prompted for the key,
never via flag) and confirm `spree api get /orders --profile prod` targets
the remote host with the profile's saved key.

**Acceptance Scenarios**:

1. **Given** a running dev stack, **When** `spree api-key create` is run
   interactively or with `--name`/`--type`/`--scopes` flags, **Then** a
   Store (`publishable`) or Admin (`secret`) key is created via the Rake
   task bridge and printed; secret keys require at least one scope.
2. **Given** `spree api-key list`/`revoke <id>`, **When** invoked, **Then**
   keys are listed/revoked against the project's store.
3. **Given** `spree auth login --profile prod --base-url <url>`, **When**
   run, **Then** the secret key is read from an interactive prompt (never a
   CLI flag, to avoid shell-history/process-list leakage) and saved to
   `~/.config/spree/config.json` (0700 dir, 0600 file) under that profile
   name.
4. **Given** saved profiles, **When** `spree auth status`/`logout --profile
   <name>` run, **Then** status lists profiles with token prefixes only, and
   logout removes the named profile.

---

### User Story 5 - Run project lifecycle and dev-workflow passthrough commands (Priority: P3)

A developer needs the remaining day-to-day commands that mirror running the
Rails app directly on the host, routed through the container: generators,
migrations, console, logs, routes, and arbitrary passthrough commands
(`exec`, `rails`, `bundle`, `rake`, `task`).

**Why this priority**: Long-tail convenience wrappers — valuable but not
blocking for the P1/P2 stories above to deliver value on their own.

**Independent Test**: Run `spree generate model Brand name:string`, `spree
migrate`, `spree console`, `spree routes -g products`, and `spree exec ls
-la` in a scaffolded project and confirm each reaches the container with the
documented argument translation.

**Acceptance Scenarios**:

1. **Given** `spree generate <name> <args>`, **When** `<name>` has no `:` and
   isn't a known Rails built-in, **Then** it is prefixed `spree:<name>`
   (e.g. `model` → `spree:model`); Rails built-ins and any name containing
   `:` are forwarded as-is.
2. **Given** `spree migrate`, **When** run, **Then** it installs pending
   Spree gem migrations then runs `db:migrate` — the canonical post-update
   sequence; `migrate:status`/`migrate:rollback STEP=n` map to
   `db:migrate:status`/`db:rollback`.
3. **Given** `spree db:reset`, **When** run without `--yes`, **Then** it
   prompts for confirmation before dropping/recreating/migrating/seeding
   (destructive); `--yes` skips the prompt for CI.
4. **Given** `spree exec`/`spree rails`/`spree bundle`/`spree rake`/`spree
   task`, **When** invoked with trailing arguments, **Then** those arguments
   reach the inner container command unmodified (passthrough, no
   reinterpretation).
5. **Given** `spree upgrade`, **When** run with `--plan`, `--to <version>`,
   `--step <id>`, or `--yes`, **Then** it walks `bundle update` → pending
   migrations → version-specific data backfills from the upgrade manifest,
   honoring dry-run/target/single-step/no-prompt semantics; a monorepo edge
   project (`SPREE_PATH` set) is refused with the same guard as `dev`/`build`.

### Edge Cases

- What happens when `spree api get` runs outside any Spree project and no
  flags/env/profile supply credentials? The CLI raises `CredentialError`
  listing all four resolution layers and exits `2`.
- How does the system handle a corrupt `~/.config/spree/config.json` or
  `.spree/credentials.json`? The global config is backed up to `.bak` and a
  fresh empty config is used (with a stderr warning); corrupt project
  credentials are treated as "not minted yet" and silently re-minted.
- What happens when `spree dev`/`spree build` run from inside the
  `create-spree-app` wrapper's stale `backend/` compose file? `detectProject`
  detects the `./backend:/rails` bind-mount marker in the parent's compose
  and re-roots to the wrapper root rather than targeting the broken
  leftover file.
- How does the system handle two containers racing to populate a cold
  `bundle_cache` volume on first boot? `spree dev` brings `web` up alone
  first (best-effort) so it wins the Docker copy-up uncontended before the
  full stack starts.
- What happens when an `-d` request body file is missing, or stdin is a TTY
  with no piped input? A missing `@file.json` raises a clear "not found"
  error; `-d -` on an interactive TTY prints a stderr prompt so the
  developer knows to paste JSON and press Ctrl-D rather than appearing to
  hang.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The CLI MUST manage the Docker dev stack lifecycle (`init`,
  `dev`, `stop`, `restart`, `update`, `build`, `eject`) by wrapping `docker
  compose` invocations against the project's `docker-compose.yml`.
- **FR-002**: The CLI MUST refuse `dev`/`build`/`upgrade` (and any command
  that materializes compose config) when the project's `.env` sets
  `SPREE_PATH`, directing the developer to the monorepo `pnpm server:*`
  scripts instead; label-based commands (`exec`, `stop`, `restart`, `logs`)
  remain unaffected since they resolve the same compose project either way.
- **FR-003**: The CLI MUST provide a generic Admin API client (`spree api
  get|post|patch|delete`) supporting Ransack query predicates, sorting,
  pagination, field selection (`--fields`, always including `id`),
  relationship expansion (`--expand`), and flat (unwrapped) JSON request
  bodies from inline string, file (`@file`), or stdin (`-`).
- **FR-004**: The CLI MUST resolve Admin API credentials through four
  layers, evaluated in order, with host and key drawn from the same layer
  except when explicit `--base-url`/`--api-key` flags are given: (1) flags,
  (2) environment (`SPREE_API_KEY`/`SPREE_BASE_URL`), (3) project
  (auto-minted read-only key in `.spree/credentials.json`), (4) saved
  profile (`~/.config/spree/config.json`).
- **FR-005**: The CLI MUST auto-mint a `read_all`-scoped secret key on first
  `spree api` use inside a project with the dev stack running (via the
  `spree:cli:create_api_key` Rake task), and MUST NOT auto-mint any write
  scope — write access requires an explicitly created key.
- **FR-006**: The CLI MUST persist credentials with owner-only permissions
  (0600 files, 0700 directories) and MUST ensure `.spree/` is gitignored
  independent of the host project's own `.gitignore` vintage.
- **FR-007**: The CLI MUST provide offline endpoint/schema discovery
  (`spree api endpoints`, `spree api schema`) and shell completion (`spree
  completion {zsh,bash,fish}`) from a bundled OpenAPI spec snapshot, with no
  network dependency.
- **FR-008**: The CLI MUST map failures to two exit codes: `1` for API-level
  errors (the Stripe-style error envelope, printed to stderr, with a scope
  remediation hint when the failure is a scope denial), `2` for
  usage/configuration/connectivity problems.
- **FR-009**: The CLI MUST adapt JSON output formatting to the output
  destination — colored/indented for a TTY, compact/uncolored when
  piped/redirected — and MUST support `--format table` for human-readable
  collection display.
- **FR-010**: The CLI MUST provide `spree api-key {create,list,revoke}` for
  Store (publishable) and Admin (secret, scoped) key management, and `spree
  auth {login,status,logout}` for named remote-store profiles, reading the
  secret key via an interactive prompt (never a flag) in `login`.
- **FR-011**: The CLI MUST provide dev-workflow passthrough commands
  (`generate`, `migrate`, `db:reset`, `db:console`, `routes`, `exec`,
  `rails`, `bundle`, `rake`, `task`) that translate to the equivalent
  in-container Rails/Bundler/Rake invocation, with `generate` auto-prefixing
  bare generator names with `spree:` unless the name is a known Rails
  built-in or already namespaced.
- **FR-012**: The CLI MUST provide `spree upgrade` to walk `bundle update` →
  pending migrations → version-specific data backfills in one flow, with
  `--plan` (dry run), `--to <version>` (cap), `--step <id>` (single,
  idempotent re-run), and `--yes` (skip prompts) modifiers.
- **FR-013**: The CLI MUST provide `spree seed` and `spree sample-data` for
  database seeding and demo content loading (see `specs/026-sample-data-seeds`
  for the underlying seed/sample-data model — not duplicated here).
- **FR-014**: Mutating Admin API requests (`post`/`patch`/`delete`) MUST
  automatically carry an `Idempotency-Key` header so retries are safe.

### Key Entities

- **Resolved Credentials**: `{ baseUrl, apiKey, source, profileName?,
  tokenPrefix, scopes? }` — the outcome of the four-layer resolution; never
  persists the full key beyond its originating store (project file or
  profile config).
- **Project Credentials**: `{ baseUrl, token, scopes, mintedAt }` — the
  auto-minted, project-scoped credential persisted to
  `.spree/credentials.json`.
- **CLI Config / Profile Entry**: `{ defaultProfile?, profiles: { [name]:
  { baseUrl, token } } }` — persisted to `~/.config/spree/config.json`.
- **Project Context**: `{ mode: 'docker', projectDir, port }` — the detected
  project root (re-rooted from a stale `backend/` wrapper dir when
  applicable) and its configured `SPREE_PORT`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `packages/cli` | Yes | The entire feature: `src/commands/*.ts` (project lifecycle + dev-workflow passthrough + `api`/`api-key`/`auth`/`completion`), `src/api/*.ts` (body parsing, output formatting, error mapping, endpoint/schema discovery), `src/config.ts` (credential resolution/persistence), `src/context.ts` (project detection, monorepo-edge guard), `src/docker.ts` (Compose wrapper, bundle-volume priming) |
| `packages/admin-sdk` | Yes (consumer) | `spree api` is a thin CLI wrapper over `@spree/admin-sdk`'s `SpreeError` and request layer — no admin-sdk changes originate from this feature, but it is a hard runtime dependency |
| `spree/core` | Yes (bridge) | `spree:cli:create_api_key` Rake task (referenced from `docs/plans/5.5-admin-api-cli.md`) is the server-side bridge the CLI calls to auto-mint project credentials |
| `spree/api` | No | Consumes the existing Admin API v3 surface as-is; no controller/serializer changes originate here |
| `packages/dashboard` | No | Not touched — this is a terminal tool, not an admin SPA feature |
| `docs/plans/` | Yes | Governed by `docs/plans/5.5-admin-api-cli.md` (`spree api` command group design) |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints**: None — `spree api` is a generic passthrough to
  whatever Admin API v3 endpoint the caller names; it does not add
  endpoints.
- **Serializer fields (read)**: N/A — output is whatever the targeted
  endpoint's existing serializer returns, passed through unmodified.
- **Auth**: Admin API secret keys (`sk_...`) with Shopify-style scopes, per
  `docs/plans/5.5-admin-api-key-scopes.md`. The CLI never uses publishable
  keys or JWT for `spree api` itself (those are for Store API / human SPA
  login respectively); `spree api-key create --type publishable` exists only
  to manage Store API keys for *other* consumers (e.g. a storefront).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer goes from a freshly scaffolded project to a
  running admin dashboard with `spree init` alone, with no manual Docker or
  Rails commands.
- **SC-002**: `spree api get <any-endpoint>` inside a project works with
  zero prior credential setup on the first invocation.
- **SC-003**: An agent hitting a scope-denied write can self-correct (mint
  the right key, retry) using only the text printed to stderr — no need to
  consult external docs.
- **SC-004**: `spree api endpoints`/`spree api schema` answer "what's the
  shape of this call" with the network/server unreachable (fully offline).
- **SC-005**: Every credential file the CLI writes (`.spree/credentials.json`,
  `~/.config/spree/config.json`) is unreadable by other local users (0600)
  and never committed to the project's git history.

## Assumptions

- The Admin API v3 surface (endpoints, scopes, serializers) already exists
  and is stable enough for the CLI's bundled OpenAPI snapshot to track it;
  this feature does not add or change API endpoints.
- `create-spree-app` has already scaffolded the target project (compose
  files, `.env`, `backend/` if ejected) before any `spree` command runs —
  project scaffolding itself is a separate feature (`5.4-spree-starter-and-
  create-spree-app.md`).
- Docker (or a compatible `docker compose` CLI) is available on the
  developer's host; there is no non-Docker code path for project lifecycle
  commands (a native no-Docker path exists via `bin/setup`/`bin/dev` but is
  outside this CLI's scope).
- The `spree:cli:create_api_key` Rake task (server-side) is treated as an
  existing dependency of this feature, not something this spec defines —
  it is covered under `docs/plans/5.5-admin-api-cli.md`.

## Migration Notes

- **Cross-reference to 026**: `spree seed` and `spree sample-data` (User
  Story 5, FR-013) are covered in depth by
  `specs/026-sample-data-seeds/spec.md` (`Spree::Seeds::All`,
  `Spree::SampleData` loaders). This spec intentionally does not duplicate
  that acceptance criteria — it only notes the CLI commands exist as thin
  wrappers over the Rake tasks those seed/sample-data services expose.
- **SPREE_PATH guard**: Per `CLAUDE.md` → "Development Server (`server/`)",
  `spree dev` and `spree build` refuse to run inside the monorepo's
  `server/` directory (or any project with `SPREE_PATH` set in `.env`) —
  enforced by `hasMonorepoSpreePath()` in `packages/cli/src/context.ts` and
  checked in `commands/dev.ts`, `commands/build.ts`, `commands/db.ts`, and
  `commands/upgrade.ts`. The guard exists because the monorepo boots via
  `pnpm server:dev`/`pnpm server:build` against an edge compose overlay with
  gems bind-mounted from `spree/*` source — the project-local
  `docker-compose.yml` the CLI would otherwise target is not the config
  actually running, so acting on it would silently diverge from the live
  stack. Label-based commands (`exec`, `stop`, `restart`, `logs`) are exempt
  since they resolve the same Compose project regardless of which compose
  file materialized it.
- **Gaps identified during migration**: No dedicated automated test suite
  was located under `packages/cli/` at migration time beyond what ships with
  the package (tests were not exhaustively enumerated per the "sample, don't
  read every file" instruction) — Phase 4 (Polish) tasks in `tasks.md`
  reflect the existing `pnpm test`/`pnpm typecheck`/`pnpm lint` gates rather
  than asserting full coverage exists. The `spree:cli:create_api_key` Rake
  task itself lives in `spree/core` but was not read in full during this
  pass — treated as a stable dependency per the Assumptions above.
