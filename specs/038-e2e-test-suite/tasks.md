---

description: "Task list template for feature implementation"
---

# Tasks: Admin SPA E2E Test Suite

**Input**: Design documents from `/specs/038-e2e-test-suite/`

**Prerequisites**: plan.md, spec.md

**Tests**: This feature *is* the test suite — there is no separate "tests for the tests" phase. Tasks below are organized by harness component and by spec-file domain area (not by invented user stories, since this is test infrastructure rather than a product feature), and are marked complete as a record of already-shipped work (brownfield migration).

**Status**: All tasks below reflect the implementation as it exists on `main` at migration time. No new work is proposed by this document.

## Path Conventions

All paths are under `packages/dashboard/e2e/` (harness) or `packages/dashboard/playwright.config.ts` (runner config). No backend, `dashboard-ui`, `dashboard-core`, or SDK paths apply.

---

## Phase 1: Harness Configuration

**Purpose**: Playwright runner configuration — ports, serial execution, webServer/global lifecycle wiring

- [x] T001 Configure isolated ports distinct from dev defaults (Rails :3010 vs :3000, Vite :5174 vs :5173) in `packages/dashboard/playwright.config.ts`
- [x] T002 Configure serial execution (`fullyParallel: false, workers: 1`) — shared Rails process + SQLite DB can't run concurrently, in `packages/dashboard/playwright.config.ts`
- [x] T003 Configure `webServer` entry for Vite dev pointed at the test Rails port via `VITE_API_PROXY_TARGET`, in `packages/dashboard/playwright.config.ts`
- [x] T004 Wire `globalSetup` / `globalTeardown` to `./e2e/global-setup.ts` / `./e2e/global-teardown.ts`, in `packages/dashboard/playwright.config.ts`
- [x] T005 Set CI-aware reporter/retries (`github` reporter + 2 retries under `CI`, `list` + 0 retries locally) and per-test/expect timeouts, in `packages/dashboard/playwright.config.ts`

**Checkpoint**: Running `pnpm test:e2e` boots an isolated stack on the configured ports

---

## Phase 2: Harness Lifecycle (Setup / Teardown / Paths)

**Purpose**: Backend bootstrap, seeding, and cleanup that every spec depends on

- [x] T006 [P] Centralize path constants (`E2E_DIR`, `CREDENTIALS_FILE`, `RAILS_PID_FILE`) in `packages/dashboard/e2e/paths.ts`
- [x] T007 Implement `globalSetup()` in `packages/dashboard/e2e/global-setup.ts`: wipe `spec/dummy/db/spree_test.sqlite3`, run the `BOOTSTRAP_RUBY` script via `bundle exec spec/dummy/bin/rails runner` to load schema + `Spree::Seeds::All.call` + admin user + fixtures, write `.credentials.json`
- [x] T008 Spawn the test Rails server (`rails server -p 3010 -e test`) as a detached child process and record its PID to `.rails.pid`, in `packages/dashboard/e2e/global-setup.ts`
- [x] T009 Poll `/api/v3/admin/me` until it responds (`waitForServer`, 30s timeout) before letting Playwright proceed, in `packages/dashboard/e2e/global-setup.ts`
- [x] T010 Implement `globalTeardown()` in `packages/dashboard/e2e/global-teardown.ts`: read `.rails.pid`, `SIGTERM` the process, tolerate a missing PID file (ENOENT), delete the PID file
- [x] T011 Seed idempotent shared fixtures in the `BOOTSTRAP_RUBY` script (promo product/category/customer/customer-group, disjoint bulk-action product sets A–N, second channel, EUR market) matching the constants declared in `helpers.ts`, in `packages/dashboard/e2e/global-setup.ts`

**Checkpoint**: `.credentials.json` is available and a real seeded backend is reachable before any spec file runs

---

## Phase 3: Shared Spec Helpers

**Purpose**: Cross-cutting interaction patterns so individual specs stay declarative and UI-only

- [x] T012 [P] `login()` — drive the admin login form and wait for navigation away from `/login`, in `packages/dashboard/e2e/helpers.ts`
- [x] T013 [P] `gotoIndex()` — navigate to a resource index and wait for its primary CTA button (proves auth + data loaded), in `packages/dashboard/e2e/helpers.ts`
- [x] T014 [P] `openRowMenu()` — open a table row's kebab/actions menu by row text, in `packages/dashboard/e2e/helpers.ts`
- [x] T015 [P] `clickBulkAction()` — click a bulk action, falling back to the "More actions" overflow dropdown when the inline button isn't visible, in `packages/dashboard/e2e/helpers.ts`
- [x] T016 [P] `rowButton()` — resolve the `<ResourceNameCell>` button for a row by name, disambiguating regex-unsafe/updated-suffix names, in `packages/dashboard/e2e/helpers.ts`
- [x] T017 [P] `fillAddressForm()` — fill the shared address form dialog (including country/state Combobox interaction), in `packages/dashboard/e2e/helpers.ts`
- [x] T018 [P] Export fixture-name constants (`FIXTURE_PROMO_*`, `FIXTURE_BULK_PRODUCT_A`..`_N`, `FIXTURE_BULK_CHANNEL_*`) kept in sync with the seed script, in `packages/dashboard/e2e/helpers.ts`
- [x] T019 [P] Products-domain-specific spec helpers, in `packages/dashboard/e2e/products-helpers.ts`

**Checkpoint**: Every spec file can be written against a small, shared, UI-only interaction vocabulary

---

## Phase 4: Auth & Account Domain Specs

**Goal**: Cover login, staff invitations, and profile/account self-service flows

- [x] T020 [P] `packages/dashboard/e2e/auth.spec.ts` — login flow itself (not covered by the shared `login()` helper, which assumes success)
- [x] T021 [P] `packages/dashboard/e2e/invitation-acceptance.spec.ts` — admin invites a teammate, invitee accepts via link in a fresh browser context; documented exception: `page.waitForResponse` used to capture `acceptance_url` (no UI feedback — normally emailed)
- [x] T022 [P] `packages/dashboard/e2e/profile.spec.ts` — account/profile self-service

**Checkpoint**: Auth and account lifecycle flows are covered independently of resource CRUD

---

## Phase 5: Products Domain Specs

**Goal**: Cover product CRUD, variants, media, pricing/inventory, custom fields, translations, publishing, and bulk actions — the largest domain in the suite

- [x] T023 [P] `packages/dashboard/e2e/products-new.spec.ts` — product creation
- [x] T024 [P] `packages/dashboard/e2e/products-new-media.spec.ts` — media attachment during creation
- [x] T025 [P] `packages/dashboard/e2e/products-edit.spec.ts` — product edit flow
- [x] T026 [P] `packages/dashboard/e2e/products-edit-media-variants.spec.ts` — media + variant editing
- [x] T027 [P] `packages/dashboard/e2e/products-variants.spec.ts` — variant management
- [x] T028 [P] `packages/dashboard/e2e/products-prices-inventory.spec.ts` — pricing and inventory editing
- [x] T029 [P] `packages/dashboard/e2e/products-custom-fields.spec.ts` — custom field values on a product
- [x] T030 [P] `packages/dashboard/e2e/products-translations.spec.ts` — product translation editing
- [x] T031 [P] `packages/dashboard/e2e/products-publishing.spec.ts` — channel publishing card
- [x] T032 [P] `packages/dashboard/e2e/products-bulk.spec.ts` — bulk status/category/tag/delete/clone/channel actions against the disjoint `FIXTURE_BULK_PRODUCT_A`..`_N` set

**Checkpoint**: Product management is covered end-to-end across its sub-flows

---

## Phase 6: Catalog Structure & Merchandising Specs

**Goal**: Cover categories, option types, price lists, promotions, and custom field definitions

- [x] T033 [P] `packages/dashboard/e2e/categories.spec.ts` — category CRUD
- [x] T034 [P] `packages/dashboard/e2e/option-types.spec.ts` — option type + option value CRUD
- [x] T035 [P] `packages/dashboard/e2e/option-type-translations.spec.ts` — option type translation editing
- [x] T036 [P] `packages/dashboard/e2e/price-lists.spec.ts` — price list CRUD
- [x] T037 [P] `packages/dashboard/e2e/promotions.spec.ts` — promotion rule/action editor flows, consuming `FIXTURE_PROMO_*` fixtures
- [x] T038 [P] `packages/dashboard/e2e/custom-field-definitions.spec.ts` — custom field definition CRUD

**Checkpoint**: Catalog/merchandising configuration surfaces are covered

---

## Phase 7: Customers, Channels & Store Configuration Specs

**Goal**: Cover customer management, channels, markets, payment methods, stock, tax, webhooks, and store-level settings

- [x] T039 [P] `packages/dashboard/e2e/customers.spec.ts` — customer CRUD
- [x] T040 [P] `packages/dashboard/e2e/customer-groups.spec.ts` — customer group CRUD
- [x] T041 [P] `packages/dashboard/e2e/channels.spec.ts` — channel CRUD
- [x] T042 [P] `packages/dashboard/e2e/channels-settings.spec.ts` — per-channel settings
- [x] T043 [P] `packages/dashboard/e2e/markets.spec.ts` — market CRUD (multi-currency EUR/Germany fixture)
- [x] T044 [P] `packages/dashboard/e2e/payment-methods.spec.ts` — payment method CRUD
- [x] T045 [P] `packages/dashboard/e2e/stock-locations.spec.ts` — stock location CRUD
- [x] T046 [P] `packages/dashboard/e2e/stock-transfers.spec.ts` — stock transfer lifecycle
- [x] T047 [P] `packages/dashboard/e2e/tax-categories.spec.ts` — tax category CRUD
- [x] T048 [P] `packages/dashboard/e2e/webhooks.spec.ts` — webhook endpoint CRUD
- [x] T049 [P] `packages/dashboard/e2e/gift-cards.spec.ts` — gift card management
- [x] T050 [P] `packages/dashboard/e2e/allowed-origins.spec.ts` — allowed-origins (CORS) settings
- [x] T051 [P] `packages/dashboard/e2e/store-settings.spec.ts` — store-level settings
- [x] T052 [P] `packages/dashboard/e2e/orders.spec.ts` — order management flows

**Checkpoint**: Every remaining resource domain in the admin SPA has at least one spec file

---

## Dependencies & Execution Order

- **Phase 1 (Harness Configuration)**: No dependencies — governs how every later phase runs
- **Phase 2 (Lifecycle)**: Depends on Phase 1's port/webServer config; blocks every spec phase (no spec can run without a seeded, reachable backend)
- **Phase 3 (Shared Helpers)**: Depends on Phase 2 only for `getCredentials()`'s backing file shape; otherwise independent of any single spec
- **Phases 4–7 (spec files)**: All depend on Phases 1–3; individual spec files within a phase are independent of each other ([P]) except where a file intentionally shares fixture state with another (e.g. `products-bulk.spec.ts`'s per-test disjoint fixture pairs, documented in `helpers.ts`)

## Notes

- All tasks are marked `[x]` — this document records already-shipped test infrastructure (brownfield migration), not planned work.
- [P] on spec-file tasks reflects that each file is an independently runnable Playwright test file; it does **not** imply parallel *execution* — the suite as a whole is intentionally serial (`workers: 1`) per Phase 1.
- No RSpec/Vitest tasks appear here: this feature's only test framework is Playwright, and Playwright *is* the deliverable, not a verification layer bolted onto some other deliverable.
