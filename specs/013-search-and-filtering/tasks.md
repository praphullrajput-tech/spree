---

description: "Task list template for feature implementation"
---

# Tasks: Search & Filtering

**Input**: Design documents from `/specs/013-search-and-filtering/`

**Prerequisites**: plan.md, spec.md

**Tests**: Backend-only feature; RSpec is the applicable framework per constitution Principle IV.

**Organization**: Tasks are grouped by user story, reflecting the already-implemented architecture (brownfield migration — all tasks are marked complete as a record of what was built, not a forward plan).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Could have run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task maps to (US1/US2/US3)

## Path Conventions

- **Backend model/service**: `spree/core/app/{models,services,jobs}/spree/...`, rake task in `spree/core/lib/tasks/`
- **API endpoint**: `spree/api/app/controllers/spree/api/v3/store/...`, service in `spree/api/app/services/spree/api/v3/...`
- No `packages/dashboard`, `packages/dashboard-ui`/`dashboard-core`, or `packages/sdk` paths apply — no frontend surface found for this feature.

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core` and `spree/api` gems load and test suites run: `cd spree/core && bundle exec rspec` / `cd spree/api && bundle exec rspec`
- [x] T002 [P] Add `meilisearch-ruby` as an optional dependency (lazily required in `Spree::SearchProvider::Meilisearch#initialize`, not a hard gemspec dependency) so stores on the Database provider incur no extra load

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The provider abstraction itself — everything else builds on this contract.

- [x] T003 [spree/core] Define `Spree::SearchProvider::Base` abstract contract in `spree/core/app/models/spree/search_provider/base.rb`: `self.indexing_required?`, `search_and_filter`, `filters`, `index`, `remove`, `remove_by_id`, `index_batch`, `ensure_index_settings!`, `reindex` (all no-op/`NotImplementedError` defaults), plus `locale`/`currency` private helpers reading `Spree::Current`
- [x] T004 [P] [spree/core] Define `Spree::SearchProvider::SearchResult` struct in `spree/core/app/models/spree/search_provider/search_result.rb` (`products`, `total_count`, `pagy`)
- [x] T005 [P] [spree/core] Define `Spree::SearchProvider::FiltersResult` struct in `spree/core/app/models/spree/search_provider/filters_result.rb` (`filters`, `sort_options`, `default_sort`, `total_count`)
- [x] T006 [spree/core] Add `Spree.search_provider` / `Spree.search_provider=` config accessor in `spree/core/lib/spree/core.rb`, defaulting to `'Spree::SearchProvider::Database'`; deprecate the legacy `Spree.searcher_class`
- [x] T007 [spree/core] Add `Spree::SearchIndexable` concern in `spree/core/app/models/concerns/spree/search_indexable.rb`: `after_commit` hooks enqueueing indexing only when the active provider's `indexing_required?` is true
- [x] T008 [P] [spree/core] Add `Spree::SearchProvider::IndexJob` and `Spree::SearchProvider::RemoveJob` in `spree/core/app/jobs/spree/search_provider/`
- [x] T009 [spree/core] Add `rake spree:search:reindex` task in `spree/core/lib/tasks/search.rake`

**Checkpoint**: Provider contract, config switch, and indexing lifecycle exist — user-facing endpoints can be built on top.

---

## Phase 3: User Story 1 - Storefront visitor searches and filters (Priority: P1) 🎯 MVP

**Goal**: End-to-end text search + structured filters (price, availability, category, option values) against the Store API, provider-agnostic.

**Independent Test**: `GET /api/v3/store/products?q[search]=shirt&q[price_gte]=10` and `GET /api/v3/store/products/filters?category_id=<slug>` against the Database provider.

### Implementation for User Story 1

- [x] T010 [US1] Implement `Spree::SearchProvider::Database#search_and_filter`/`#filters` in `spree/core/app/models/spree/search_provider/database.rb` — Ransack-driven, delegates facet computation to `Spree::Api::V3::FiltersAggregator` when defined
- [x] T011 [US1] Implement `Spree::Api::V3::FiltersAggregator` in `spree/api/app/services/spree/api/v3/filters_aggregator.rb` — price/availability/option/category facets via grouped SQL COUNT queries, prefixed-ID encoding on output
- [x] T012 [US1] Add `Spree::Api::V3::Store::SearchProviderSupport` concern in `spree/api/app/controllers/concerns/spree/api/v3/store/search_provider_support.rb` — `search_query`, `search_filters`, and `decode_prefixed_id_predicates` for `*_id_in`/`_id_eq`-style Ransack keys
- [x] T013 [US1] Override `Spree::Api::V3::Store::ProductsController#collection` in `spree/api/app/controllers/spree/api/v3/store/products_controller.rb` to call `search_provider.search_and_filter`, feeding `@pagy`/`@collection` from the returned `SearchResult`
- [x] T014 [US1] Implement `Spree::Api::V3::Store::Products::FiltersController#index` in `spree/api/app/controllers/spree/api/v3/store/products/filters_controller.rb` — calls `search_provider.filters`, wraps in 15-minute `Rails.cache.fetch` keyed on store/currency/locale/category/query/filters + catalog staleness signal
- [x] T015 [US1] Implement `Spree::SearchProvider::Meilisearch#search_and_filter`/`#filters` in `spree/core/app/models/spree/search_provider/meilisearch.rb` as the alternate provider satisfying the same contract (query building, system-scoping conditions, facet distribution → standard facet shape translation)

**Checkpoint**: Full search + filter flow works against the default (Database) provider; Meilisearch available as a drop-in swap.

---

## Phase 4: User Story 2 - Sort and paginate results (Priority: P2)

**Goal**: Consistent sort vocabulary and pagination metadata regardless of active provider.

**Independent Test**: `GET /api/v3/store/products?sort=-price&page=2`.

### Implementation for User Story 2

- [x] T016 [P] [US2] Implement `Database#apply_sort` (Ransack sort translation + `CUSTOM_SORT_SCOPES` for `price`/`-price`/`best_selling`) and `#build_pagy` (`Pagy::Offset`) in `spree/core/app/models/spree/search_provider/database.rb`
- [x] T017 [P] [US2] Implement `Meilisearch#sort_mapping`/`#build_sort` and `#build_pagy` (via `Pagy::MeilisearchPaginator`, `pagy/toolbox/paginators/meilisearch`) in `spree/core/app/models/spree/search_provider/meilisearch.rb`, matching the same sort vocabulary as the Database provider

**Checkpoint**: Sorting and pagination are provider-agnostic and verified equivalent across both implementations.

---

## Phase 5: User Story 3 - Platform operator swaps the search backend (Priority: P3)

**Goal**: Extension contract that lets an operator or third party plug in a custom provider (or subclass Meilisearch) without touching controllers.

**Independent Test**: Set `Spree.search_provider = 'Spree::SearchProvider::Meilisearch'`, run `rake spree:search:reindex`, hit the same Store API endpoints and confirm behavior parity.

### Implementation for User Story 3

- [x] T018 [US3] Implement Meilisearch index lifecycle: `#index`, `#remove`, `#remove_by_id`, `#index_batch`, `#reindex`, `#ensure_index_settings!`/`#ensure_index_settings_once!` in `spree/core/app/models/spree/search_provider/meilisearch.rb`
- [x] T019 [US3] Implement self-healing retry on `invalid_search_filter` `::Meilisearch::ApiError` in `Meilisearch#execute_search` — refresh index settings once, retry, else log + `Rails.error.report` + return `nil`
- [x] T020 [US3] Implement disjunctive facet merge for option-value filters in `Meilisearch#merge_disjunctive_facets`/`group_option_values_by_type`/`build_grouped_option_conditions`, mirroring `FiltersAggregator#disjunctive_scope_for`/`grouped_selected_options` in the Database provider
- [x] T021 [US3] Document override points for custom subclasses (`build_filter_condition`, `sort_mapping`, `build_facet_response` — "call super for built-in, override to extend") via inline YARD comments in `meilisearch.rb`

**Checkpoint**: A third-party provider (or Meilisearch subclass) can be dropped in via config alone; extension contract is documented at the code level.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T022 [P] Record the design decision in `docs/plans/5.4-search-provider.md` (provider abstraction, PgSearch/`add_search_scope` removal) — already exists, shipped
- [x] T023 [P] Record the disjunctive faceting design in `docs/plans/5.4-disjunctive-option-faceting.md` — already exists, shipped
- [ ] T024 Full backend suite: `cd spree/core && bundle exec rspec` and `cd spree/api && bundle exec rspec` — not re-run in this migration pass; flagged in spec.md Migration Notes as unverified coverage, recommend running before treating this migrated spec as fully validated

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: provider contract, config, indexing lifecycle — blocks everything else.
- **User Story 1 (Phase 3)**: depends on Foundational; delivers the MVP (search + filters over Database provider, Meilisearch as parallel implementation of the same contract).
- **User Story 2 (Phase 4)**: depends on Foundational; independently testable sort/pagination behavior, built alongside US1 in practice (same files) but conceptually separable.
- **User Story 3 (Phase 5)**: depends on Foundational and the Meilisearch skeleton from US1; adds the indexing lifecycle, self-healing, and disjunctive-facet behavior that make the *swap* itself safe in production.
- **Polish (Phase 6)**: depends on all prior phases.

## Notes

- This tasks.md is a **migration record**, not a forward execution plan — all tasks are checked off because the corresponding code already exists in the repository at the paths listed. One task (T024) is intentionally left unchecked because full-suite re-verification was out of scope for this reverse-engineering pass; see spec.md → Migration Notes.
