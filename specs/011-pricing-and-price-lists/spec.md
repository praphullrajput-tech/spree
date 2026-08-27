# Feature Specification: Pricing & Price Lists

**Feature Branch**: `011-pricing-and-price-lists`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — no original user description. Source: `spree/core/app/models/spree/price.rb`, `price_list.rb`, `price_rule.rb`, `spree/core/app/models/spree/price_rules/{channel,customer_group,market,user,volume,zone}_rule.rb`, `spree/core/lib/spree/core/pricing/{context,resolver}.rb`, `spree/core/app/services/spree/prices/bulk_upsert.rb`, `spree/api/app/controllers/spree/api/v3/admin/{price_lists,prices}_controller.rb`, `spree/api/app/serializers/spree/api/v3/{price_serializer.rb,price_history_serializer.rb,admin/{price,price_list,price_rule,price_history}_serializer.rb}`, `packages/dashboard/src/{hooks/use-price-lists.ts,hooks/use-prices.ts,schemas/price-list.ts,components/spree/bulk-price-editor/*,routes/_authenticated/$storeId/products/price-lists/**}`, `packages/dashboard-ui/src/spree/bulk-price-table.tsx`, `docs/plans/5.4-6.0-eu-legal-compliance.md` (PriceHistory / Omnibus).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merchant sets a base price and compare-at price for a variant (Priority: P1)

A store admin sets/edits a `Spree::Price` row for a variant in a given currency: `amount` (the sell price) and optional `compare_at_amount` (strikethrough/"was" price). Every variant×currency pair has at most one base price (`price_list_id: nil`), enforced by a partial unique index.

**Why this priority**: The base price is the price the storefront resolves to when no price list applies — without it nothing is purchasable.

**Independent Test**: `POST /api/v3/admin/prices` with `variant_id`, `currency`, `amount`; `GET` the resource back and confirm `display_amount`/`amount_in_cents` reflect it; `PATCH` a `compare_at_amount` equal to `amount` and confirm the model clears it (`remove_compare_at_amount_if_equals_amount`).

**Acceptance Scenarios**:

1. **Given** a variant with no price in EUR, **When** an admin creates a `Price` with `amount: "19.99"`, **Then** the row persists with `currency` defaulted/validated and `Price#discounted?` is false.
2. **Given** an existing price, **When** the admin sets `compare_at_amount` lower than or equal to `amount`, **Then** validation numeric bounds apply, and if `compare_at_amount == amount` the model nils it out on save (no false "on sale" state).
3. **Given** `Spree::Config[:track_price_history]` is enabled, **When** a base price's `amount` changes, **Then** a `Spree::PriceHistory` row is recorded (`after_save :record_price_history`), feeding EU Omnibus `prior_price` (lowest price in the last 30 days).

---

### User Story 2 - Merchant creates a price list with rules to segment pricing (Priority: P1)

A store admin creates a `Spree::PriceList` (name, optional schedule `starts_at`/`ends_at`, `match_policy: all|any`, ordered by `acts_as_list`), attaches products via `product_ids`, attaches typed `Spree::PriceRule` STI subclasses (`ChannelRule`, `CustomerGroupRule`, `MarketRule`, `UserRule` — labeled "Customer rule" — `VolumeRule`, `ZoneRule`) each with their own `preferences`, and sets per-variant `amount`/`compare_at_amount` overrides — all through one flat PATCH payload (`rules: [...]`, `prices: [...]`, `product_ids: [...]`).

**Why this priority**: Price lists are the mechanism for segmented/contextual pricing (B2B tiers, market-specific pricing, volume discounts) — the core value proposition beyond flat base pricing.

**Independent Test**: `PATCH /api/v3/admin/price_lists/:id` with `product_ids: [...]`, `rules: [{ type: 'volume_rule', preferences: { min_quantity: 10 } }]`, `prices: [{ variant_id, currency, amount }]` in one request; `GET` back and confirm rule + price rows exist and product membership matches.

**Acceptance Scenarios**:

1. **Given** an admin adds `product_ids` to a list, **When** the list saves, **Then** `add_products` materializes placeholder (`amount: nil`) `Price` rows for every eligible variant × store-supported currency not already present, and `remove_products` hard-deletes prices for products dropped from the set.
2. **Given** a list has a `VolumeRule` (min/max quantity) and a `CustomerGroupRule`, **When** `match_policy: 'all'`, **Then** `PriceList#rules_applicable?` requires every rule's `#applicable?(context)` to return true for the list to apply; with `'any'`, at least one.
3. **Given** `rules: [...]` includes rows with `id` (existing) and rows without (new), **When** the list saves, **Then** typed-association reconciliation (`assign_typed_association`) updates matched rows, inserts new ones, and destroys rows omitted from the payload.
4. **Given** `prices: [...]` rows with `id`, **When** the list saves, **Then** `after_update :process_bulk_prices_update` upserts only `amount`/`compare_at_amount` via `upsert_all`, rejecting any row whose `id` doesn't belong to this list's `prices` association.

---

### User Story 3 - Storefront resolves the correct price for a variant given context (Priority: P1)

Given a `Spree::Pricing::Context` (variant, currency, store, zone, market, channel, user, quantity, date), `Spree::Pricing::Resolver#resolve` returns the best-matching price: it evaluates applicable, currently-active price lists (by `position`) in order, and within each list looks for a non-zero price in the requested currency; if no list price matches, it falls back to the variant's base price (or an empty placeholder `Price`).

**Why this priority**: This is the runtime payoff of the whole feature — every cart/PDP price shown to a customer flows through this resolution.

**Independent Test**: Build a variant with a base price and a second price under an active `PriceList` scoped to a `MarketRule` matching the context's market; call `Resolver.new(context).resolve` with and without that market in context, and assert it returns the list price only when the market matches.

**Acceptance Scenarios**:

1. **Given** two active price lists both applicable to the context, **When** `resolve` runs, **Then** the first list (lowest `position`) with a non-zero price for the currency wins — later lists are not consulted.
2. **Given** no applicable price list has a matching price, **When** `resolve` runs, **Then** the variant's own base price (`price_list_id: nil`) for the currency is returned.
3. **Given** neither a list price nor a base price exists for the currency, **When** `resolve` runs, **Then** an unsaved placeholder `Price` (`amount: nil`) is returned rather than `nil` or an error.

---

### User Story 4 - Merchant bulk-edits prices via a spreadsheet-style grid (Priority: P2)

An admin opens the bulk price editor (product-level or price-list-level) and edits many variants' `amount`/`compare_at_amount` cells in a grid, then submits one batch. `POST /api/v3/admin/prices/bulk_upsert` writes all rows transactionally keyed on `(variant_id, currency, price_list_id)`, and `DELETE .../bulk_destroy` soft-deletes a set of price ids.

**Why this priority**: Editing prices one row at a time doesn't scale to catalogs with many variants/currencies/price lists; this is the primary UI merchants use day-to-day.

**Independent Test**: Submit `bulk_upsert` with a mix of new and existing `(variant_id, currency)` keys, some with blank `amount` (clear); assert new rows are inserted, existing rows updated, and rows with blank amounts are removed by the post-write sweep — all in one call reported back as `{ price_count: N }`.

**Acceptance Scenarios**:

1. **Given** a payload with rows for both base prices (`price_list_id` absent) and price-list overrides, **When** `bulk_upsert` runs, **Then** rows are routed to the correct partial unique index (base vs. override) in separate `upsert_all` batches within one transaction.
2. **Given** a row references a variant or price list outside the current store, **When** `bulk_upsert` validates, **Then** the request is rejected with `invalid_prices` and no rows are written.
3. **Given** duplicate `(variant_id, currency, price_list_id)` keys appear in one payload, **When** `bulk_upsert` dedupes, **Then** last-write-wins (Postgres rejects an `ON CONFLICT` upsert touching the same key twice in one statement).

---

### User Story 5 - Merchant schedules and activates a price list (Priority: P3)

A price list has a `status` state machine (`draft → active`, `draft → scheduled`, `→ inactive`) driven by `PATCH .../activate` and `.../deactivate`. Activating a list with a future `starts_at` transitions it to `scheduled` instead of `active`; `PriceList.for_context` only returns lists that are `active`/`scheduled` AND currently within their date range.

**Why this priority**: Time-boxed promotions (seasonal pricing, flash sales) need a lifecycle distinct from "rules match" — narrower in scope than core CRUD/resolution.

**Independent Test**: Create a list with `starts_at` in the future, call `activate`, assert `status == 'scheduled'`; advance time past `starts_at` and assert `PriceList.for_context(...)`/`currently_active?` now includes it.

**Acceptance Scenarios**:

1. **Given** a `draft` list with no `starts_at`, **When** `activate` is called, **Then** it transitions straight to `active`.
2. **Given** an `active` list, **When** `deactivate` is called, **Then** it transitions to `inactive` and is excluded from `PriceList.for_context`.

### Edge Cases

- What happens when a variant has a price row with `amount: nil` (a placeholder created by `add_products`)? The resolver's `non_zero`/`where.not(amount: nil)` scopes skip it, so resolution falls through to base price or an empty placeholder.
- How does the system handle two price lists with overlapping applicability and the same currency both having a price for a variant? Resolution is strictly positional (`by_position`/`acts_as_list scope: :store_id`) — the first applicable list with a matching price wins; there is no "best/lowest price" merge across lists.
- What happens on MySQL, where `NULL` values are treated as distinct in unique indexes (unlike PG/SQLite)? `BulkUpsert` and `PriceList#bulk_update_prices` special-case MySQL with a SELECT-then-update/insert path instead of relying on `ON DUPLICATE KEY UPDATE` for base (list-less) prices.
- How is a price's history preserved for EU Omnibus when the price is inside a price list (not the base price)? It isn't — `should_record_price_history?` only fires when `price_list_id.nil?`; price-list overrides never generate `PriceHistory` rows or feed `prior_price`.
- What happens when `add_products` is called with variants already having prices in some currencies but not others? Only the missing `(variant_id, currency)` placeholder rows are inserted (`existing.include?` guard), so already-priced currencies are untouched.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store one `Spree::Price` per `(variant_id, currency)` for base prices (`price_list_id IS NULL`) and per `(variant_id, currency, price_list_id)` for price-list overrides, enforced by partial unique indexes.
- **FR-002**: System MUST support `amount` (required for base prices unless `Spree::Config.allow_empty_price_amount`) and optional `compare_at_amount`, both bounded `[0, 99_999_999.99]`, with automatic clearing of `compare_at_amount` when it equals `amount`.
- **FR-003**: System MUST allow a `Spree::PriceList` to carry a `name`, optional `description`, optional `starts_at`/`ends_at` schedule (validated `starts_at < ends_at`), `match_policy` (`all`/`any`), ordered `position` (`acts_as_list scope: :store_id`), and a `status` state machine (`draft`/`active`/`scheduled`/`inactive`).
- **FR-004**: System MUST support typed `Spree::PriceRule` STI subclasses — `ChannelRule`, `CustomerGroupRule`, `MarketRule`, `UserRule`, `VolumeRule`, `ZoneRule` — each with its own preference schema, uniquely constrained one-per-type per price list.
- **FR-005**: System MUST reconcile a price list's nested `rules`, `product_ids`, and `prices` from one PATCH payload — updating/inserting/destroying rule rows, adding/removing product membership (materializing/removing placeholder prices), and upserting listed price overrides — without separate endpoints.
- **FR-006**: System MUST resolve the applicable price for a `(variant, currency, context)` via `Spree::Pricing::Resolver`: applicable price lists in position order, first non-zero currency match wins; else the base price; else an empty placeholder.
- **FR-007**: System MUST expose a bulk endpoint (`POST /prices/bulk_upsert`) that writes many price rows transactionally keyed on `(variant_id, currency, price_list_id)`, rejecting rows referencing another store's variant/price list, and a bulk soft-delete (`DELETE /prices/bulk_destroy`).
- **FR-008**: System MUST record a `Spree::PriceHistory` row whenever a base price's `amount` changes (if `Spree::Config[:track_price_history]`), and expose `Price#prior_price` (lowest recorded amount in the trailing 30 days) for EU Omnibus compliance.
- **FR-009**: System MUST expose price-rule type discovery (`GET /price_lists/price_rule_types`) returning `{ type, label, description, preference_schema }` for every registered subclass, driving a generic "Add rule" picker in the admin SPA.
- **FR-010**: The Admin API MUST require a `products`-scoped API key or CanCanCan-authorized JWT for all price/price-list endpoints — there is no separate `price_lists` scope.

### Key Entities

- **Spree::Price**: A sell price for one variant in one currency, optionally scoped to a price list (`price_list_id`). Carries `amount`, `compare_at_amount`, `currency`. `price_list_id: nil` = base price.
- **Spree::PriceList**: A named, schedulable, ordered container of price overrides + eligibility rules for a store. Has many `prices`, many `price_rules`, and (through prices/variants) many `products`.
- **Spree::PriceRule** (STI base): A typed eligibility condition attached to a price list (`ChannelRule`, `CustomerGroupRule`, `MarketRule`, `UserRule`, `VolumeRule`, `ZoneRule`). One per type per list.
- **Spree::Pricing::Context**: A value object (variant, currency, store, zone, market, channel, user, quantity, date, order) passed to rules/resolver to answer "is this list/rule applicable, and what price applies."
- **Spree::PriceHistory**: An immutable snapshot of a base price's `amount`/`compare_at_amount` at a point in time, used to compute EU Omnibus `prior_price`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Price`, `Spree::PriceList`, `Spree::PriceRule` + 6 STI subclasses, `Spree::PriceHistory`, `Spree::Pricing::Context`/`Resolver`, `Spree::Prices::BulkUpsert` service |
| `spree/api` (Store/Admin API v3) | Yes | Store `PriceSerializer`/`PriceHistorySerializer`; Admin `PriceListsController`/`PricesController`, `Admin::Price{,List,Rule,History}Serializer` |
| `packages/dashboard` (admin SPA) | Yes | `price-lists` routes (index/new/`$priceListId`), `use-price-lists`/`use-prices` hooks, `price-list.ts` schema, bulk price editor components |
| `packages/dashboard-ui` / `dashboard-core` | Yes | `bulk-price-table.tsx` + `data-grid/*` headless grid primitives |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated types (`Price`, `PriceList`, `PriceRule`) + `admin-sdk` `priceLists`/`prices` resource methods — regenerated, not hand-written |
| `docs/plans/` | Yes | Governed by `5.4-6.0-eu-legal-compliance.md` (PriceHistory/`prior_price`, Phase 1 shipped) — no dedicated price-list plan exists; price lists shipped without a `docs/plans/` entry |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints**: `GET/POST /api/v3/admin/price_lists`, `GET/PATCH/DELETE /api/v3/admin/price_lists/:id`, `PATCH /api/v3/admin/price_lists/:id/activate`, `PATCH /api/v3/admin/price_lists/:id/deactivate`, `GET /api/v3/admin/price_lists/price_rule_types`; `GET/POST /api/v3/admin/prices`, `GET/PATCH/DELETE /api/v3/admin/prices/:id`, `POST /api/v3/admin/prices/bulk_upsert`, `DELETE /api/v3/admin/prices/bulk_destroy`. No Store API price-list endpoints (admin-only) — the Store API only exposes resolved `Price`/`PriceHistory` via product/variant serializers.
- **Serializer fields (read)**: `Price` — `amount`, `amount_in_cents`, `compare_at_amount`, `compare_at_amount_in_cents`, `currency`, `display_amount`, `display_compare_at_amount`, `price_list_id`; Admin adds `variant_id`, `created_at`, `updated_at`. `PriceList` (admin-only) — `name`, `description`, `status`, `position`, `match_policy`, `starts_at`, `ends_at`, `deleted_at`, `currently_active`, `products_count`, `prices_count`, `product_ids`, expandable `price_rules`. `PriceRule` — `type`, `price_list_id`, `preferences`, `preference_schema`, `label`, `description`, plus conditional `markets`/`customer_groups`/`channels`/`customers` embeds. `PriceHistory` — `amount`, `amount_in_cents`, `currency`, `display_amount`, `recorded_at`. Controllers' `permitted_params` mirror these field names exactly (constitution Principle III): e.g. `PriceRuleSerializer#type`/`#preferences` ⇄ `permitted_params rules: [:id, :type, { preferences: {} }]`.
- **Auth**: Admin API only — secret key with `products` scope, or Admin JWT + CanCanCan (`authorize! :read/:update, @resource`). No publishable-key/Store API surface for price lists or price rules.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A merchant can create a price list, attach products, rules, and per-variant overrides, and activate it in a single admin session without a page reload between steps (one PATCH round-trip for the whole editor).
- **SC-002**: Price resolution for any variant/currency/context combination returns in O(active price lists for the store), never scanning inapplicable/inactive lists.
- **SC-003**: Bulk price edits across hundreds of variant/currency rows complete in one transactional API call, with zero partial-write states (all-or-nothing per `ActiveRecord::Base.transaction`).
- **SC-004**: EU Omnibus `prior_price` (30-day lowest) is available for every base-priced variant without an extra admin action, once `track_price_history` is enabled.

## Assumptions

- Price lists are a single-store, admin-only concept — there's no multi-store sharing (`Spree::SingleStoreResource`) and no storefront-facing price-list API; customers only ever see the resolved price.
- "Rules" apply at the price-list level (does this list apply to this context at all), not at the individual price-row level — granularity finer than "which list" is out of scope.
- `track_price_history`/Omnibus compliance is opt-in per store (`Spree::Config[:track_price_history]`) and only ever tracks base prices, never price-list overrides.
- The bulk price editor's client-side money normalization (locale-aware decimal parsing before submit) is assumed already covered by `docs/plans/5.5-client-side-money-normalization.md` (referenced in code comments; not independently verified in this migration pass).
- Currency support per price is bounded by the owning store's `supported_currencies_list` — `add_products` only materializes placeholders for those currencies.

## Migration Notes

- **No dedicated `docs/plans/` entry.** Price Lists (and the six `PriceRule` STI subclasses) appear to have shipped without their own `6.0-*.md`/`5.x-*.md` plan document — only the adjacent EU Omnibus plan (`5.4-6.0-eu-legal-compliance.md`) documents the `PriceHistory`/`prior_price` slice. Per constitution Principle VI this is a gap; a retroactive plan entry may be warranted if further pricing work continues.
- **Dead/unreachable controller action found**: `Admin::PriceListsController#prices` (the "spreadsheet data feed", `GET /price_lists/:id/prices`) is defined and has a `before_action :load_member_resource` wired for it, but no matching route exists in `spree/api/config/routes.rb` (only `member do patch :activate; patch :deactivate end` — no `get :prices`). The frontend (`use-prices.ts`, bulk price editor) instead reads/writes prices through the generic `/api/v3/admin/prices` resource (filtered via Ransack on `price_list_id`) and the price list's own nested `prices` PATCH payload. This action is either legacy/orphaned or a route registration was dropped; flagged for follow-up rather than silently resolved during this reverse-engineering pass.
- **No `whitelisted_ransackable_attributes`/`_associations` found on `Spree::PriceList` or `Spree::PriceRule`** beyond `PriceList`'s own `status`/`match_policy`/`starts_at`/`ends_at` — `Spree::Price` has a fuller allowlist (`variant`, `price_list` associations + `search` scope). Ransack filtering surface for price lists/rules from the API is narrower than for prices; not verified whether the admin SPA needs more.
- **`Spree::PriceRule#applicable?` for the base class raises `NotImplementedError`** — every shipped subclass overrides it, so this is a template-method pattern, not a currently-reachable error path; noted for completeness only.
