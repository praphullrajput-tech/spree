# Implementation Plan: Search & Filtering

**Branch**: `013-search-and-filtering` | **Date**: 2026-08-25 | **Spec**: `specs/013-search-and-filtering/spec.md`

**Input**: Feature specification from `/specs/013-search-and-filtering/spec.md`

**Note**: This plan documents an already-implemented feature (brownfield migration). It records the architecture as built, not a forward-looking implementation sequence.

## Summary

Product search, filtering, sorting, and facet aggregation on the Store API are abstracted behind `Spree::SearchProvider::Base`, a pluggable strategy interface. Two providers ship today: `Spree::SearchProvider::Database` (default, SQL/Ransack-based, no external dependency) and `Spree::SearchProvider::Meilisearch` (typo-tolerant, faceted, requires background indexing via `Spree::SearchIndexable` + `IndexJob`/`RemoveJob`). `Spree::Api::V3::Store::ProductsController#collection` and `Products::FiltersController#index` are the only two call sites; both are provider-agnostic — they call `search_provider.search_and_filter` / `.filters` and never branch on which provider is active.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines) — backend only; no frontend surface for this feature was found.

**Primary Dependencies**: Ransack (Database provider filter/sort translation), Pagy (`Pagy::Offset` for Database, `Pagy::MeilisearchPaginator` for Meilisearch, via `pagy/toolbox/paginators/meilisearch`), CanCanCan (`accessible_by`), `meilisearch-ruby` (optional gem, lazily `require`d only when the Meilisearch provider is instantiated), Active Job (`Spree::SearchProvider::IndexJob`/`RemoveJob`).

**Storage**: PostgreSQL/MySQL/SQLite via ActiveRecord for the Database provider; an external Meilisearch instance (`MEILISEARCH_URL`, `MEILISEARCH_API_KEY` env vars) for the Meilisearch provider — no additional Spree-owned tables for search state.

**Testing**: RSpec (per-gem `spec/`) — expected coverage: `spree/core/spec/models/spree/search_provider/*_spec.rb`, `spree/api/spec/services/spree/api/v3/filters_aggregator_spec.rb`, `spree/api/spec/integration/` for the two endpoints. (Not independently re-verified file-by-file in this pass — see Migration Notes gap in spec.md.)

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`) consumed by a Spree host app; no dashboard/SPA involvement.

**Project Type**: Monorepo — Ruby gems only (`spree/core`, `spree/api`).

**Performance Goals**: Facet computation cached 15 minutes per `(store, currency, locale, category, query, filters)` key with a cheap staleness check, so repeated filter-panel renders on an unchanged catalog avoid recomputation. No numeric SLA was found in code or `docs/plans/`.

**Constraints**: System-level scoping (store/channel/status/locale/currency/availability window) must remain non-overridable by user filter params in every provider implementation (security/multi-tenancy boundary). Meilisearch provider must degrade to an empty result (not a 5xx) on API errors.

**Scale/Scope**: Two provider implementations, one shared aggregator service, one indexing concern, two Active Jobs, one rake task, two API controllers/concerns. No scale numbers stated in source.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (provider classes, indexing concern, jobs, rake task) and `spree/api` (controllers, `FiltersAggregator`). The one cross-boundary reference — `SearchProvider::Database#build_facets` calling `Spree::Api::V3::FiltersAggregator` — is guarded by `defined?(Spree::Api::V3::FiltersAggregator)`, so `spree/core` does not hard-depend on `spree/api` being loaded. This is the documented extension seam, not a boundary violation. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: N/A — no `packages/dashboard` work found for this feature; it is Store-API-only (customer-facing search/filter), not surfaced in the admin SPA.
- **III. Read/Write Field Symmetry**: N/A — both endpoints are read-only (`index` actions only); no `permitted_params`/serializer write path exists for search/filters.
- **IV. Test-Backed**: RSpec is the applicable framework (backend-only feature). Existing coverage was not exhaustively re-verified in this migration pass (see spec.md Migration Notes) — flagged as a gap, not a violation, since this plan documents existing code rather than introducing new code.
- **V. Translations and Prefixed IDs**: Applies to prefixed IDs only (no new user-visible strings, since there's no frontend surface). Confirmed: `SearchProviderSupport#decode_prefixed_id_predicates` decodes prefixed IDs on read; `FiltersAggregator#encode_prefixed_id` and `OptionType/Taxon#prefixed_id` encode them on the way out. **Pass.**
- **VI. `docs/plans/` for Architectural Changes**: Already governed by `docs/plans/5.4-search-provider.md` (provider abstraction, shipped) and `docs/plans/5.4-disjunctive-option-faceting.md` (disjunctive facet counting, shipped). This spec-kit artifact documents that existing plan rather than superseding it. **Pass** (plan already exists, no new entry required).

No violations — Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/013-search-and-filtering/
├── plan.md              # This file
├── spec.md              # Feature specification (migrated)
└── tasks.md             # Task checklist (migrated, all marked complete)
```

### Source Code (repository root)

```text
# spree/core — provider interface, indexing, background jobs
spree/core/
├── app/models/spree/search_provider/base.rb              # Spree::SearchProvider::Base — abstract contract
├── app/models/spree/search_provider/database.rb          # Default provider — Ransack/SQL, no external dep
├── app/models/spree/search_provider/meilisearch.rb        # Optional provider — meilisearch-ruby client
├── app/models/spree/search_provider/search_result.rb      # SearchResult value struct
├── app/models/spree/search_provider/filters_result.rb     # FiltersResult value struct
├── app/models/concerns/spree/search_indexable.rb          # Mixin: after_commit index/remove hooks
├── app/jobs/spree/search_provider/index_job.rb            # Async indexing job
├── app/jobs/spree/search_provider/remove_job.rb           # Async removal job
├── lib/spree/core.rb                                      # Spree.search_provider config accessor (default: Database)
└── lib/tasks/search.rake                                  # rake spree:search:reindex

# spree/api — Store API endpoints + facet aggregation
spree/api/
├── app/controllers/spree/api/v3/store/products_controller.rb            # #collection override → search_provider.search_and_filter
├── app/controllers/spree/api/v3/store/products/filters_controller.rb    # #index → search_provider.filters, 15-min cache
├── app/controllers/concerns/spree/api/v3/store/search_provider_support.rb  # search_query/search_filters/prefixed-ID decoding
└── app/services/spree/api/v3/filters_aggregator.rb        # Database-provider facet computation (SQL COUNT queries)
```

**Structure Decision**: Backend-only, split across two gems: `spree/core` owns the provider abstraction/config/indexing lifecycle (framework-agnostic, reusable outside the API layer — e.g. by future GraphQL or admin surfaces), `spree/api` owns the two Store API controllers and the Database provider's facet-aggregation service. No `packages/*` changes — this is a pure backend extension point with no dashboard consumer found.

## Complexity Tracking

*No violations — table omitted.*
