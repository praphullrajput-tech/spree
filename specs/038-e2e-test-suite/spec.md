# Feature Specification: Admin SPA E2E Test Suite

**Feature Branch**: `038-e2e-test-suite`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration). Playwright end-to-end test suite for `packages/dashboard` (the admin SPA): a globally-booted real Rails test server (`spree/api/spec/dummy`, port 3010) + a real Vite dev server (port 5174), seeded once via `Spree::Seeds::All` plus idempotent fixture records, exercised serially by 33 spec files under `packages/dashboard/e2e/`. This is test infrastructure, not a runtime product feature — there are no end users, only developers writing and running Playwright specs against the admin SPA.

## User Scenarios & Testing *(mandatory)*

<!-- Framed as developer workflows against the E2E harness, not end-user journeys — this is test infrastructure. -->

### User Story 1 - Developer runs the full E2E suite locally before opening a PR (Priority: P1)

A developer changes admin SPA code (a route, a form, a table) and wants to verify nothing broke across the resources the suite covers, using the project's real backend rather than mocks.

**Why this priority**: This is the core promise of the suite — a single command boots a disposable, isolated Rails + Vite stack and runs every spec against it, so a developer gets a realistic pass/fail signal without touching their own dev stack.

**Independent Test**: Run `cd packages/dashboard && pnpm test:e2e`. `global-setup.ts` wipes `spec/dummy/db/spree_test.sqlite3`, boots Rails in `test` env on port 3010, seeds base data + fixtures, writes `.credentials.json`; Playwright then starts Vite on port 5174 (proxying `/api/*` to :3010) and runs all specs sequentially; `global-teardown.ts` kills the Rails process by PID.

**Acceptance Scenarios**:

1. **Given** no dev stack is running, **When** `pnpm test:e2e` is invoked, **Then** a dedicated Rails server on port 3010 and Vite dev server on port 5174 boot, distinct from the developer's own `:3000`/`:5173` stack.
2. **Given** the suite has finished (pass or fail), **When** teardown runs, **Then** the spawned Rails process is terminated via its recorded PID file and no orphan process is left running.
3. **Given** a spec needs an authenticated session, **When** it calls the shared `login()` helper, **Then** it reaches an authenticated admin session using credentials written by global setup, without re-implementing the login flow.

---

### User Story 2 - Developer writes a new spec following the UI-only assertion convention (Priority: P1)

A developer adds coverage for a new admin resource/flow and needs to know how to drive and assert against the SPA in a way that stays stable across refactors.

**Why this priority**: The convention (drive through visible UI, assert on visible UI, no `page.waitForResponse` for backend completion) is what keeps 33+ spec files from becoming brittle against internal API shape changes; violating it silently reintroduces flakiness/coupling.

**Independent Test**: Write a spec using only `getByRole`/`getByLabel`/`getByText` locators and `expect(...).toBeVisible()` polling (mirroring Capybara's `default_max_wait_time`); confirm it passes without any `waitForResponse` call, using the shared helpers in `packages/dashboard/e2e/helpers.ts` (`login`, `gotoIndex`, `openRowMenu`, `clickBulkAction`, `rowButton`, `fillAddressForm`).

**Acceptance Scenarios**:

1. **Given** a mutation that renders a visible success state only after the API call resolves, **When** a spec is written for it, **Then** the spec asserts on that visible state (e.g. a toast, a new row) instead of waiting on the network response.
2. **Given** a resource index page, **When** a spec needs to reach it post-login, **Then** it uses `gotoIndex(page, path, ctaButtonName)` rather than hand-rolling a navigate + wait.
3. **Given** a row-level action (edit, delete, clone) on a resource table, **When** a spec needs to trigger it, **Then** it uses `openRowMenu`/`rowButton`/`clickBulkAction` rather than duplicating kebab-menu/bulk-action-bar locator logic per spec.

---

### User Story 3 - Developer relies on the two narrow API-wait exceptions when UI has no signal (Priority: P2)

Occasionally a mutation has no visible DOM signal to assert against (e.g. a value only ever emailed, never shown in the admin), or the UI is optimistically rendered before the server confirms. The developer needs a documented, narrow escape hatch rather than inventing ad hoc waits per spec.

**Why this priority**: Without a codified exception list, developers either avoid testing these flows entirely or scatter undocumented `waitForResponse` calls that erode the "UI-only" convention over time.

**Independent Test**: Inspect `invitation-acceptance.spec.ts`, which uses `page.waitForResponse` to capture the `POST /api/v3/admin/invitations` response body for its `acceptance_url` — a value normally emailed to the invitee and never rendered in the admin UI — with an inline comment citing the exception.

**Acceptance Scenarios**:

1. **Given** a mutation with no UI feedback (e.g. a value only delivered out-of-band, like an email), **When** a spec needs data from that response, **Then** it may use `page.waitForResponse`, with a comment explaining why no UI-only alternative exists.
2. **Given** an optimistic-UI mutation where success renders before server confirmation, **When** a spec would otherwise be unable to distinguish "rendered" from "rendered and persisted," **Then** it may fall back to an API-level wait, per the same documented exception.
3. **Given** any other flow, **When** a spec is reviewed, **Then** a `waitForResponse` call without one of these two justifications is treated as a convention violation.

---

### User Story 4 - Developer keeps fixture/seed data disjoint across a serial suite (Priority: P2)

Because the suite runs `fullyParallel: false, workers: 1` against one shared Rails process and SQLite DB, specs that mutate the same seeded records (e.g. bulk product actions) can silently corrupt each other's expected state if fixtures overlap.

**Why this priority**: Test-suite reliability at this scale depends on deliberate data isolation; without it, failures become order-dependent and hard to reproduce.

**Independent Test**: Trace `FIXTURE_BULK_PRODUCT_A` .. `_N` in `helpers.ts` and their seeding in `global-setup.ts`'s `BOOTSTRAP_RUBY` script — each pair (A/B status, C/D categories, E/F tags, G/H delete, I clone/delete, K/L add-to-channel, M/N pre-listed remove-from-channel) is consumed by exactly one test in `products-bulk.spec.ts`.

**Acceptance Scenarios**:

1. **Given** two specs mutate bulk-action state on products, **When** both run in the same serial pass, **Then** each operates on its own disjoint fixture products so neither test's assertions are affected by the other's mutations.
2. **Given** a new bulk-action test is added, **When** it needs seed products, **Then** it is seeded a new disjoint fixture pair/set in `global-setup.ts` rather than reusing another test's fixtures.
3. **Given** dynamic (non-fixture) test data, **When** a spec creates it, **Then** it suffixes names with `Date.now()` so reruns and leftover rows from earlier runs never collide.

---

### Edge Cases

- What happens when the Rails test server fails to boot within the 30s `waitForServer` poll against `/api/v3/admin/me`? Setup throws and the whole run fails fast rather than letting specs run against a half-booted backend.
- How does the suite handle a prior run's leftover `spec/dummy/db/spree_test.sqlite3` or stale `.rails.pid`? `global-setup.ts` removes the SQLite file unconditionally before reseeding (idempotent `first_or_create!`/`find_or_create_by!` seeds); `global-teardown.ts` tolerates a missing PID file (ENOENT is swallowed).
- What happens when a bootstrap Ruby seed script itself fails (e.g. missing `Spree::Country` for the EUR market)? It fails fast with `find_by!` rather than deferring to an opaque later E2E failure.
- How are ambiguous row-name matches (e.g. `"E2E Foo"` vs `"E2E Foo (updated)"`) disambiguated? `rowButton()` anchors the accessible-name regex with `^` plus a trailing word-boundary and escapes regex metacharacters in dynamic names.
- What happens when the admin's session cookie would leak into a second identity's flow (e.g. invitee accepting an invite)? The spec opens a fresh `browser.newContext()` rather than reusing the admin's authenticated page.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The suite MUST boot an isolated Rails test server (port 3010, `RAILS_ENV=test`) and Vite dev server (port 5174) distinct from the developer's normal dev ports (3000/5173), configured in `packages/dashboard/playwright.config.ts`.
- **FR-002**: Global setup MUST reset the SQLite test database and reseed it (`Spree::Seeds::All.call` plus idempotent fixture records) before every full suite run.
- **FR-003**: Global setup MUST persist run credentials (`api_url`, `admin_email`, `admin_password`, `store_id`, `store_name`) to `.credentials.json` for specs to read via `getCredentials()`.
- **FR-004**: Global teardown MUST terminate the spawned Rails process via its recorded PID and tolerate a missing PID file.
- **FR-005**: Specs MUST run sequentially (`fullyParallel: false, workers: 1`) since they share one Rails process and one SQLite database.
- **FR-006**: Specs MUST assert against visible UI (`getByRole`/`getByLabel`/`getByText` + `toBeVisible`/`toHaveValue`/`toHaveCount` polling) rather than `page.waitForResponse`, except for the two documented exceptions (no UI feedback; optimistic UI ambiguity).
- **FR-007**: Shared cross-spec interaction patterns (login, index-page readiness, row-menu actions, bulk-action-bar overflow handling, row-button lookup, address-form filling) MUST live in `packages/dashboard/e2e/helpers.ts`, not be duplicated per spec.
- **FR-008**: Fixture records shared across specs (promo product/category/customer/group, bulk-action product sets, bulk channel) MUST be named as exported constants in `helpers.ts` and seeded idempotently in `global-setup.ts` so specs and seed data stay in sync.
- **FR-009**: Specs that create ad hoc (non-fixture) data MUST suffix names with `Date.now()` to avoid collisions with leftover rows from prior runs.
- **FR-010**: Path helpers (`E2E_DIR`, `CREDENTIALS_FILE`, `RAILS_PID_FILE`) MUST be centralized in `packages/dashboard/e2e/paths.ts` rather than recomputed per file.

### Key Entities *(include if feature involves data)*

- **E2ECredentials**: Runtime record written by global setup and read by specs — `api_url`, `admin_email`, `admin_password`, `store_id`, `store_name`. Not a persisted domain entity; scoped to one suite run.
- **Fixture records**: Idempotently-seeded `Spree::Product`, `Spree::Taxon`/category, `Spree::Channel`, customer, and customer-group rows created by the `BOOTSTRAP_RUBY` script in `global-setup.ts`, referenced by name from `helpers.ts` constants (e.g. `FIXTURE_PROMO_PRODUCT`, `FIXTURE_BULK_PRODUCT_A`..`_N`).

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | No | — |
| `spree/api` (Store/Admin API v3) | No | Consumed only — global setup boots `spree/api/spec/dummy` as the real backend under test, but this feature adds no API code |
| `packages/dashboard` (admin SPA) | Yes | All artifacts live under `packages/dashboard/e2e/`: `playwright.config.ts`, `global-setup.ts`, `global-teardown.ts`, `paths.ts`, `helpers.ts`, `products-helpers.ts`, and 33 `*.spec.ts` files covering products, orders, promotions, customers, channels, markets, payment methods, categories, custom fields, translations, staff invitations, auth, profile, store settings, stock locations/transfers, tax categories, webhooks, gift cards, allowed origins |
| `packages/dashboard-ui` / `dashboard-core` | No | Exercised indirectly through rendered DOM; no test code lives there |
| `packages/sdk` / `packages/admin-sdk` | No | — |
| `docs/plans/` | No | Test infrastructure convention already documented in root `CLAUDE.md` → "Admin SPA E2E (Playwright)"; no `docs/plans/` entry exists or is needed |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can run `cd packages/dashboard && pnpm test:e2e` from a clean checkout with no manually-started backend and get a pass/fail result for all 33 spec files.
- **SC-002**: No spec file uses `page.waitForResponse` except where justified by one of the two documented exceptions (currently one occurrence, in `invitation-acceptance.spec.ts`).
- **SC-003**: Re-running the full suite twice in a row (without wiping node/browser state) produces the same pass/fail outcome — no order-dependent or leftover-data-dependent flakiness from fixture collisions.
- **SC-004**: A failed run leaves no orphaned Rails process — teardown always fires and the recorded PID is killed or the missing-PID case is tolerated.

## Assumptions

- Docker/host Ruby is not required for E2E runs specifically — `global-setup.ts` shells out to `bundle exec spec/dummy/bin/rails`, assuming a working Ruby/Bundler environment for `spree/api`'s dummy app (independent of the `pnpm server:*` Docker-based dev workflow documented for day-to-day development).
- SQLite is the assumed test database for the dummy app (`spec/dummy/db/spree_test.sqlite3`), matching the backend RSpec default described in root `CLAUDE.md`, not PostgreSQL.
- The suite is scoped to `packages/dashboard` only; the legacy Rails admin (`spree/admin`) and the Store API-facing storefront have no equivalent Playwright coverage in this feature.
- CI parallelization across spec *files* (if any) is out of scope for this migration note — `fullyParallel: false, workers: 1` is a hard constraint from shared Rails/SQLite state, not a config knob evaluated here.

## Migration Notes

- **Two narrow exceptions to the UI-only assertion rule** (per root `CLAUDE.md` → "Admin SPA E2E (Playwright)"), both intentional and documented, not violations to "fix":
  1. **No UI feedback** — a mutation kicks off something with no visible DOM signal (e.g. `invitation-acceptance.spec.ts` needs the `acceptance_url` from the `POST /api/v3/admin/invitations` response body, since that URL is normally emailed and never rendered in the admin UI).
  2. **Optimistic UI** — success state appears in the DOM before the API call resolves, so a UI-only assertion can't distinguish "rendered" from "rendered but will later fail." Both exceptions are rare in this codebase; the admin SPA generally renders success only after mutations resolve.
- **Spec file count**: 33 `*.spec.ts` files enumerated under `packages/dashboard/e2e/` at migration time (not read exhaustively — `option-types.spec.ts` and `invitation-acceptance.spec.ts` were read in full as representative samples; the remainder were enumerated by filename only: `allowed-origins`, `auth`, `categories`, `channels`, `channels-settings`, `custom-field-definitions`, `customer-groups`, `customers`, `gift-cards`, `markets`, `option-type-translations`, `orders`, `payment-methods`, `price-lists`, `products-bulk`, `products-custom-fields`, `products-edit`, `products-edit-media-variants`, `products-new`, `products-new-media`, `products-prices-inventory`, `products-publishing`, `products-translations`, `products-variants`, `profile`, `promotions`, `stock-locations`, `stock-transfers`, `store-settings`, `tax-categories`, `webhooks`). A `fixtures/` subdirectory and `products-helpers.ts` (a products-domain-specific helper module alongside the general `helpers.ts`) also exist.
- No gaps requiring `[NEEDS CLARIFICATION]` were found — the harness, conventions, and file inventory are fully observable from source.
