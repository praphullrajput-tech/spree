---
status: migrated
---

# Spec: Search Provider

**Feature**: Pluggable search provider interface for storefront product search, filtering, and faceting

---

## Overview

The Search Provider is a strategy-pattern abstraction over product search. Two built-in backends exist: `Database` (default, zero-config SQL/ILIKE) and `Meilisearch` (production-grade external engine). The provider handles search, filtering, facet aggregation, and index management. Security and visibility enforcement live in the AR scope layer — the provider never bypasses them.

---

## User Scenarios

### US1 — Customer searches products on storefront
Given a published Store API with products indexed,
When a customer submits `GET /api/v3/store/products?q[search]=cotton+shirt`,
Then results are ordered by relevance, respect the active provider's ranking, and exclude unavailable/draft products.

### US2 — Customer filters by price, category, or option
Given the storefront filter panel,
When a customer applies `q[price_gte]=20&q[price_lte]=50&q[in_category]=taxon_xxx`,
Then only matching products are returned, with updated facet counts reflecting the current selection.

### US3 — Customer fetches available filters for the current query
Given a storefront category page,
When the browser calls `GET /api/v3/store/products/filters?q[in_category]=taxon_xxx`,
Then the response includes all available option-type filters, price range, availability filters, sort options, and total count; the response is cached for 15 minutes.

### US4 — Merchant switches to Meilisearch
Given `Spree.search_provider = 'Spree::SearchProvider::Meilisearch'` in an initializer,
When the merchant runs `rake spree:search:reindex`,
Then all products across all stores are indexed in Meilisearch with one document per market × locale combination; subsequent storefront searches use Meilisearch.

### US5 — Admin uses the global command palette
Given a logged-in admin user,
When the admin presses Cmd+K and types a query,
Then results from products, orders, customers, and promotions are returned in parallel, each limited to 5 hits, with debouncing and 30-second stale-while-revalidate.

---

## Functional Requirements

### FR-001 — Provider interface contract
The provider must implement: `search_and_filter(scope:, query:, filters:, sort:, page:, limit:)` → `SearchResult`, `filters(scope:, query:, filters:)` → `FiltersResult`, `index(product, store)`, `remove(product, store)`, `remove_by_id(prefixed_id, store)`, `reindex(store)`, `index_batch(products, store)`, `ensure_index_settings!(store)`.

### FR-002 — Database provider
Default provider; no external dependencies. Text search via SQL ILIKE with `%` wildcards. Filters map to AR scopes. Facets computed via `FiltersAggregator` with disjunctive counting per option type. Sort options: `price`, `-price`, `best_selling`, `created_at`, `-created_at`. `indexing_required? = false`.

### FR-003 — Meilisearch provider
External engine provider. `indexing_required? = true` — after-commit hooks enqueue background jobs. Documents are composite: one per product × locale × currency (`prod_abc_en_USD`). Searchable attributes: `name`, `description`, `sku`, `option_values`, `category_names`, `tags`. Sortable attributes: `price`, `name`, `available_on`, `units_sold_count`, `created_at`. Disjunctive faceting via Meilisearch multi-search (one request per option type).

### FR-004 — SearchIndexable concern
Included in `Spree::Product`. After-commit hooks enqueue `IndexJob` on create/update; `RemoveJob` on destroy. Provides `add_to_search_index`, `remove_from_search_index`, `search_presentation(store)`.

### FR-005 — ProductPresenter
Converts a product to a flat, indexable document. Generates one document per store market × locale combination. Composite ID: `{prefixed_id}_{locale}_{currency}`. Includes translated fields, pricing per currency, category hierarchy, option values, tags, `in_stock`.

### FR-006 — Background indexing jobs
`IndexJob` and `RemoveJob` on queue `Spree.queues.search`. Polynomial backoff, 5 retry attempts. `ActiveJob::DeserializationError` discarded (product deleted).

### FR-007 — Store API integration
`Store::ProductsController` includes `SearchProviderSupport`. Overrides `collection` to delegate to `search_provider.search_and_filter`. Decodes prefixed IDs in Ransack filter params. Security-filtered AR scope passed to provider.

### FR-008 — Filters endpoint
`GET /api/v3/store/products/filters` — calls `search_provider.filters`. Cached 15 minutes; cache key includes store, currency, locale, category, query, product count, max updated_at.

### FR-009 — Configuration
`Spree.search_provider` accessor (default: `'Spree::SearchProvider::Database'`). Swappable at runtime or via initializer. Deprecated `Spree.searcher_class` removed in 5.5.

### FR-010 — Reindex rake task
`rake spree:search:reindex` iterates all stores and calls `provider.reindex(store)`.

### FR-011 — Admin global search (command palette)
`packages/dashboard-core/src/hooks/use-global-search.ts` debounces (200ms, min 2 chars), runs parallel queries per registered resource (limit 5 each), 30s stale / 60s GC. Search registry (`search-registry.ts`) is extensible — plugins can register new resource types. Default entries: products, orders, customers, promotions. Triggered via Cmd+K.

### FR-012 — Custom provider support
Any class inheriting `Spree::SearchProvider::Base` and implementing the full contract can be assigned to `Spree.search_provider`. Developer documentation available in `docs/developer/how-to/custom-search-provider.mdx`.

---

## Non-Functional Requirements

- **NFR-001** — Filters endpoint cached 15 minutes to avoid N+1 facet queries on every page load
- **NFR-002** — Provider never enforces visibility — always receives a pre-filtered AR scope
- **NFR-003** — `IndexJob` discards on `DeserializationError` to handle deleted records gracefully
- **NFR-004** — SSRF-safe HTTP not applicable (provider issues no outbound HTTP; that's the webhook system)
- **NFR-005** — Prefixed IDs decoded in filter params so clients can pass `taxon_abc` without stripping prefix

---

## Success Criteria

- [ ] `GET /api/v3/store/products?q[search]=<term>` returns relevant results via both Database and Meilisearch providers
- [ ] `GET /api/v3/store/products/filters` returns filter structure + sort options with 15-minute caching
- [ ] After-commit hooks on Product trigger index/remove background jobs when Meilisearch is active
- [ ] `rake spree:search:reindex` indexes all products across all stores
- [ ] `Spree.search_provider = 'Spree::SearchProvider::Database'` (default) works with no configuration
- [ ] Admin Cmd+K returns results from products, orders, customers, promotions

---

## Out of Scope

- Metafield-based faceting (6.0 pending — see `5.4-search-provider.md`)
- Autocomplete/typeahead endpoint
- Synonyms/stopwords management UI
- PgSearch integration (removed in 5.4)
- `add_search_scope` macro (removed in 5.4)
