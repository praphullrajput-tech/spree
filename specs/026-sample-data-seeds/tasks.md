---

description: "Task list for feature migration (retrospective — feature already shipped)"
---

# Tasks: Sample Data & Seeds

**Input**: Design documents from `/specs/026-sample-data-seeds/`

**Prerequisites**: plan.md, spec.md

**Status**: migrated — all tasks below reflect code that already exists in the repository. This is a retrospective record, not pending work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent files, no dependency ordering required
- **[Story]**: US1 = baseline seeds, US2 = sample/demo data, US3 = CLI wrapper

## Phase 1: Baseline Seeds [US1]

- [x] T001 `spree/core/app/services/spree/seeds/all.rb` — orchestrator, sequences every seed class in dependency order, wrapped in `Spree::Events.disable` + `ActiveRecord::Base.no_touching`
- [x] T002 [P] `spree/core/app/services/spree/seeds/countries.rb`, `states.rb` — populate from the `carmen` gem
- [x] T003 [P] `spree/core/app/services/spree/seeds/zones.rb` — `EU_VAT`, `UK_VAT`, continent zones + members
- [x] T004 [P] `spree/core/app/services/spree/seeds/roles.rb`
- [x] T005 [P] `spree/core/app/services/spree/seeds/returns_environment.rb`
- [x] T006 [P] `spree/core/app/services/spree/seeds/shipping_categories.rb`, `store_credit_categories.rb`, `tax_categories.rb`
- [x] T007 [P] `spree/core/app/services/spree/seeds/digital_delivery.rb`
- [x] T008 `spree/core/app/services/spree/seeds/stores.rb` — default store, no-ops if one already exists
- [x] T009 `spree/core/app/services/spree/seeds/stock_locations.rb` — default stock location scoped to the default store's country
- [x] T010 `spree/core/app/services/spree/seeds/admin_user.rb` — reads `ADMIN_EMAIL`/`ADMIN_PASSWORD`/`ADMIN_FIRST_NAME`/`ADMIN_LAST_NAME`, no-ops if `Spree.admin_user_class.present?` is false or an admin already exists
- [x] T011 [P] `spree/core/app/services/spree/seeds/payment_methods.rb` — default store-credit payment method
- [x] T012 [P] `spree/core/app/services/spree/seeds/api_keys.rb`, `allowed_origins.rb`
- [x] T013 `spree/core/app/services/spree/seeds/default_reimbursement_types.rb` — flagged in spec.md Migration Notes as possibly dead/superseded (not called from `Seeds::All`); left as-is, not removed, since this migration is documentation-only
- [x] T014 `spree/core/db/seeds.rb` — thin delegate to `Spree::Seeds::All.call`

## Phase 2: Sample/Demo Data [US2]

- [x] T015 `spree/core/app/services/spree/sample_data/loader.rb` — orchestrator; detects missing baseline via `Spree::Country.find_by(iso: 'US')&.states&.any?` + `Spree::Store.default&.persisted?` and calls `Spree::Seeds::All.call` first if needed; wraps address-related steps in `without_geocoding`
- [x] T016 `spree/core/app/services/spree/sample_data/import_runner.rb` — generic CSV-import driver; requires `Spree.admin_user_class.first` to exist (raises a clear error otherwise); attaches CSV to a `Spree::Imports::*` STI record owned by the default store + first admin; tolerates and counts per-row failures
- [x] T017 [P] `spree/core/db/sample_data/markets.rb`, `channels.rb`, `options.rb`, `promotions.rb`, `shipping_methods.rb`, `payment_methods.rb`, `metafield_definitions.rb`, `orders.rb` — Ruby fixture scripts, `load`-ed with full Rails context
- [x] T018 [P] `spree/core/db/sample_data/products.csv` → `Spree::Imports::Products` (via `ImportRunner`), then published on the default channel; categories derived from the CSV
- [x] T019 [P] `spree/core/db/sample_data/customers.csv` → `Spree::Imports::Customers` (via `ImportRunner`)
- [x] T020 [P] `spree/core/db/sample_data/product_translations.csv` → `Spree::Imports::ProductTranslations` (via `ImportRunner`); skipped silently if the CSV is absent
- [x] T021 `spree/core/lib/tasks/sample_data.rake` — `spree:load_sample_data` task; deprecated `spree_sample:load` alias prints a warning and delegates

## Phase 3: CLI Wrapper [US3]

- [x] T022 `packages/cli/src/commands/sample-data.ts` — `registerSampleDataCommand`, shells out to `rakeTask('spree:load_sample_data', ctx.projectDir)` (`packages/cli/src/docker.ts`), no independent logic

## Phase 4: Existing Test Coverage (partial — see Migration Notes)

- [x] T023 [P] `spree/core/spec/services/spree/seeds/all_spec.rb`
- [x] T024 [P] `spree/core/spec/services/spree/seeds/{tax_categories,payment_methods,returns_environment,digital_delivery,allowed_origins}_spec.rb`
- [x] T025 `spree/core/spec/services/spree/sample_data/loader_spec.rb` — asserts `Spree::Product.count > 30`, `Variant.count > 100`, non-admin user count > 5, `Order.complete.count >= 2`

## Notes

- Every phase above is already implemented; nothing here is scheduled work.
- Per spec.md's Migration Notes: `Countries`, `States`, `Zones`, `Roles`, `ShippingCategories`, `StoreCreditCategories`, `Stores`, `StockLocations`, `AdminUser`, `ApiKeys`, and `DefaultReimbursementTypes` have no dedicated spec file — covered only indirectly via `all_spec.rb`/`loader_spec.rb`. Not remediated as part of this migration (documentation-only).
- Per spec.md's Migration Notes: sample-data re-runs are not fully idempotent for product imports (`load_products` re-runs the full CSV import each time); not remediated here.
</content>
