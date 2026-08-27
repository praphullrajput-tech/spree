# Implementation Plan: Sample Data & Seeds

**Branch**: `026-sample-data-seeds` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-sample-data-seeds/spec.md`

**Note**: This plan is reverse-engineered from an already-shipped feature (brownfield migration), not authored ahead of implementation.

## Summary

A two-layer bootstrap system: `Spree::Seeds::All` seeds the minimum baseline data (geography, zones, tax/shipping categories, a default store + stock location, an admin user, a store-credit payment method) required for any store to function, and `Spree::SampleData::Loader` optionally layers realistic demo content (products, customers, completed orders, promotions, channels, markets) on top by routing product/customer/translation data through the real CSV import pipeline (`Spree::SampleData::ImportRunner` → `Spree::Imports::*`) rather than direct AR inserts. `@spree/cli` wraps the sample-data Rake task for Docker-based projects.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core`) for the seed/sample-data mechanism; TypeScript (`@spree/cli`) for the convenience wrapper only.

**Primary Dependencies**: `carmen` (country/state data), `Spree::ServiceModule::Base` (seed service objects), `Spree::Imports::*` (real import pipeline reused for sample data), `Spree::Events.disable` / `ActiveRecord::Base.no_touching` (seed-time side-effect suppression).

**Storage**: PostgreSQL/SQLite3 via ActiveRecord — no new tables; seeds/sample data populate existing models only.

**Testing**: RSpec (`spree/core/spec/services/spree/seeds/*_spec.rb`, `spree/core/spec/services/spree/sample_data/loader_spec.rb`); no frontend or E2E coverage (feature has no UI surface).

**Target Platform**: Rails console / Rake tasks (`rails db:seed`, `rails spree:load_sample_data`, deprecated `rails spree_sample:load`), invoked directly or via `pnpm server:seed` / `pnpm server:load_sample_data` / `spree sample-data` (CLI).

**Project Type**: Monorepo — `spree/core` (all seed/sample-data logic) + `packages/cli` (thin Rake-task wrapper only).

**Performance Goals**: N/A — one-time/idempotent setup operation, not a request-path concern.

**Constraints**: Must remain safe to re-run (idempotent for baseline seeds; sample-data re-runs are a known, documented gap — see spec.md Migration Notes). Must not fire domain events or webhooks while seeding (`Spree::Events.disable`).

**Scale/Scope**: Baseline seeds: ~15 seed service classes. Sample data: ~10 Ruby fixture files + 3 CSV files (products, customers, product_translations), producing 30+ products / 100+ variants / 5+ customers / 2+ complete orders per the existing `loader_spec.rb` assertions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Entirely within `spree/core` (seed/sample-data logic) with a thin `packages/cli` wrapper that only shells out to a Rake task — no boundary crossing, no direct cross-package coupling. PASS.
- **II. Admin API Is the Only Frontend Data Source**: N/A — this feature has no `packages/dashboard` surface; it is a backend/ops mechanism only, never consumed by the SPA.
- **III. Read/Write Field Symmetry**: N/A — no serializer or API endpoint exists for this feature.
- **IV. Test-Backed**: Partially covered — see spec.md Migration Notes for the list of seed classes with no dedicated spec file (covered only indirectly via `all_spec.rb`/`loader_spec.rb`). No violation being introduced by this migration (no new code), but a real pre-existing coverage gap.
- **V. Translations and Prefixed IDs**: N/A — no user-visible strings (developer/ops tooling) and no new resource IDs exposed via API.
- **VI. `docs/plans/` for Architectural Changes**: N/A — stable existing infrastructure, no architectural change proposed by this migration. Per spec.md's Migration Notes, a plan entry should be added only if this subsystem is later redesigned.

No violations. Complexity Tracking table intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/026-sample-data-seeds/
├── plan.md              # This file
├── spec.md              # Reverse-engineered specification
└── tasks.md             # Reverse-engineered task list (all complete)
```

### Source Code (repository root)

```text
# spree/core — baseline seeds + sample-data loader
spree/core/
├── app/services/spree/seeds/
│   ├── all.rb                          # orchestrator
│   ├── countries.rb, states.rb, zones.rb
│   ├── roles.rb, returns_environment.rb
│   ├── shipping_categories.rb, store_credit_categories.rb, tax_categories.rb
│   ├── digital_delivery.rb
│   ├── stores.rb, stock_locations.rb
│   ├── admin_user.rb, payment_methods.rb, api_keys.rb, allowed_origins.rb
│   └── default_reimbursement_types.rb  # flagged as possibly dead/superseded — see Migration Notes
├── app/services/spree/sample_data/
│   ├── loader.rb                       # orchestrator, detects+triggers baseline seeds if missing
│   └── import_runner.rb                # generic CSV-import driver reusing Spree::Imports::*
├── db/seeds.rb                         # delegates to Spree::Seeds::All.call
├── db/sample_data/
│   ├── markets.rb, channels.rb, options.rb, promotions.rb
│   ├── shipping_methods.rb, payment_methods.rb, metafield_definitions.rb, orders.rb
│   └── products.csv, customers.csv, product_translations.csv
├── lib/tasks/sample_data.rake          # spree:load_sample_data + deprecated spree_sample:load alias
└── spec/services/spree/seeds/{tax_categories,all,payment_methods,returns_environment,digital_delivery,allowed_origins}_spec.rb
    spec/services/spree/sample_data/loader_spec.rb

# packages/cli — convenience wrapper only
packages/cli/src/commands/sample-data.ts   # registerSampleDataCommand → rakeTask('spree:load_sample_data', ...)
```

**Structure Decision**: Backend-only (`spree/core`) plus a thin `packages/cli` Rake-task wrapper. No `spree/api`, no `packages/dashboard`/`dashboard-core`/`dashboard-ui`, no `packages/sdk`/`admin-sdk` involvement — this is invocation tooling, not a user-facing or API-exposed feature.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
</content>
