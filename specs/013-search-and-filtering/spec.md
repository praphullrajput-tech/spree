# Feature Specification: Search & Filtering

**Feature Branch**: `013-search-and-filtering`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration). No original feature request text exists — this spec documents the `Spree::SearchProvider` pluggable interface and its Store API surface as built.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Storefront visitor searches and filters a product listing (Priority: P1)

A storefront visitor browses a category or the full catalog, types a text query, and narrows results using facets (price range, availability, option values like color/size, sub-categories).

**Why this priority**: This is the core commerce interaction — without it, customers cannot find products in any catalog larger than a handful of items.

**Independent Test**: Call `GET /api/v3/store/products?q[search]=shirt&q[price_gte]=10` against a store with products and confirm only matching, in-stock-scoped, currency/locale-scoped, visible products are returned with correct pagination metadata.

**Acceptance Scenarios**:

1. **Given** a store with products in multiple categories, **When** a visitor requests the product listing with `q[search]=<term>`, **Then** only products whose name/description/sku/option-values/tags match the term are returned.
2. **Given** a category with children, **When** a visitor requests `GET /api/v3/store/products/filters?category_id=<slug>`, **Then** the response includes price range, availability counts, per-option-type facets, and child-category facets scoped to that category.
3. **Given** a visitor has selected one option value (e.g. "Blue"), **When** the filters endpoint is re-queried with that selection applied, **Then** facet counts for *other* option types re-narrow to the filtered set, while counts for option values within the *same* option type remain disjunctive (still show what would be available if a different value in that same type were picked instead).
4. **Given** a store configured with the default provider, **When** no external search service is available, **Then** search and filtering still work end-to-end via plain SQL/Ransack (no hard dependency on an external service).

---

### User Story 2 - Store operator sorts and paginates results (Priority: P2)

A storefront visitor or headless client sorts the listing (price, name, availability date, best-selling) and pages through results.

**Why this priority**: Sorting/pagination is expected baseline behavior for any listing endpoint; it is independently testable and valuable without facets.

**Independent Test**: Request `GET /api/v3/store/products?sort=-price&page=2` and confirm descending price order and correct offset.

**Acceptance Scenarios**:

1. **Given** a product listing, **When** `sort=price` or `sort=-price` is passed, **Then** results are ordered ascending/descending by current-currency price.
2. **Given** more results than fit one page, **When** `page`/`limit` params are passed, **Then** the response's pagination metadata (`Pagy`) reflects total count and current page correctly regardless of which provider is active.

---

### User Story 3 - Platform operator swaps the search backend (Priority: P3)

An operator running at scale replaces the built-in SQL search with Meilisearch (typo tolerance, relevance ranking, faster faceting) by setting `Spree.search_provider = 'Spree::SearchProvider::Meilisearch'` and running a reindex, without changing any controller code.

**Why this priority**: This is the extensibility contract the whole feature is built around — it's what justifies the `SearchProvider::Base` abstraction existing at all, but is not required for a store to function on day one (Database provider is the default).

**Independent Test**: Set the provider config, run `rake spree:search:reindex`, then confirm the same Store API request (`GET /api/v3/store/products?q[search]=...`) returns equivalent results shaped by `SearchResult`/`FiltersResult`, sourced from Meilisearch instead of SQL.

**Acceptance Scenarios**:

1. **Given** `Spree.search_provider` is set to a custom class name, **When** any controller calls `search_provider.search_and_filter` or `.filters`, **Then** it invokes the configured class with no controller changes needed.
2. **Given** a provider declares `indexing_required? == true`, **When** a product is created/updated/destroyed, **Then** `Spree::SearchIndexable` enqueues `Spree::SearchProvider::IndexJob`/`RemoveJob` per store the product belongs to; providers that don't require indexing (e.g. Database) no-op silently.
3. **Given** an index is queried before its filterable-attribute settings have been applied (e.g. right after a new attribute like `preorder` is added), **When** the Meilisearch provider hits an `invalid_search_filter` API error, **Then** it self-heals by calling `ensure_index_settings!` once and retrying, rather than surfacing a hard failure.

### Edge Cases

- What happens when the search provider (e.g. Meilisearch) is unreachable or errors? → `Meilisearch#execute_search` rescues `::Meilisearch::ApiError`, logs a warning, reports to `Rails.error`, and returns `nil`, which callers translate into an empty `SearchResult`/`FiltersResult` (zero hits) rather than a 500.
- How does the system handle prefixed IDs (`prod_...`, `optval_...`, `cat_...`) passed as Ransack predicate filters (e.g. `q[variants_option_values_id_in]`)? → `SearchProviderSupport#decode_prefixed_id_predicates` decodes any key matching the `*_id(s)_<predicate>` pattern before handing filters to Ransack/the provider.
- How are option-value filters combined? → OR within one option type (selecting "Blue" or "Red" widens results), AND across option types (selecting a color AND a size narrows results) — implemented identically in both `FiltersAggregator#disjunctive_scope_for`/`grouped_selected_options` (Database) and `Meilisearch#build_grouped_option_conditions`/`group_option_values_by_type`.
- What happens to facet counts for the option type currently being filtered on? → They remain disjunctive per Acceptance Scenario 3 above — this is deliberate so users can multi-select within a facet.
- How does the system exclude products with a future `available_on` or an already-passed `discontinue_on`? Both providers mirror `Product.available(...)`; Meilisearch does this via string/int filter conditions instead of SQL predicates.
- What about multi-store / multi-channel / multi-locale / multi-currency scoping? Both providers filter system-side (never user-overridable) on store, channel (if `Spree::Current.channel` present), locale, and currency before any user filter is applied.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a `Spree::SearchProvider::Base` abstract contract with two primary operations — `search_and_filter(scope:, query:, filters:, sort:, page:, limit:)` returning a `SearchResult` (products/total_count/pagy), and `filters(scope:, query:, filters:)` returning a `FiltersResult` (filters/sort_options/default_sort/total_count) — kept separate so facet computation is not paid on every listing request.
- **FR-002**: The system MUST ship at least one built-in provider (`Spree::SearchProvider::Database`) requiring no external service, using Ransack + AR scopes (`search`, `ascend_by_price`, `descend_by_price`, `by_best_selling`, `with_option_value_ids`).
- **FR-003**: The system MUST support swapping providers via a single configuration point (`Spree.search_provider`, default `'Spree::SearchProvider::Database'`), with no controller-level code changes required.
- **FR-004**: Providers that require background indexing MUST declare `self.indexing_required? == true`; `Spree::SearchIndexable` (mixed into indexable models) MUST enqueue `Spree::SearchProvider::IndexJob`/`RemoveJob` per store only when the active provider requires it.
- **FR-005**: The system MUST allow full-text query (`q[search]`) combined with structured filters (price range, in/out of stock, category, categories, option value IDs) and sorting, applied together in one call.
- **FR-006**: The system MUST support disjunctive facet counting for option-value facets: counts for values within a selected option type reflect what's available if a *different* value of that same type were chosen, while other option types' counts reflect the current full filter set.
- **FR-007**: The system MUST decode Stripe-style prefixed IDs (`prod_`, `optval_`, `cat_`, etc.) appearing in Ransack-predicate-style filter keys (`*_id_in`, `_id_eq`, ...) before filters reach the provider.
- **FR-008**: The `Products::FiltersController#index` endpoint MUST cache its response (`Rails.cache`, 15 minutes) keyed on store/currency/locale/category/query/filters plus a cheap staleness signal (`MAX(updated_at)` + `COUNT(DISTINCT id)` over the scoped product set) so the cache invalidates when the underlying catalog changes.
- **FR-009**: All system-level scoping (store, channel, active status, locale, currency, availability window) MUST be applied unconditionally by the provider and MUST NOT be overridable by user-supplied filter params.
- **FR-010**: The Meilisearch provider MUST self-heal on `invalid_search_filter` errors by refreshing index settings once and retrying the search, to tolerate schema drift between a deploy and the next reindex.
- **FR-011**: Every provider implementation MUST expose the same sort vocabulary (`price`, `-price`, `name`, `-name`, `available_on`, `-available_on`, `best_selling`) and the same facet response shape (`price_range`, `availability`, `option`, `category` facet objects) so the Store API contract is provider-agnostic.
- **FR-012 (extension contract)**: Any custom `Spree::SearchProvider` subclass (of `Base` or of `Meilisearch`/`Database`) MUST implement/override `search_and_filter`, `filters`, and MAY override `index`/`remove`/`remove_by_id`/`index_batch`/`ensure_index_settings!`/`reindex` (all no-ops by default) plus, for Meilisearch subclasses, `build_filter_condition`/`sort_mapping`/`build_facet_response` (each documented as "call super for built-in, override to extend").

### Key Entities

- **SearchProvider (Base/Database/Meilisearch)**: Strategy object, one instance per `(provider class, store)` pair; not persisted. Holds no state beyond `store`.
- **SearchResult**: Value struct — `products` (AR relation or Array), `total_count`, `pagy` (a `Pagy::Offset` or `Pagy::MeilisearchPaginator` result) — returned by `search_and_filter`.
- **FiltersResult**: Value struct — `filters` (array of facet hashes), `sort_options`, `default_sort`, `total_count` — returned by `filters`.
- **Facet**: Not a persisted model — a hash shape with `id`, `type` (`price_range` | `availability` | `option` | `category`), and type-specific fields (`min`/`max`/`currency`, `options: [{id, count}]`, etc.), computed on the fly from `Spree::OptionType`/`Spree::OptionValue`/`Spree::Taxon`/`Spree::Price`.
- **FiltersAggregator**: Service object (not a provider) used internally by the Database provider to compute facets via grouped SQL COUNT queries; not part of the public provider contract.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::SearchProvider::{Base,Database,Meilisearch,SearchResult,FiltersResult}`, `Spree::SearchIndexable` concern, `Spree::SearchProvider::{IndexJob,RemoveJob}`, `Spree.search_provider` config accessor, `lib/tasks/search.rake` |
| `spree/api` (Store/Admin API v3) | Yes | `Spree::Api::V3::Store::Products::FiltersController`, `SearchProviderSupport` concern, `Spree::Api::V3::FiltersAggregator`, `ProductsController#collection` override |
| `packages/dashboard` (admin SPA) | No | Search/filtering is a storefront (Store API) concern; no admin SPA routes found for this feature |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Yes (generated) | `packages/sdk` Store API client types for product list/filters responses would be regenerated if serializer output changed; no dedicated resource methods found beyond standard `client.products.list()`/filters call — not independently verified in this pass |
| `docs/plans/` | Yes (already exists) | `docs/plans/5.4-search-provider.md` (provider abstraction, PgSearch/`add_search_scope` removal, 6.0 metafield faceting pending) and `docs/plans/5.4-disjunctive-option-faceting.md` (per-option-type disjunctive counting) already govern this area — this spec documents what they describe as shipped |

### API Contract *(include if feature touches spree/api)*

- **Endpoints**: `GET /api/v3/store/products` (search/filter/sort via `collection` override in `ProductsController`), `GET /api/v3/store/products/filters` (facet computation, cached 15 min)
- **Request params (Ransack-style, flat)**: `q[search]`, `q[price_gte]`, `q[price_lte]`, `q[in_stock]`, `q[out_of_stock]`, `q[in_category]`, `q[in_categories]`, `q[with_option_value_ids]`, `sort`, `page`, `limit`, `category_id` (filters endpoint only)
- **Response shape**: product listing = standard paginated Alba-serialized product collection; filters endpoint = `{ filters: [...], sort_options: [...], default_sort: "...", total_count: N }`
- **Auth**: Store API publishable key (guest-accessible, read-only) — both endpoints inherit `Store::BaseController`/`ResourceController`'s default publishable-key auth; no write actions involved

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Swapping `Spree.search_provider` from Database to Meilisearch (or a custom subclass) requires zero changes to `ProductsController`, `FiltersController`, or any Store API route/serializer.
- **SC-002**: Facet computation on the filters endpoint completes within the 15-minute cache window without re-running expensive aggregation on every request for an unchanged catalog.
- **SC-003**: Selecting multiple values within the same option-type facet never causes that facet's own counts to disappear (disjunctive-within-type behavior holds under both providers).
- **SC-004**: A request with an unreachable/erroring external search backend degrades to an empty result set (never a 5xx) and is observable via `Rails.error` reporting.

## Assumptions

- Single-tenant-per-request scoping (one `current_store`, one `Spree::Current.currency`/`locale`/`channel`) is assumed throughout; multi-store aggregation across search is out of scope for this spec.
- The Database provider's facet computation delegates to `Spree::Api::V3::FiltersAggregator`, which lives in `spree/api` even though it's invoked from `spree/core`'s `SearchProvider::Database` (guarded by `defined?(...)` — the core gem does not hard-depend on the api gem being loaded).
- Metafield-based faceting (mentioned as "6.0 pending" in `docs/plans/5.4-search-provider.md`) is explicitly out of scope for what's documented here as built.
- No admin-facing UI for configuring/monitoring the search provider was found in `packages/dashboard`; provider selection is an environment/initializer-level concern (`Spree.search_provider = '...'`), not an admin-editable setting.

## Migration Notes

This spec was reverse-engineered from an already-implemented feature (brownfield migration) — there is no prior spec-kit history to reconcile.

- **This is an extension point, not a fixed feature.** `Spree::SearchProvider::Base` is a pluggable strategy interface (see `docs/plans/5.4-search-provider.md`). The functional requirements above intentionally describe the **contract** (method signatures, no-op defaults, override points) rather than only the two shipped implementations (`Database`, `Meilisearch`), so that a third-party provider can be validated against this spec without code changes here.
- **Gap — no automated coverage located for the disjunctive-facet edge cases** in the time available for this pass; `docs/plans/5.4-disjunctive-option-faceting.md` describes the design in more depth than could be independently re-verified against spec files. Recommend a follow-up `/speckit-clarify` pass cross-referencing `spree/api/spec/` and `spree/core/spec/` for `FiltersAggregator`/`SearchProvider` specs before treating FR-006 as fully verified.
- **Gap — no `packages/sdk` search-specific resource method or Zod schema was independently located**; the Module Impact table marks this "Yes (generated)" on inference (any serializer change regenerates SDK types) but this was not directly confirmed by reading `packages/sdk/src`.
- **Gap — Admin API surface for search configuration.** No `spree/api` Admin controller for reading/writing `Spree.search_provider` or triggering `rake spree:search:reindex` was found; this remains an ops-only (rake task / env var) capability, not exposed over HTTP.
- 6.0-targeted metafield faceting (per `docs/plans/5.4-search-provider.md`) is pending and intentionally excluded from the Functional Requirements above.
