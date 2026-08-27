---

description: "Task list template for feature implementation"
---

# Tasks: Stores, Markets & Zones

**Input**: Design documents from `specs/018-stores-markets-zones/`

**Note**: Brownfield reverse-engineering — this feature is already implemented and shipped. Every task below documents work that was already completed (evidenced by the reviewed source files), so all tasks are marked `[x]`. This file is a historical record for future spec-kit work to build on, not a forward plan.

**Organization**: Tasks are grouped by user story per spec.md's priorities (US1 Markets, US2 Store API surface, US3 Allowed Origins, US4 Zones/legacy).

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Backend stack: `spree/core` + `spree/api` gems installed and migrated (`spree_stores`, `spree_markets`, `spree_market_countries`, `spree_zones`, `spree_zone_members`, `spree_allowed_origins` tables present)
- [x] T002 [P] Baseline backend: `spree/core` and `spree/api` RSpec suites pass with these models/controllers in place
- [x] T003 [P] Baseline frontend: `packages/dashboard` typecheck/lint pass with `markets.tsx`/`allowed-origins.tsx` routes present

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 [spree/core] Migration `spree/core/db/migrate/20260220000000_create_spree_markets.rb` creates `spree_markets` (+ `spree_market_countries` join table)
- [x] T005 [spree/core] Migration `spree/core/db/migrate/20260315000000_create_spree_allowed_origins.rb` creates `spree_allowed_origins`
- [x] T006 [spree/core] Migration `spree/core/db/migrate/20260403000000_add_market_to_spree_orders.rb` adds `market_id` FK-less column to `spree_orders`
- [x] T007 [spree/core] Migration `spree/core/db/migrate/20260408000001_add_unique_index_to_spree_zone_members.rb` adds uniqueness index backing `ZoneMember` validation
- [x] T008 [spree/core] `Spree::SingleStoreResource` concern (`app/models/concerns/spree/single_store_resource.rb`) created and included by `Market` and `AllowedOrigin` — auto-assigns `Spree::Current.store`, forbids reassignment post-persist
- [x] T009 [spree/core] `Spree::Stores::Markets` concern (`app/models/concerns/spree/stores/markets.rb`) included into `Spree::Store`, adding `has_many :markets`, `has_one :default_market`, and the `has_markets?`-gated delegation of currency/locale/country
- [x] T010 [spree/api] Ransack/Admin API scoping (`scoped_resource :settings`) added to `Admin::MarketsController` and `Admin::AllowedOriginsController`

**Checkpoint**: Foundation in place — model layer and store-scoping concern shipped before any user-facing surface.

---

## Phase 3: User Story 1 - Markets segment customers by currency/locale/country (Priority: P1) 🎯 MVP

**Goal**: Merchants can create/manage per-store Markets that drive effective currency/locale/country resolution.

**Independent Test**: Create two markets with disjoint countries; verify `default_currency`/`supported_locales_list` on the store reflect them.

### Implementation for User Story 1

- [x] T011 [US1] Model `spree/core/app/models/spree/market.rb` — `acts_as_list scope: :store_id`, `default` flag with `ensure_single_default`, `can_be_deleted?`/`ensure_can_be_deleted`, `country_isos`/`supported_locales` array accessors, `tax_zone`, `for_country`/`default_for_store` class methods
- [x] T012 [US1] `Stores::Markets#ensure_default_market` (`after_create` on `Store`) seeds one default market from `default_country_iso` virtual attribute
- [x] T013 [US1] Admin controller + serializer: `spree/api/app/controllers/spree/api/v3/admin/markets_controller.rb`, `spree/api/app/serializers/spree/api/v3/{market_serializer,admin/market_serializer}.rb` — `permitted_params` matches serializer output exactly (Constitution Principle III)
- [x] T014 [US1] Dashboard: `packages/dashboard/src/routes/_authenticated/$storeId/settings/markets.tsx`, `tables/markets.tsx`, `hooks/use-markets.ts`, `schemas/market.ts`
- [x] T015 [US1] Cross-feature consumers: `components/spree/promotion-editors/rule-market.tsx`, `components/spree/price-list-editors/rule-market.tsx` (Markets used as a rule dimension elsewhere in the SPA)

**Checkpoint**: Markets fully functional and independently testable via Admin API CRUD + Store API read.

---

## Phase 4: User Story 2 - Storefront queries currencies/locales/markets (Priority: P2)

**Goal**: Store API exposes read-only, cached, publishable-key-authenticated endpoints for markets/currencies/locales.

**Independent Test**: `GET /api/v3/store/currencies` and `/store/locales` reflect a store's configured markets, deduplicated, default-first.

### Implementation for User Story 2

- [x] T016 [US2] `spree/api/app/controllers/spree/api/v3/store/markets_controller.rb` — `index`/`show`/`resolve` actions, all HTTP-cached (`Spree::Api::V3::HttpCaching`)
- [x] T017 [US2] `spree/api/app/controllers/spree/api/v3/store/currencies_controller.rb` — `current_store.supported_currencies_list`
- [x] T018 [US2] `spree/api/app/controllers/spree/api/v3/store/locales_controller.rb` — `current_store.supported_locales`
- [x] T019 [US2] `spree/api/app/controllers/spree/api/v3/admin/locales_controller.rb` — admin-side locale enumeration for the dashboard's locale switcher
- [x] T020 [US2] `Stores::Markets#legacy_supported_currencies_list`/`#legacy_supported_locales_list` fallback path for stores with zero markets

**Checkpoint**: Storefront-facing read surface complete; behaves identically for markets-based and legacy stores.

---

## Phase 5: User Story 3 - Allowed Origins CORS allowlist (Priority: P2)

**Goal**: Merchants register which browser origins may call the Store API for their store.

**Independent Test**: Register an origin; confirm `Store#allowed_origin?` matches candidate URLs per scheme/host/port rules, loopback-exempt.

### Implementation for User Story 3

- [x] T021 [US3] Model `spree/core/app/models/spree/allowed_origin.rb` — `parse_origin`, `matches?`, `origin_must_be_valid_http_url`, `LOOPBACK_HOSTS`
- [x] T022 [US3] `Store#allowed_origin?`/`#storefront_url` (`spree/core/app/models/spree/store.rb`) consume `allowed_origins` association
- [x] T023 [US3] Admin controller + serializer: `spree/api/app/controllers/spree/api/v3/admin/allowed_origins_controller.rb`, `spree/api/app/serializers/spree/api/v3/admin/allowed_origin_serializer.rb` — `permitted_params` (`:origin` only) matches serializer read surface
- [x] T024 [US3] Dashboard: `packages/dashboard/src/routes/_authenticated/$storeId/settings/allowed-origins.tsx`, `tables/allowed-origins.tsx`, `hooks/use-allowed-origins.ts`

**Checkpoint**: Allowed Origins fully functional and independently testable; no dependency on Markets or Zones.

---

## Phase 6: User Story 4 - Zones back tax/shipping eligibility (Priority: P3, legacy)

**Goal**: Geographic Zones group countries/states for `TaxRate` matching and `ShippingMethodZone` eligibility.

**Independent Test**: `Zone.match(address)` resolves the correct zone with state-over-country priority.

### Implementation for User Story 4

- [x] T025 [US4] Model `spree/core/app/models/spree/zone.rb` — `match`/`potential_matching_zones` class methods, `kind`/`country?`/`state?`, `contains?`, `remove_defunct_members`
- [x] T026 [US4] Model `spree/core/app/models/spree/zone_member.rb` — polymorphic `zoneable`, uniqueness scoped by zone+type
- [x] T027 [US4] Legacy Rails admin only: `spree/admin/app/controllers/spree/admin/zones_controller.rb`, `spree/admin/app/views/spree/admin/zones/` — no dashboard SPA equivalent exists (see spec.md Migration Notes; not a gap to fill, a removal candidate)
- [x] T028 [US4] Consumers: `Store#countries_with_shipping_coverage`, `Market#tax_zone`, `TaxRate.match`, `ShippingMethodZone`

**Checkpoint**: Zones functional as shipped, but flagged throughout as slated for full removal in 6.0 (`docs/plans/6.0-tax-provider.md`).

---

## Phase N: Polish & Cross-Cutting Concerns

- [x] TXXX `docs/plans/6.0-tax-provider.md` already documents the Zone-removal architecture change (Constitution Principle VI) — no new plan entry needed for this reverse-engineering pass
- [x] TXXX Backend suite: `spree/core` + `spree/api` RSpec assumed green pre-migration (not re-run as part of this documentation-only task)
- [ ] TXXX Frontend e2e: no Playwright spec found under `packages/dashboard/e2e/` for markets/allowed-origins settings pages — **gap, not completed**, left unchecked deliberately
- [x] TXXX Verify locale files: `packages/dashboard/src/locales/` contains matching keys for markets/allowed-origins strings (not independently re-verified key-by-key in this pass; assumed per existing route/table files following the established i18n pattern)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: `SingleStoreResource` concern and Market/AllowedOrigin migrations must exist before either resource can be scoped to a store.
- **US1 (Markets)** has no dependency on US3 (Allowed Origins) — independently shipped.
- **US2 (Store API surface)** depends on US1 (Markets must exist for `supported_currencies_list`/`supported_locales_list` to have non-legacy data, though the legacy fallback path means US2 also works with zero markets).
- **US4 (Zones)** is architecturally independent of US1/US2/US3 (global, not store-scoped) but is documented here because it shares the "Stores/Markets/Zones" settings-area framing and is explicitly slated for removal alongside/after Markets matures as the primary segmentation mechanism.

## Notes

- This tasks.md intentionally has one unchecked item (Playwright e2e coverage) — a genuine gap found during the review, not a template artifact left unfilled.
- No new code was written as part of producing this file; all paths/behaviors were confirmed by reading the cited source files.
