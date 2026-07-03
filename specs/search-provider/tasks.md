---

description: "Task list for Search Provider — fully shipped in 5.4; 6.0 metafield faceting pending"
---

# Tasks: Search Provider

**Status**: Fully shipped in 5.4; Phase 2 (metafield faceting) pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Provider base + implementations | `spree/core/app/models/spree/search_provider/` |
| Concerns | `spree/core/app/models/concerns/spree/` |
| Presenter | `spree/core/app/presenters/spree/search_provider/` |
| Background jobs | `spree/core/app/jobs/spree/search_provider/` |
| Store API controllers | `spree/api/app/controllers/spree/api/v3/store/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Rake tasks | `spree/core/lib/tasks/search.rake` |
| Dashboard-core hooks | `packages/dashboard-core/src/hooks/` |
| Dashboard-core registry | `packages/dashboard-core/src/lib/` |
| Developer docs | `docs/developer/how-to/` |

---

## Phase 1: Core + API + SPA ✅

### Backend — Provider Base & Implementations

- [x] T001 `spree/core/app/models/spree/search_provider/base.rb` — abstract contract: `search_and_filter`, `filters`, `index`, `remove`, `remove_by_id`, `reindex`, `index_batch`, `ensure_index_settings!`; `self.indexing_required?`; locale/currency helpers
- [x] T002 `spree/core/app/models/spree/search_provider/search_result.rb` — Struct: `products`, `total_count`, `pagy`
- [x] T003 `spree/core/app/models/spree/search_provider/filters_result.rb` — Struct: `filters`, `sort_options`, `default_sort`, `total_count`
- [x] T004 `spree/core/app/models/spree/search_provider/database.rb` — SQL/ILIKE + Ransack; `FiltersAggregator` for disjunctive facets; sort scopes: `price`, `-price`, `best_selling`; `indexing_required? = false`
- [x] T005 `spree/core/app/models/spree/search_provider/meilisearch.rb` — Meilisearch client; composite document IDs (`prod_abc_en_USD`); structured filtering; disjunctive faceting via multi-search; `indexing_required? = true`; `Pagy::MeilisearchPaginator`

### Backend — Concerns & Presenter

- [x] T006 `spree/core/app/models/concerns/spree/search_indexable.rb` — included in `Spree::Product`; after-commit: `enqueue_search_index` (create/update), `enqueue_search_removal` (destroy); sync methods: `add_to_search_index`, `remove_from_search_index`; `search_presentation(store)`
- [x] T007 `spree/core/app/models/concerns/spree/searchable.rb` — `sanitize_query_for_search`, `search_condition`; ILIKE with `_`/`%` escaping; encrypted column support (equality-only match)
- [x] T008 `spree/core/app/presenters/spree/search_provider/product_presenter.rb` — one document per market × locale; composite ID; translated fields + pricing per currency + categories + option values + tags; `preload_associations_lazily`; registered in `Spree::Dependencies`

### Backend — Jobs

- [x] T009 `spree/core/app/jobs/spree/search_provider/index_job.rb` — queue `Spree.queues.search`; polynomial backoff, 5 attempts; discard `ActiveJob::DeserializationError`
- [x] T010 `spree/core/app/jobs/spree/search_provider/remove_job.rb` — same queue + retry policy; params: `prefixed_id`, `store_id`

### Backend — Store API

- [x] T011 `spree/api/app/controllers/concerns/spree/api/v3/store/search_provider_support.rb` — `search_query`, `search_filters`, `search_provider` helpers; decodes prefixed IDs in Ransack predicates
- [x] T012 `spree/api/app/controllers/spree/api/v3/store/products_controller.rb` — includes `SearchProviderSupport`; overrides `collection` to delegate to provider
- [x] T013 `spree/api/app/controllers/spree/api/v3/store/products/filters_controller.rb` — 15-minute cache keyed on store/currency/locale/category/query/product count/max updated_at

### Backend — Configuration & Rake

- [x] T014 `spree/core/lib/spree/core.rb` — `Spree.search_provider` accessor; default `'Spree::SearchProvider::Database'`
- [x] T015 `spree/core/lib/spree/core/dependencies.rb` — `search_product_presenter` dependency registered
- [x] T016 `spree/core/lib/tasks/search.rake` — `spree:search:reindex` iterates all stores

### Backend — Specs

- [x] T017 `spree/core/spec/models/spree/search_provider/base_spec.rb` — contract tests
- [x] T018 `spree/core/spec/models/spree/search_provider/database_spec.rb` — search, filters, disjunctive facets, sort options
- [x] T019 `spree/core/spec/models/spree/search_provider/meilisearch_spec.rb` — document composition, composite IDs, filter conditions
- [x] T020 `spree/core/spec/models/spree/search_provider/meilisearch_integration_spec.rb` — live Meilisearch integration
- [x] T021 `spree/core/spec/models/concerns/spree/search_indexable_spec.rb` — after-commit hooks, job enqueueing

### Frontend — Admin Command Palette

- [x] T022 `packages/dashboard-core/src/hooks/use-global-search.ts` — debounced (200ms, min 2 chars), parallel queries per resource (limit 5), 30s stale / 60s GC
- [x] T023 `packages/dashboard-core/src/lib/search-registry.ts` — extensible registry with `useSyncExternalStore`; default entries: products, orders, customers, promotions
- [x] T024 Command palette Cmd+K toggle wired to `use-command-palette.tsx`

### Documentation

- [x] T025 `docs/developer/how-to/custom-search-provider.mdx` — custom provider walkthrough (contract table, ProductPresenter, indexing lifecycle, prefixed ID requirements)

**Checkpoint**: Database + Meilisearch providers; disjunctive faceting; filters caching; admin command palette; developer docs ✅

---

## Phase 2: 6.0 — Metafield Faceting (PENDING)

Per `5.4-search-provider.md` (6.0 section):

- [ ] T026 `MetafieldDefinition` facet flag — merchants designate which metafields appear as filters
- [ ] T027 `ProductPresenter` — include metafield values in indexed documents
- [ ] T028 Meilisearch provider — configure metafield attributes as filterable + facetable
- [ ] T029 Database provider — extend `FiltersAggregator` to handle metafield facets
- [ ] T030 Filters endpoint response — include metafield facets alongside option-type facets

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| Metafield faceting not implemented | Low | Planned for 6.0; current option-type faceting covers most use cases |
| Autocomplete/typeahead endpoint not implemented | Low | No dedicated `GET /products/suggestions` endpoint; admin command palette covers admin use case |
| `meilisearch_integration_spec.rb` requires live instance | Low | By design; guarded by env variable; CI skips when Meilisearch unavailable |
