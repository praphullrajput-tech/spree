---
description: "Task list for feature implementation (brownfield migration — reverse-engineered, all tasks already shipped)"
---

# Tasks: Pricing & Price Lists

**Input**: Design documents from `specs/011-pricing-and-price-lists/`

**Prerequisites**: plan.md, spec.md

**Note**: This is a brownfield reverse-engineering pass. Every task below documents work already present in the codebase (marked `[x]`) — nothing was implemented as part of generating these artifacts.

**Tests**: Existing RSpec/API-integration/Vitest coverage is documented per task; no new tests were written in this pass.

**Organization**: Tasks are grouped by user story from `spec.md`, in priority order.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core` and `spree/api` gems build/load with `Spree::Price`, `Spree::PriceList`, `Spree::PriceRule` registered
- [x] T002 [P] Baseline backend: `cd spree/core && bundle exec rspec spec/models/spree/price_spec.rb spec/models/spree/price_list_spec.rb spec/models/spree/price_rule_spec.rb` passes
- [x] T003 [P] Baseline frontend: `pnpm typecheck && pnpm lint` passes for `packages/dashboard`, `packages/dashboard-ui`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 [spree/core] Migrations: `spree/core/db/migrate/20251110120000_create_spree_price_lists.rb`, `20251110120001_create_spree_price_rules.rb`, `20251110120002_add_price_list_id_to_spree_prices.rb`, `20260112000000_fix_spree_prices_unique_indexes.rb` (partial unique indexes for base vs. override prices), `20260529000001_add_unique_index_to_spree_price_rules.rb` (one rule per type per list)
- [x] T005 [spree/core] `Spree::Price < Spree.base_class` (`spree/core/app/models/spree/price.rb`) — `has_prefix_id :price`, `acts_as_paranoid`, `belongs_to :variant`/`:price_list`, amount/compare_at_amount validations, `discounted?`/`was_discounted?`/`prior_price`
- [x] T006 [spree/core] `Spree::PriceList < Spree.base_class` (`spree/core/app/models/spree/price_list.rb`) — `has_prefix_id :pl`, `acts_as_list scope: :store_id`, `include Spree::SingleStoreResource`, `status` state machine, `product_ids=`/`prices=`/`rules=` flat-payload writers, `add_products`/`remove_products`/`bulk_update_prices`
- [x] T007 [spree/core] `Spree::PriceRule < Spree.base_class` STI base (`spree/core/app/models/spree/price_rule.rb`) + 6 subclasses in `spree/core/app/models/spree/price_rules/`: `ChannelRule`, `CustomerGroupRule`, `MarketRule`, `UserRule`, `VolumeRule`, `ZoneRule`
- [x] T008 [spree/core] `Spree::Pricing::Context` + `Spree::Pricing::Resolver` (`spree/core/lib/spree/core/pricing/{context,resolver}.rb`) — resolution context + best-price lookup
- [x] T009 [spree/core] `Spree::Prices::BulkUpsert` service (`spree/core/app/services/spree/prices/bulk_upsert.rb`) — transactional upsert across base/override partial indexes + stale-placeholder sweep + MySQL fallback path
- [x] T010 [spree/core] `Spree::PriceHistory` model + `20260323000000_create_spree_price_histories.rb` migration, `Price#record_price_history`/`#should_record_price_history?`/`#prior_price` (EU Omnibus, shared with `docs/plans/5.4-6.0-eu-legal-compliance.md`)
- [x] T011 [spree/core] Ransack allowlists on `Spree::Price` (`whitelisted_ransackable_attributes`/`_associations`/`_scopes`) and `Spree::PriceList` (`status`, `match_policy`, `starts_at`, `ends_at`)
- [x] T012 [packages/dashboard] i18next keys under `admin.products.price_lists.*` in `packages/dashboard/src/locales/en.json` (messages, errors, validation strings referenced by `use-price-lists.ts`)

**Checkpoint**: Foundation shipped — user story implementation below builds on it.

---

## Phase 3: User Story 1 - Merchant sets a base price and compare-at price (Priority: P1) 🎯 MVP

### Tests for User Story 1

- [x] T013 [P] [US1] RSpec model spec `spree/core/spec/models/spree/price_spec.rb` — amount/compare_at_amount validation, `discounted?`, `remove_compare_at_amount_if_equals_amount`, price-history recording
- [x] T014 [P] [US1] API integration spec `spree/api/spec/integration/admin/prices_spec.rb` — create/update happy path + simple 422s

### Implementation for User Story 1

- [x] T015 [US1] `Spree::Price` model (`spree/core/app/models/spree/price.rb`) — amount/compare_at_amount accessors, money display methods, `ensure_currency`
- [x] T016 [US1] `Admin::PricesController` (`spree/api/app/controllers/spree/api/v3/admin/prices_controller.rb`) — CRUD via `ResourceController`, `permitted_params` resolves `variant_id`/`price_list_id` through current-store scopes
- [x] T017 [US1] `Spree::Api::V3::PriceSerializer` + `Admin::PriceSerializer` (read/write field symmetry: `amount`, `compare_at_amount`, `currency`, `price_list_id`, admin-only `variant_id`/`created_at`/`updated_at`)
- [x] T018 [US1] `Spree::PriceHistory` recording wired via `after_save :record_price_history` on `Price`

**Checkpoint**: Base price CRUD + history recording functional independently.

---

## Phase 4: User Story 2 - Merchant creates a price list with rules (Priority: P1)

### Tests for User Story 2

- [x] T019 [P] [US2] RSpec model specs `spree/core/spec/models/spree/price_list_spec.rb`, `spree/core/spec/models/spree/price_rule_spec.rb`, `spree/core/spec/models/spree/price_rules/*_spec.rb`
- [x] T020 [P] [US2] API integration spec `spree/api/spec/integration/admin/price_lists_spec.rb` — nested `rules`/`product_ids`/`prices` PATCH payload

### Implementation for User Story 2

- [x] T021 [US2] `Spree::PriceList` typed-association reconciliation for `rules=` (`assign_typed_association`) and flat writers for `product_ids=`/`prices=`
- [x] T022 [US2] `add_products`/`remove_products` placeholder-price materialization keyed on store `supported_currencies_list`
- [x] T023 [US2] `Admin::PriceListsController` (`spree/api/app/controllers/spree/api/v3/admin/price_lists_controller.rb`) — CRUD, `reject_foreign_membership` cross-store guard, `price_rule_types` discovery endpoint
- [x] T024 [US2] `Admin::PriceListSerializer` + `Admin::PriceRuleSerializer` (conditional `markets`/`customer_groups`/`channels`/`customers` embeds per rule type)
- [x] T025 [US2] `packages/dashboard/src/schemas/price-list.ts` — `priceListFormSchema`, `PriceRuleFormDraft`, `ruleDraftFromRule`/`ruleDraftFromType`/`ruleDraftToPayload`
- [x] T026 [US2] `packages/dashboard/src/hooks/use-price-lists.ts` — `usePriceList`/`useCreatePriceList`/`useUpdatePriceList`/`useDeletePriceList`/`useActivatePriceList`/`useDeactivatePriceList`/`usePriceRuleTypes`
- [x] T027 [US2] `packages/dashboard/src/routes/_authenticated/$storeId/products/price-lists/{index,new}.tsx` + `$priceListId/index.tsx` detail/edit route

**Checkpoint**: Price list CRUD with rules + product membership functional independently.

---

## Phase 5: User Story 3 - Storefront resolves the correct price for a variant (Priority: P1)

### Tests for User Story 3

- [x] T028 [P] [US3] RSpec spec for `spree/core/lib/spree/core/pricing/resolver.rb` (list-vs-base-price precedence, position ordering, empty placeholder fallback)

### Implementation for User Story 3

- [x] T029 [US3] `Spree::Pricing::Context` value object with `.from_currency`/`.from_order` constructors and `#cache_key`
- [x] T030 [US3] `Spree::Pricing::Resolver#resolve` — applicable-list iteration via `PriceList.for_context`/`Spree::Current.price_lists`, non-zero currency match, base-price fallback, placeholder `Price.new`
- [x] T031 [US3] `PriceList#applicable?`/`#rules_applicable?`/`#within_date_range?` — match-policy (`all`/`any`) evaluation against each rule's `#applicable?(context)`

**Checkpoint**: Price resolution functional independently of the admin CRUD surface.

---

## Phase 6: User Story 4 - Merchant bulk-edits prices via a spreadsheet grid (Priority: P2)

### Tests for User Story 4

- [x] T032 [P] [US4] RSpec spec `spree/core/spec/services/spree/prices/bulk_upsert_spec.rb` — base/override batch routing, dedup last-write-wins, MySQL fallback path, stale-placeholder sweep
- [x] T033 [P] [US4] Vitest `packages/dashboard/src/components/spree/bulk-price-editor/normalize-money.test.ts` — locale-aware decimal normalization before submit

### Implementation for User Story 4

- [x] T034 [US4] `Admin::PricesController#bulk_upsert`/`#bulk_destroy` — cross-store validation (`invalid_prices`), decode prefixed ids, delegate to `Spree::Prices::BulkUpsert`
- [x] T035 [US4] `packages/dashboard/src/hooks/use-prices.ts` — `useBulkUpsertPrices` mutation hook (no toast; caller renders inline dirty-state UI)
- [x] T036 [US4] `packages/dashboard-ui/src/spree/bulk-price-table.tsx` + `data-grid/{data-grid.tsx,use-data-grid-keyboard.ts}` — headless spreadsheet grid primitive (keyboard nav, no provider/hook imports)
- [x] T037 [US4] `packages/dashboard/src/components/spree/bulk-price-editor/{bulk-price-editor,bulk-price-editor-dialog,product-bulk-price-editor,currency-parts,normalize-money}.ts(x)` — app-level editor wiring the grid to `useBulkUpsertPrices`

**Checkpoint**: Bulk spreadsheet editing functional independently.

---

## Phase 7: User Story 5 - Merchant schedules and activates a price list (Priority: P3)

### Tests for User Story 5

- [x] T038 [P] [US5] RSpec spec covering `PriceList` `status` state machine transitions (`activate`/`deactivate`/`schedule`) and `.for_context`/`#currently_active?`

### Implementation for User Story 5

- [x] T039 [US5] `PriceList` `state_machine :status` (`draft`/`active`/`scheduled`/`inactive`) + `starts_at_before_ends_at` validation
- [x] T040 [US5] `Admin::PriceListsController#activate`/`#deactivate` — future-`starts_at` routes to `schedule` event instead of `activate`
- [x] T041 [US5] `packages/dashboard/src/hooks/use-price-lists.ts` `useActivatePriceList`/`useDeactivatePriceList` mutation hooks

**Checkpoint**: Full lifecycle functional independently.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T042 [P] Type-generation pipeline output present: `packages/admin-sdk/src/types/generated/{Price,PriceList,PriceRule}.ts`
- [x] T043 Full backend suite passes for `spree/core`/`spree/api` (per-gem `bundle exec rspec`)
- [x] T044 Full frontend suite passes: `pnpm typecheck && pnpm lint && pnpm test` at workspace root
- [x] T045 Documented gap (see spec.md Migration Notes): no dedicated `docs/plans/` entry for Price Lists/PriceRule beyond the adjacent EU Omnibus plan — flagged, not retroactively created (non-destructive migration pass)
- [x] T046 Documented gap (see spec.md Migration Notes): `Admin::PriceListsController#prices` action has no matching route in `spree/api/config/routes.rb` — flagged as dead/orphaned code, not removed or fixed in this pass

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → all User Stories (Phases 3-7), which shipped independently of each other in practice (US1 base pricing, US2 price lists, and US3 resolution are all P1 but touch disjoint files) → **Polish (Phase 8)**.
- US4 (bulk editor) depends on US1 (`Price` model) and US2 (`PriceList#bulk_update_prices`) being in place.
- US5 (lifecycle) depends on US2 (`PriceList` existing) but is independent of US1/US3/US4.

## Notes

- This tasks.md reflects a **completed, shipped feature** discovered via reverse engineering — all items are checked because the corresponding code already exists in the repository, not because work was performed during this migration pass.
- No code was written or modified to produce this file; only `spec.md`, `plan.md`, and `tasks.md` under `specs/011-pricing-and-price-lists/` were created.
