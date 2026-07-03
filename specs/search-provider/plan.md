# Implementation Plan: Search Provider

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped in 5.4; 6.0 metafield faceting pending

---

## Summary

The Search Provider is a strategy pattern abstraction over product search. `Spree::SearchProvider::Base` defines the contract; `Database` (default, SQL/ILIKE + Ransack) and `Meilisearch` (external engine) are the two built-in implementations. The provider never enforces security — it always receives an AR scope that has already been filtered for visibility and authorization. Background indexing jobs (`IndexJob`, `RemoveJob`) are only active when the provider returns `indexing_required? = true`. The Store API delegates collection building to the provider; the admin SPA uses a separate search registry for global Cmd+K search.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Default provider** | `Spree::SearchProvider::Database` |
| **External provider** | `Spree::SearchProvider::Meilisearch` |
| **Configuration** | `Spree.search_provider` accessor |
| **Scope** | Fully shipped |

---

## Key Decisions

1. **Provider receives a pre-filtered AR scope, never raw data.** Security (visibility, store scoping, CanCanCan) is enforced at the controller level before the scope is handed to the provider. This means a custom provider cannot accidentally expose unpublished or cross-store products.

2. **Database provider is zero-config.** `indexing_required? = false` — no background jobs, no external services. SQL ILIKE with `%` wildcards is good enough for small catalogs and requires no setup. Merchants upgrade to Meilisearch when they need relevance ranking.

3. **Meilisearch documents are composite: one per product × market × locale.** A product in a store with 2 currencies and 3 locales generates 6 documents. Composite ID: `prod_abc_en_USD`. This allows per-currency/per-locale relevance ranking without runtime joins.

4. **`ProductPresenter` separates indexing from the model.** The presenter builds the flat document without touching the model directly. Registered in `Spree::Dependencies` for swappability. Uses `preload_associations_lazily` to avoid N+1 across batch indexing.

5. **`SearchProviderSupport` concern decodes prefixed IDs in filter params.** Ransack predicates like `taxon_id_in[]=taxon_abc` have their values decoded before being passed to the provider. This lets the Store API be ID-format-agnostic from the client's perspective.

6. **Filters endpoint cached 15 minutes.** Facet queries are expensive on large catalogs. The cache key captures all parameters that affect the result (store, currency, locale, category, query, product count, max `updated_at`). Cache is invalidated when any product changes.

7. **Admin global search uses a separate registry, not the search provider.** The command palette (`use-global-search.ts`, `search-registry.ts`) queries Admin API endpoints directly (`?q[search]=…&limit=5`) and is extensible via `searchRegistry.add()`. It is not a wrapper around the storefront search provider.

8. **`add_search_scope` macro removed in 5.4.** The old DSL for defining custom filter scopes was replaced by the provider interface. Custom filtering now lives in a custom provider implementation.

---

## Constitution Check

- [x] **No prefix IDs on provider** — SearchProvider is a service, not a model; no `has_prefix_id`
- [x] **Serializer Hierarchy**: Store API `ProductSerializer` used for search results; no dedicated search serializer
- [x] **Security**: Provider always receives pre-filtered scope; CanCanCan enforced before provider call
- [x] **Namespace**: `Spree::SearchProvider::*`
- [x] **Plan Conflicts**: `5.4-search-provider.md` — fully shipped; `5.4-disjunctive-option-faceting.md` — `FiltersAggregator` + Meilisearch multi-search shipped

---

## Project Structure

```text
# Backend — provider interface + implementations (✅ shipped)
spree/core/app/models/spree/search_provider/base.rb              ← abstract contract
spree/core/app/models/spree/search_provider/database.rb          ← SQL/ILIKE + Ransack
spree/core/app/models/spree/search_provider/meilisearch.rb       ← external engine
spree/core/app/models/spree/search_provider/search_result.rb     ← Struct: products, total_count, pagy
spree/core/app/models/spree/search_provider/filters_result.rb    ← Struct: filters, sort_options, default_sort, total_count

# Backend — concerns (✅ shipped)
spree/core/app/models/concerns/spree/search_indexable.rb         ← after-commit hooks on Product
spree/core/app/models/concerns/spree/searchable.rb               ← ILIKE helpers

# Backend — presenter (✅ shipped)
spree/core/app/presenters/spree/search_provider/product_presenter.rb  ← multi-locale doc generation

# Backend — jobs (✅ shipped)
spree/core/app/jobs/spree/search_provider/index_job.rb
spree/core/app/jobs/spree/search_provider/remove_job.rb

# Backend — API (✅ shipped)
spree/api/app/controllers/spree/api/v3/store/products_controller.rb                         ← SearchProviderSupport
spree/api/app/controllers/spree/api/v3/store/products/filters_controller.rb                 ← 15-min cache
spree/api/app/controllers/concerns/spree/api/v3/store/search_provider_support.rb

# Backend — rake (✅ shipped)
spree/core/lib/tasks/search.rake                                  ← spree:search:reindex

# Frontend (✅ shipped)
packages/dashboard-core/src/hooks/use-global-search.ts           ← debounced parallel query
packages/dashboard-core/src/lib/search-registry.ts              ← extensible registry
```

---

## Phase 1: Core + API + SPA (✅ Complete)

- Provider interface + Database + Meilisearch backends
- `SearchIndexable` concern with after-commit hooks
- `ProductPresenter` with multi-locale/currency document generation
- Background jobs (`IndexJob`, `RemoveJob`)
- Store API `/products` + `/products/filters` endpoints with search/filter/sort
- 15-minute filters cache
- Admin global search (command palette, search registry)
- `rake spree:search:reindex`
- Developer documentation + custom provider how-to

---

## Phase 2: 6.0 — Metafield Faceting (PENDING)

Per `5.4-search-provider.md` (6.0 section):

- `MetafieldDefinition` faceting — allow merchants to designate metafields as facets
- Meilisearch provider: include metafield values in indexed documents
- Filters endpoint: return metafield facets alongside option-type facets

---

## Complexity Tracking

| Component | Why Needed | Simpler Alternative Rejected |
|-----------|------------|------------------------------|
| Composite document IDs (`prod_abc_en_USD`) | One product needs per-currency pricing in index; Meilisearch has no runtime join support | Separate index per currency — operational overhead for merchants with many currencies |
| `FiltersAggregator` for disjunctive counts | Selecting "Red" in a color filter should still show counts for "Blue" and "Green" — not zero them out | Simple post-filter facets zero out sibling options, breaking multi-select UX |
