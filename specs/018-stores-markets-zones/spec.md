# Feature Specification: Stores, Markets & Zones

**Feature Branch**: `018-stores-markets-zones`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — no original feature request text. Scope: `Spree::Store` (config/preferences), `Spree::Market` (per-store currency/locale/country grouping), `Spree::Zone`/`Spree::ZoneMember` (geographic groupings historically used for tax/shipping), `Spree::AllowedOrigin` (CORS/storefront origin allowlist), and the `Spree::SingleStoreResource` concern that most of these mix in.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merchant segments customers into Markets by currency/locale/country (Priority: P1)

A merchant operating a single Spree store wants to sell into multiple regions, each with its own currency, default locale, and set of countries — e.g., a "North America" market priced in USD and a "Eurozone" market priced in EUR. `Spree::Market` (`spree/core/app/models/spree/market.rb`) is the unit that carries this: `currency`, `default_locale`, `supported_locales`, `country_isos`, and a `default` flag (exactly one default market per store, enforced by `ensure_single_default`). `Spree::Store` delegates `default_currency`, `default_locale`, `default_country`, `supported_currencies_list`, and `supported_locales_list` to markets once any exist (`Spree::Stores::Markets#has_markets?`), falling back to legacy store-level columns otherwise.

**Why this priority**: Markets are the mechanism that determines the currency/locale a storefront visitor sees and the tax zone resolution starting point (`Market#tax_zone`); every other capability in this feature (Zone-based tax/shipping, currency listing, locale listing, order routing) is downstream of a store having (or not having) markets.

**Independent Test**: Create a store, create two markets with disjoint countries via `POST /api/v3/admin/markets`, verify `GET /api/v3/store/markets` lists both and `GET /api/v3/store/markets/resolve?country=DE` resolves to the market containing Germany.

**Acceptance Scenarios**:

1. **Given** a store with no markets, **When** the store is created with a `default_country_iso`, **Then** `Spree::Stores::Markets#ensure_default_market` (an `after_create` callback) creates one default market seeded from that country's currency/locale.
2. **Given** a store with two markets, **When** an admin marks a non-default market as `default: true` and saves, **Then** `Market#ensure_single_default` unsets `default` on every other market for that store.
3. **Given** a market that is the store's only market, **When** an admin attempts to destroy it, **Then** `Market#ensure_can_be_deleted` blocks the destroy (`errors.add(:base, :cannot_destroy_last_market)`) because `Spree::Current.currency` would have no fallback.
4. **Given** a market that is currently flagged `default`, **When** an admin attempts to destroy it (even if other markets exist), **Then** the destroy is blocked (`:cannot_destroy_default_market`) — a different market must be promoted to default first.

---

### User Story 2 - Storefront queries available currencies/locales/markets (Priority: P2)

A storefront client (Next.js or any Store API consumer) needs to render a currency switcher, locale switcher, or market picker without hardcoding values. `Spree::Api::V3::Store::CurrenciesController`, `LocalesController`, and `MarketsController` (all under `spree/api/app/controllers/spree/api/v3/store/`) expose read-only, publishable-key-authenticated endpoints backed by `current_store.supported_currencies_list` / `supported_locales` / `markets`.

**Why this priority**: Depends on Markets existing (US1) but is the actual customer-facing surface; without it, Markets are admin-only configuration with no storefront effect.

**Independent Test**: With a store that has 2 markets (USD/EUR), call `GET /api/v3/store/currencies` and `GET /api/v3/store/locales` with a publishable key and confirm both markets' currencies/locales appear, deduplicated.

**Acceptance Scenarios**:

1. **Given** a store with markets in USD and EUR, **When** `GET /api/v3/store/currencies` is called, **Then** the response lists both currencies, with the store's `default_currency` sorted first.
2. **Given** a store with no markets (legacy store), **When** the same endpoint is called, **Then** `Stores::Markets#legacy_supported_currencies_list` falls back to the store's `default_currency` + `supported_currencies` column.
3. **Given** `GET /api/v3/store/markets/resolve?country=XX` for a country not covered by any market, **Then** the controller raises `ActiveRecord::RecordNotFound` (404).

---

### User Story 3 - Store restricts which browser origins may call its Store API (Priority: P2)

A merchant running a headless storefront on a custom domain (and possibly a staging domain) needs to register which origins are allowed to make CORS/guest-cart requests against the Store API. `Spree::AllowedOrigin` (`spree/core/app/models/spree/allowed_origin.rb`) stores one `origin` (scheme+host+port) per row, validated as a bare origin (no path/query/fragment) via `origin_must_be_valid_http_url`, with loopback hosts (`localhost`, `127.0.0.1`, `::1`, `0.0.0.0`) exempted from strict port matching. `Store#allowed_origin?` and `Store#storefront_url` consume this.

**Why this priority**: Security-adjacent (CORS allowlisting) but independent of Markets/Zones — it's a per-store, per-origin admin CRUD surface with no cross-entity dependency.

**Independent Test**: `POST /api/v3/admin/allowed_origins` with `origin: "https://shop.example.com"`, then confirm `store.allowed_origin?("https://shop.example.com/some/path")` returns true (path is ignored in matching) and `store.allowed_origin?("https://evil.com")` returns false.

**Acceptance Scenarios**:

1. **Given** an allowed origin `http://localhost`, **When** checked against `http://localhost:4000`, **Then** it matches (loopback hosts skip port comparison).
2. **Given** an allowed origin `https://shop.com`, **When** checked against `https://shop.com:443`, **Then** it matches (default HTTPS port is implicit).
3. **Given** a submitted origin with a path/query/fragment (e.g., `https://shop.com/checkout`), **When** validated, **Then** `AllowedOrigin` is invalid (`:must_be_origin_only`).

---

### User Story 4 - Geographic Zones back tax and shipping-method eligibility (Priority: P3, legacy)

`Spree::Zone` (`spree/core/app/models/spree/zone.rb`) groups `Spree::Country` or `Spree::State` records via polymorphic `Spree::ZoneMember` rows, and is consumed today by `TaxRate.match(zone)` (tax) and `ShippingMethodZone` (shipping-method eligibility). `Zone.match(address_or_country)` resolves the most specific zone (state-kind zones outrank country-kind) for a given address.

**Why this priority**: Lowest priority because this model is explicitly slated for removal — see Migration Notes. It's included here because it's still load-bearing in the current codebase (`Store#countries_with_shipping_coverage`, `Market#tax_zone`, tax rate matching) and any spec-kit work touching tax/shipping in the interim must account for it.

**Independent Test**: Create a Zone with two Country members, attach a TaxRate to it, and confirm `TaxRate.match` returns the rate for an order whose ship address is in one of those countries.

**Acceptance Scenarios**:

1. **Given** a Zone with `Spree::Country` members, **When** `Zone#kind` is read, **Then** it returns `"country"` (inferred from the most recently added member's type when the `kind` column is blank).
2. **Given** overlapping state- and country-kind zones matching the same address, **When** `Zone.match(address)` is called, **Then** the state-kind zone wins (state has higher priority than country).
3. **Given** a Zone member's zoneable record is deleted, **When** the Zone is next saved, **Then** `remove_defunct_members` prunes members whose `zoneable_type` no longer matches the zone's inferred `kind`.

---

### Edge Cases

- What happens when a store has zero markets and zero legacy `default_currency`/`default_locale` column values? `default_currency`/`default_locale` return `nil`, and downstream currency/locale formatting must handle that (out of scope for this spec — no guard was found in the reviewed files).
- How does the system handle two `AllowedOrigin` rows for the same store with the same origin string? Blocked by a uniqueness validation scoped to `store_id` (`validates :origin, uniqueness: { scope: [:store_id, *spree_base_uniqueness_scope] }`).
- How does `Store#storefront_url` behave with zero `AllowedOrigin` rows? Falls back to `formatted_url` (derived from the store's `url` column).
- What happens when a `Market#country_isos=` is set with only unknown ISO codes? All are silently dropped, then `validates :countries, presence: true` fails the save.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow exactly one `Spree::Market` per store to be flagged `default: true`, auto-demoting any prior default on save (`Market#ensure_single_default`).
- **FR-002**: System MUST prevent deletion of a store's only market or its current default market (`Market#can_be_deleted?` / `#ensure_can_be_deleted`).
- **FR-003**: System MUST derive a store's effective `default_currency`, `default_locale`, `default_country`, `supported_currencies_list`, and `supported_locales_list` from its Markets when any exist, falling back to legacy `spree_stores` columns otherwise (`Spree::Stores::Markets`).
- **FR-004**: System MUST auto-create a default market on store creation when a `default_country_iso` is supplied (`Stores::Markets#ensure_default_market`, an `after_create` callback), seeded with that country's ISO currency and official language.
- **FR-005**: System MUST expose Store API read-only endpoints for markets (`GET /api/v3/store/markets`, `GET /api/v3/store/markets/:id`, `GET /api/v3/store/markets/resolve?country=`), currencies (`GET /api/v3/store/currencies`), and locales (`GET /api/v3/store/locales`), all publishable-key-authenticated and HTTP-cached (`Spree::Api::V3::HttpCaching`).
- **FR-006**: System MUST expose full Admin API CRUD for markets (`Spree::Api::V3::Admin::MarketsController`, inherited actions from `ResourceController`) accepting `country_isos` and `supported_locales` as arrays, translated to associations/columns via model setters.
- **FR-007**: System MUST expose full Admin API CRUD for allowed origins (`Spree::Api::V3::Admin::AllowedOriginsController`) permitting only `:origin` on write, matching the serializer's read surface (`origin`, `created_at`, `updated_at`).
- **FR-008**: System MUST validate that an `AllowedOrigin#origin` is a bare HTTP(S) origin — no path (beyond `/`), query, or fragment (`AllowedOrigin#origin_must_be_valid_http_url`).
- **FR-009**: System MUST match a candidate URL against a stored `AllowedOrigin` by scheme + host (case/trailing-dot insensitive) + port, except loopback hosts skip the port check (`AllowedOrigin#matches?`, `LOOPBACK_HOSTS`).
- **FR-010**: System MUST scope `Spree::Market` and `Spree::AllowedOrigin` to a single owning store via `Spree::SingleStoreResource` (auto-assigns `Spree::Current.store` on create, forbids re-assigning `store_id` after persistence).
- **FR-011**: System MUST resolve the most specific matching `Spree::Zone` for an address via `Zone.match`, preferring state-kind zones over country-kind zones.
- **FR-012**: System MUST keep `Zone#kind` self-consistent by pruning `ZoneMember` rows whose type no longer matches the zone's inferred kind after each save (`Zone#remove_defunct_members`).
- **FR-013**: System MUST provide `Store#allowed_origin?(url)` and `Store#storefront_url` as the store-level API surface for the CORS/origin allowlist, consumed elsewhere (guest cart auth, transactional email links).

### Key Entities *(include if feature involves data)*

- **Spree::Store**: Root tenant/config entity. Owns preferences (timezone, weight/unit system, checkout flags), a translated `TRANSLATABLE_FIELDS` set, and `has_many :markets`, `has_many :channels`, `has_many :allowed_origins`. `belongs_to :checkout_zone` (deprecated, superseded by Markets).
- **Spree::Market**: Belongs to one `Store`. Groups `Spree::Country` records (via `market_countries`/`countries`) under one `currency`, `default_locale`, `supported_locales`. Exactly one per store may be `default`. Ordered by `acts_as_list scope: :store_id`.
- **Spree::MarketCountry**: Join model between `Market` and `Country` (referenced, not separately reviewed in depth — see gap below).
- **Spree::Zone**: Named grouping of `Spree::Country` or `Spree::State` records via polymorphic `Spree::ZoneMember`. Consumed by `TaxRate` (tax) and `ShippingMethodZone` (shipping eligibility). Not store-scoped (global).
- **Spree::ZoneMember**: Polymorphic join (`zoneable_type`/`zoneable_id`) between a `Zone` and a `Country` or `State`, with a `counter_cache` on `Zone`.
- **Spree::AllowedOrigin**: Belongs to one `Store`. Stores a single validated HTTP(S) origin string used for CORS/storefront-origin matching.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Store`, `Spree::Stores::Markets`/`Channels` concerns, `Spree::Market`, `Spree::Zone`, `Spree::ZoneMember`, `Spree::AllowedOrigin`, `Spree::SingleStoreResource` concern |
| `spree/api` (Store/Admin API v3) | Yes | `Admin::MarketsController`/`MarketSerializer`, `Store::MarketsController`/`MarketSerializer`, `Admin::AllowedOriginsController`/`AllowedOriginSerializer`, `Store::CurrenciesController`, `Store::LocalesController`, `Admin::LocalesController` |
| `packages/dashboard` (admin SPA) | Yes | `routes/_authenticated/$storeId/settings/markets.tsx`, `.../allowed-origins.tsx`, `tables/markets.tsx`, `tables/allowed-origins.tsx`, `hooks/use-markets.ts`, `hooks/use-allowed-origins.ts`, `schemas/market.ts` — no equivalent Zones route exists in the SPA (legacy-admin-only today, see Migration Notes) |
| `packages/dashboard-ui` / `dashboard-core` | No | No dedicated primitive/registry entries found beyond standard `ResourceTable` usage |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated types for `AllowedOrigin`, `Market` (regenerated from serializers, not hand-written) |
| `docs/plans/` | Yes | `docs/plans/6.0-tax-provider.md` already governs the planned removal of `Spree::Zone` — see Migration Notes; no dedicated `docs/plans/` entry exists for Stores/Markets/AllowedOrigin themselves |

### API Contract *(include if feature touches spree/api)*

- **Endpoints**:
  - Store API: `GET /api/v3/store/markets`, `GET /api/v3/store/markets/:id`, `GET /api/v3/store/markets/resolve`, `GET /api/v3/store/currencies`, `GET /api/v3/store/locales`
  - Admin API: full CRUD `/api/v3/admin/markets`, full CRUD `/api/v3/admin/allowed_origins`, `GET /api/v3/admin/locales`
- **Serializer fields (read)**:
  - `MarketSerializer` (Store, extended by Admin): `name`, `currency`, `default_locale`, `tax_inclusive`, `default`, `country_isos`, `supported_locales` (computed), optional expanded `countries`; Admin adds `created_at`, `updated_at`.
  - `AllowedOriginSerializer` (Admin only — no Store-facing serializer, by design, since this is admin-only config): `origin`, `created_at`, `updated_at`.
  - Admin `MarketsController#permitted_params` accepts `name, currency, default_locale, tax_inclusive, default, position, supported_locales: [], country_isos: []` — matches serializer read surface (Constitution Principle III honored: `country_isos`/`supported_locales` read and write symmetrically as arrays, translated by model setters).
  - Admin `AllowedOriginsController#permitted_params` accepts only `:origin` — matches serializer read surface exactly.
- **Auth**: Store API endpoints use publishable key (`allow_guest_storefront_access!`); Admin API endpoints use the standard `ResourceController`/`Admin::BaseController` secret-key-or-JWT auth, scoped under `scoped_resource :settings`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A store with N markets exposes all N markets' currencies/locales via the Store API with zero duplicate entries.
- **SC-002**: A store can never end up with zero markets after having had at least one (deletion of the last/default market is always blocked at the model layer).
- **SC-003**: An `AllowedOrigin` correctly discriminates between matching and non-matching candidate URLs for 100% of scheme/host/port combinations exercised in `Spree::AllowedOrigin#matches?` (loopback-port-exempt, non-loopback-port-strict).
- **SC-004**: `Zone.match` returns a deterministic, priority-ordered result (state before country) for any address covered by more than one zone kind.

## Assumptions

- This is a reverse-engineered spec for already-shipped code; "requirements" describe observed behavior, not aspirational behavior — gaps are called out explicitly in Migration Notes rather than silently filled in.
- `Spree::MarketCountry` was referenced but not independently read in full; its role is inferred from `Market`'s associations only.
- The Store API deliberately has no `AllowedOrigin`-reading endpoint — it's treated as admin-only configuration, consumed server-side (`Store#allowed_origin?`) rather than exposed to storefront clients.
- Legacy `Store#checkout_zone`/`checkout_zone=` are deprecated pass-throughs (warn-and-delegate) already mid-migration toward Markets; new work should not add call sites for them.

## Migration Notes

- **Zone model is slated for full removal in 6.0.** Per `docs/plans/6.0-tax-provider.md` ("Drop TaxZone — TaxRate links directly to country/state", line ~207-233): `Spree::Zone` and `Spree::ZoneMember` are dropped entirely; `TaxRate` gets direct `country_id`/`state_id` FKs, and shipping zone coverage moves to a new `DeliveryZone` model (see `docs/plans/6.0-delivery-rate-provider.md`). A rake task (`spree:migrate_zones`, still unimplemented per the plan) is expected to backfill `TaxRate` and `DeliveryZone` from existing `Zone`/`ZoneMember` rows, after which `spree_zones`/`spree_zone_members` tables are dropped. Any new spec-kit feature touching tax or shipping zone logic MUST NOT deepen the dependency on `Spree::Zone` — prefer the country/state FK pattern the target plan describes.
- **No dedicated Zones admin-SPA route exists.** Zones are only manageable via the legacy Rails admin (`spree/admin/app/controllers/spree/admin/zones_controller.rb`, `spree/admin/app/views/spree/admin/zones/`) plus embedded pickers in shipping-method and price-rule forms. Per Constitution Principle II/the "legacy admin phased out" rule, no new Zone UI should be added to `spree/admin`; given the planned 6.0 removal, building a dashboard SPA route for Zones is likely wasted effort — flagging for reviewer judgment rather than assuming either direction.
- **`Store#checkout_zone` is a deprecated bridge**, not a live association — it warns and delegates to the underlying `belongs_to :checkout_zone` column, which itself predates Markets. Treat any future touch to this accessor as a deletion candidate, not a maintenance target.
- **No `docs/plans/` entry exists specifically for Markets/AllowedOrigin's own history** (e.g., when Markets was introduced, or what it superseded) — inferred entirely from code comments (`@deprecated Use Markets instead. Will be removed in Spree 5.5.` on `Store#checkout_zone`) rather than a plan document. If a future architectural change touches Markets, consider backfilling a `docs/plans/` entry per Constitution Principle VI, since none currently exists to check for conflicts.
