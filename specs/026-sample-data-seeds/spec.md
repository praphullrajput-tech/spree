# Feature Specification: Sample Data & Seeds

**Feature Branch**: `026-sample-data-seeds`

**Created**: 2026-08-24

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — `spree/core/app/services/spree/seeds/*`, `spree/core/app/services/spree/sample_data/*`, `spree/core/lib/tasks/sample_data.rake`, `spree/core/db/seeds.rb`, `spree/core/db/sample_data/*`, `packages/cli/src/commands/sample-data.ts`.

## User Scenarios & Testing *(mandatory)*

This is developer/ops tooling, not an end-user storefront or admin feature.
The "user" is a developer or operator bringing up a new Spree store
(locally, in CI, in a fresh production deploy, or via `@spree/cli`) who
needs the database populated with the minimum configuration required for
the app to function, optionally followed by realistic demo content.

### User Story 1 - Bootstrap a working store from an empty database (Priority: P1)

A developer runs `rails db:seed` (or `pnpm server:seed` from the monorepo
root) against a freshly migrated, empty database and expects to end up with
a store that can actually process an order: countries/states, tax
categories, zones, shipping categories, a default `Spree::Store`, a default
stock location, an admin user they can log in with, and a store-credit
payment method — all without hand-crafting fixtures.

**Why this priority**: Nothing else in the app works without this — every
other seed/sample-data path (`Loader`, the `@spree/cli` command) calls
`Spree::Seeds::All` first if it detects the baseline is missing.

**Independent Test**: Point at an empty test/dev database and run
`Spree::Seeds::All.call` (or `rails db:seed`, which just calls it). Verify a
default `Spree::Store` exists, an admin user can authenticate, and a
`Spree::Order` can be built end-to-end (address → shipping → payment)
without further manual setup.

**Acceptance Scenarios**:

1. **Given** an empty database, **When** `Spree::Seeds::All.call` runs,
   **Then** `Spree::Country`/`Spree::State` are populated from the `carmen`
   gem, `Spree::Zone`s (`EU_VAT`, `UK_VAT`, continents) and their members
   exist, `Spree::TaxCategory` has a default + non-taxable row, and
   `Spree::ShippingCategory` has default + digital rows.
2. **Given** an empty database, **When** seeds run, **Then** exactly one
   `Spree::Store` is created (`Spree::Seeds::Stores` no-ops if any store
   already has `default: true`), with a default `Spree::StockLocation`
   scoped to that store's default country.
3. **Given** `Spree.admin_user_class.count.zero?`, **When** seeds run,
   **Then** one admin user is created from `ADMIN_EMAIL`/`ADMIN_PASSWORD`/
   `ADMIN_FIRST_NAME`/`ADMIN_LAST_NAME` env vars (defaulting to
   `spree@example.com` / `spree123` / `Spree` / `Admin`) and added to the
   default store.
4. **Given** seeds have already run once, **When** `Spree::Seeds::All.call`
   runs again, **Then** it is idempotent — every seed class uses
   `first_or_create!` / `find_or_create_by!` / `find_or_initialize_by` /
   existence guards, so no duplicate rows are created and no exception is
   raised.

---

### User Story 2 - Load realistic demo/sample data for local development and demos (Priority: P2)

A developer wants a store that *looks* real — dozens of products with
variants and images, customers, completed orders, categories, promotions,
option types — to develop and demo against, without hand-authoring CSV
fixtures or writing throwaway scripts.

**Why this priority**: Baseline seeds (US1) make the app functional but
empty; most day-to-day frontend/admin development and demos need populated
catalog + order data. This is optional and only needed after US1.

**Independent Test**: Run `rails spree:load_sample_data` (or
`pnpm server:load_sample_data`, or `spree sample-data` via `@spree/cli`)
against a store that already has baseline seeds. Verify `Spree::Product`
count > 30, `Spree::Variant` count > 100, non-admin customer count > 5, and
completed `Spree::Order` count >= 2 (per the existing `loader_spec.rb`
assertions).

**Acceptance Scenarios**:

1. **Given** an empty database (no seeds run yet), **When**
   `Spree::SampleData::Loader.call` runs, **Then** it first detects the
   missing baseline (`Spree::Country.find_by(iso: 'US')&.states&.any?` and
   `Spree::Store.default&.persisted?`) and calls `Spree::Seeds::All.call`
   before loading sample content.
2. **Given** baseline seeds exist, **When** the loader runs, **Then** it
   loads, in order: shipping methods, payment methods, promotions
   (Ruby fixture files), markets, channels, metafield definitions, options,
   products (via CSV import), publishes products on the default channel,
   categories (derived from the products CSV), product translations,
   customers (CSV import), orders (Ruby fixture), and posts.
3. **Given** the products/customers/translations sample data, **When**
   loaded, **Then** it goes through the real import pipeline
   (`Spree::SampleData::ImportRunner` → `Spree::Imports::Products` /
   `Customers` / `ProductTranslations`, attached as a CSV upload owned by
   the default store's admin user) — not direct `ActiveRecord` inserts —
   so any row-level import failure is caught, logged, and counted rather
   than aborting the whole load.
4. **Given** `Spree::Config[:geocode_addresses]` is enabled, **When** the
   loader runs, **Then** geocoding is temporarily disabled for the duration
   of the load (`without_geocoding`) and restored afterward, so sample
   address data doesn't trigger real geocoding API calls.

---

### User Story 3 - Trigger seeding/sample data from tooling outside Rails (Priority: P3)

A developer using the `@spree/cli` (Docker-based project management CLI)
wants to load sample data into their containerized Spree instance without
knowing the underlying Rake task name.

**Why this priority**: Convenience wrapper — not required for either
seeding or sample-data loading to function, but it's the documented
entry point for `create-spree-app`/CLI users per `CLAUDE.md`.

**Independent Test**: Run `spree sample-data` from a project directory
created by `@spree/cli`; verify it shells out to
`docker compose exec ... rails spree:load_sample_data` and reports success/
failure via the CLI spinner.

**Acceptance Scenarios**:

1. **Given** a running Dockerized Spree project, **When** `spree
   sample-data` is run, **Then** `registerSampleDataCommand` invokes
   `rakeTask('spree:load_sample_data', ctx.projectDir)` inside the app
   container and surfaces the result.

---

### Edge Cases

- What happens when seeds run against a database that already has a
  default store but no admin user? `Spree::Seeds::AdminUser` only checks
  `Spree.admin_user_class.count.zero?`, independent of store state, so it
  still creates the admin and attaches it to the existing default store.
- What happens when `Spree.admin_user_class` is not configured (`nil`)?
  `Spree::Seeds::AdminUser#call` guards with
  `Spree.admin_user_class.present?` and no-ops.
- What happens when sample product translations CSV is absent (older
  install/extension without it)? `Loader#load_product_translations` checks
  `csv_path.exist?` and skips silently.
- What happens when a sample-data CSV row fails to import (e.g. a bad
  category or malformed price)? `ImportRunner` rescues per-row, increments a
  `failed` counter, prints a warning, and continues — the whole load is not
  aborted.
- What happens if `Spree::SampleData::ImportRunner` is called with no admin
  user present? It raises `'No admin user found. Please run seeds first.'`
  — sample data always depends on baseline seeds having created an admin.
- What happens on a re-run of `spree:load_sample_data` against a store that
  already has sample products? Not idempotent by row — CSV imports and
  `find_or_create_by!` calls in the Ruby fixture files (`markets.rb`,
  `channels.rb`, etc.) avoid exact duplicates for named/keyed resources, but
  `Spree::Imports::Products` may create additional products/variants on
  each run since the import path doesn't dedupe by slug — see Migration
  Notes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a single entry point
  (`Spree::Seeds::All.call`) that seeds the minimum baseline data required
  for a functional store: countries, states, zones, roles, returns
  environment, shipping categories, store credit categories, tax
  categories, digital delivery, a default store, a default stock location,
  an admin user, a store-credit payment method, an API key, and an allowed
  CORS origin.
- **FR-002**: Every individual seed service (`Spree::Seeds::*`) MUST be
  idempotent — safe to call multiple times without creating duplicate rows
  or raising, using `first_or_create!`, `find_or_create_by!`,
  `find_or_initialize_by`, or an explicit existence guard.
- **FR-003**: `Spree::Seeds::All` MUST run inside
  `Spree::Events.disable` and `ActiveRecord::Base.no_touching` so seeding
  does not fire domain events or bump `updated_at` timestamps on
  unrelated records.
- **FR-004**: `rails db:seed` (`spree/core/db/seeds.rb`) MUST delegate to
  `Spree::Seeds::All.call` as the single source of truth — no
  seed-specific logic duplicated in `db/seeds.rb` itself.
- **FR-005**: System MUST provide an optional, separate sample-data path
  (`Spree::SampleData::Loader.call`, wired to `rails spree:load_sample_data`)
  that layers realistic demo content (products, variants, customers,
  completed orders, categories, promotions, channels, markets, posts) on
  top of the baseline seeds.
- **FR-006**: `Spree::SampleData::Loader` MUST detect whether baseline
  seeds are missing (`Spree::Country.find_by(iso: 'US')&.states&.any?` and
  `Spree::Store.default&.persisted?`) and call `Spree::Seeds::All.call`
  first if so, so sample data can be loaded standalone against an empty DB.
- **FR-007**: Sample data that maps to a bulk-import-shaped resource
  (products, customers, product translations) MUST go through the existing
  import pipeline (`Spree::SampleData::ImportRunner` +
  `Spree::Imports::*`) rather than direct model creation, so it exercises
  and stays consistent with the real CSV import feature.
- **FR-008**: `Spree::SampleData::ImportRunner` MUST require an existing
  admin user (`Spree.admin_user_class.first`) as the import's `user`
  owner, and MUST raise a clear error if none exists.
- **FR-009**: The sample-data load MUST temporarily disable
  `Spree::Config[:geocode_addresses]` for its duration and restore the
  prior value afterward (`without_geocoding`), to avoid live geocoding
  calls against fixture addresses.
- **FR-010**: The legacy Rake task `spree_sample:load` MUST remain callable
  but MUST print a deprecation warning and delegate to
  `spree:load_sample_data`.
- **FR-011**: `@spree/cli` MUST expose a `sample-data` command that runs
  `spree:load_sample_data` inside the target project's Docker container,
  as a convenience wrapper (no independent seeding logic in TypeScript).

### Key Entities

- **Spree::Seeds::All**: Orchestrator service; sequences every baseline
  seed class in dependency order (geo → roles → categories/config →
  store/stock location → store-scoped resources).
- **Spree::Seeds::\*** (Countries, States, Zones, Roles, ReturnsEnvironment,
  ShippingCategories, StoreCreditCategories, TaxCategories,
  DigitalDelivery, Stores, StockLocations, AdminUser, PaymentMethods,
  ApiKeys, AllowedOrigins, DefaultReimbursementTypes): One service object
  per baseline concern, each a `Spree::ServiceModule::Base`-backed `call`
  method, independently idempotent.
- **Spree::SampleData::Loader**: Orchestrator for the optional demo-data
  layer; depends on baseline seeds existing (or triggers them) and loads
  a fixed sequence of Ruby fixture files (`db/sample_data/*.rb`) and CSV
  imports (`db/sample_data/*.csv`).
- **Spree::SampleData::ImportRunner**: Generic CSV-import driver — attaches
  a CSV to a `Spree::Imports::*` STI import record owned by the default
  store + first admin user, replays rows through the real import row
  processor, tolerates per-row failure.
- **db/sample_data/\*.rb fixture files** (markets, channels, options,
  promotions, shipping_methods, payment_methods, metafield_definitions,
  orders): plain Ruby scripts `load`-ed by the Loader, executed with full
  Rails app context.
- **db/sample_data/\*.csv** (products.csv, customers.csv,
  product_translations.csv): row-oriented demo content consumed via the
  standard import pipeline, not by the Loader directly.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `app/services/spree/seeds/*.rb` (15 files), `app/services/spree/sample_data/{loader,import_runner}.rb`, `db/seeds.rb`, `db/sample_data/*` (Ruby fixtures + CSVs), `lib/tasks/sample_data.rake` |
| `spree/api` (Store/Admin API v3) | No | No API endpoint; seeding/sample-data is invoked via Rake/console only |
| `packages/dashboard` (admin SPA) | No | Not surfaced in the admin UI |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | No | — |
| `packages/cli` (`@spree/cli`) | Yes | `src/commands/sample-data.ts` registers `spree sample-data`, shelling out to the `spree:load_sample_data` Rake task via `rakeTask()` in `src/docker.ts` |
| `docs/plans/` | No | Stable, long-standing infrastructure; no active/pending `docs/plans/*.md` entry governs it and no architectural change is proposed here |

### API Contract

Not applicable — this feature has no `spree/api` surface. It is invoked via
`rails db:seed`, `rails spree:load_sample_data`, `rails spree_sample:load`
(deprecated alias), the monorepo's `pnpm server:seed` /
`pnpm server:load_sample_data` scripts, or `spree sample-data` via
`@spree/cli`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `Spree::Seeds::All.call` against an empty database
  produces a store capable of completing a full checkout (address →
  shipment → payment) with zero additional manual setup.
- **SC-002**: Running `Spree::Seeds::All.call` a second time against an
  already-seeded database creates zero duplicate `Spree::Store`,
  `Spree::Zone`, `Spree::TaxCategory`, `Spree::ShippingCategory`, or admin
  user rows.
- **SC-003**: Running `Spree::SampleData::Loader.call` against a baseline-
  seeded database results in `Spree::Product.count > 30`,
  `Spree::Variant.count > 100`, non-admin `Spree.user_class` count > 5, and
  `Spree::Order.complete.count >= 2` (existing `loader_spec.rb`
  assertions).
- **SC-004**: A CSV row that fails to import during sample-data loading
  does not abort the run — the loader completes and reports a per-file
  failed-row count.
- **SC-005**: A developer following `CLAUDE.md`'s Development Server table
  can go from a freshly cloned monorepo to a logged-in, populated admin
  dashboard using only `pnpm server:setup` (which runs `db:prepare`,
  implicitly seeding) followed by `pnpm server:load_sample_data`, with no
  manual database work.

## Assumptions

- "Feature" here means the existing seed/sample-data subsystem as built
  today, not a proposed redesign — this document reverse-engineers current
  behavior for spec-kit tracking purposes.
- The `carmen` gem's bundled country/state/subdivision data is treated as
  an external dependency, not something this feature defines.
- Sample data content (specific product names, prices, customer names) is
  illustrative fixture data and intentionally not enumerated as a
  requirement — only the *mechanism* that loads it is in scope.
- `Spree.admin_user_class` and `Spree.user_class` are assumed configured
  per standard Spree installation conventions (see `CLAUDE.md`).
- No new tests were added as part of this migration — existing coverage
  (`spec/services/spree/seeds/*_spec.rb`, `spec/services/spree/sample_data/
  loader_spec.rb`) is treated as the system of record for behavior.

## Migration Notes

- **Gap — sample-data re-run idempotency**: `Spree::SampleData::Loader`
  is not fully idempotent. Ruby fixture files (`markets.rb`, `channels.rb`,
  etc.) mostly guard with `find_or_create_by!`, but `load_products` re-runs
  `Spree::Imports::Products` against the full `products.csv` on every
  invocation; whether the importer dedupes by slug was not verified in this
  pass — flagged for follow-up rather than asserted as a requirement.
- **Gap — no automated coverage for most individual seed classes**: only
  `tax_categories_spec.rb`, `all_spec.rb`, `payment_methods_spec.rb`,
  `returns_environment_spec.rb`, `digital_delivery_spec.rb`, and
  `allowed_origins_spec.rb` exist under `spec/services/spree/seeds/`.
  `Countries`, `States`, `Zones`, `Roles`, `ShippingCategories`,
  `StoreCreditCategories`, `Stores`, `StockLocations`, `AdminUser`,
  `ApiKeys`, `DefaultReimbursementTypes` have no dedicated spec files (only
  indirectly covered via `all_spec.rb` and `loader_spec.rb`).
  `DefaultReimbursementTypes` also appears to duplicate the `RefundReason`
  creation already done in `ReturnsEnvironment` — not called from
  `Seeds::All` at all; likely dead/superseded code, not confirmed.
- **Gap — no `docs/plans/` entry**: per constitution Principle VI, an
  architectural-change plan is only required for significant changes; this
  is stable existing infrastructure, so none was created. If this
  subsystem is redesigned (e.g. pluggable sample-data providers per store
  type), a `docs/plans/` entry should be added at that time.
- **Not migrated**: no code changes were made. This is a reverse-engineered
  spec for existing, already-shipped behavior.
