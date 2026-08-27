# Implementation Plan: Stores, Markets & Zones

**Branch**: `018-stores-markets-zones` | **Date**: 2026-08-25 | **Spec**: `specs/018-stores-markets-zones/spec.md`

**Input**: Feature specification from `specs/018-stores-markets-zones/spec.md`

**Note**: This is a **brownfield reverse-engineering** plan — the feature is already implemented and shipped. There is no Phase 0/1 research to perform; this document records the actual architecture as built, for future spec-kit-driven changes to build on top of.

## Summary

`Spree::Store` is the tenant root. `Spree::Market` (store-scoped, via `Spree::SingleStoreResource`) groups countries under a currency/locale and supersedes the legacy store-level `default_currency`/`default_locale`/`supported_currencies`/`supported_locales` columns once any market exists (`Spree::Stores::Markets` concern). `Spree::Zone`/`Spree::ZoneMember` is a global (non-store-scoped) geographic grouping still used by `TaxRate` and `ShippingMethodZone`, but is explicitly slated for removal in 6.0 per `docs/plans/6.0-tax-provider.md`. `Spree::AllowedOrigin` (also store-scoped via `Spree::SingleStoreResource`) is an independent CORS/origin allowlist consumed by `Store#allowed_origin?`/`#storefront_url`. All four models are exposed through Admin API v3 CRUD (markets, allowed origins) and read-only Store API v3 endpoints (markets, currencies, locales); the admin SPA has table/route/hook coverage for Markets and Allowed Origins but none for Zones (legacy-Rails-admin-only).

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`) and TypeScript (React SPA, `packages/dashboard`)

**Primary Dependencies**: Backend: CanCanCan, Alba serializers, `acts_as_list`, `acts_as_paranoid`, Mobility (translations on `Store`). Frontend: TanStack Router/Query, React Hook Form + Zod, shadcn/ui + Base UI.

**Storage**: PostgreSQL/MySQL/SQLite via ActiveRecord — no FK constraints, per migration conventions. Key tables: `spree_stores`, `spree_markets`, `spree_market_countries`, `spree_zones`, `spree_zone_members`, `spree_allowed_origins`.

**Testing**: RSpec + Factory Bot (`spree/core/spec/models/spree/{store,market,zone,allowed_origin}_spec.rb`, `spree/api/spec/integration/{markets,allowed_origins,currencies,locales}_spec.rb`), Playwright (no e2e spec found for markets/allowed-origins/zones as of this review — see Gaps).

**Target Platform**: Rails engine gems consumed by a Spree host app; React SPA served standalone against the Admin/Store API v3.

**Project Type**: Monorepo — `spree/core`, `spree/api`, `packages/dashboard` (+ generated `packages/sdk`/`packages/admin-sdk` types).

**Performance Goals**: N/A — no documented performance targets found for this feature; Store API market/currency/locale endpoints are HTTP-cached (`Spree::Api::V3::HttpCaching`) per-store/per-collection.

**Constraints**: A store must always retain at least one `Market` once markets exist (`Market#can_be_deleted?`); `AllowedOrigin#origin` must be a bare HTTP(S) origin (no path/query/fragment).

**Scale/Scope**: Per-store cardinality — typically single-digit Markets and AllowedOrigins per store; Zones are global (not store-scoped) and can be large in count across a multi-tenant install (out of this feature's ownership, shared with Tax/Shipping).

## Constitution Check

*Retrospective check — this is reverse-engineered documentation of already-shipped code, not a forward plan gated on these principles before implementation.*

- **I. Module Boundaries**: Touches `spree/core` (models/concerns), `spree/api` (controllers/serializers), `packages/dashboard` (routes/tables/hooks for Markets and Allowed Origins only). No boundary violations found — the dashboard consumes these exclusively through `@spree/admin-sdk`, never reaching into Rails models directly.
- **II. Admin API Is the Only Frontend Data Source**: Satisfied — `use-markets.ts`/`use-allowed-origins.ts` wrap `adminClient` calls; no server-rendered HTML or direct model access from the SPA.
- **III. Read/Write Field Symmetry**: Satisfied for both reviewed controllers — `Admin::MarketsController#permitted_params` and `Admin::AllowedOriginsController#permitted_params` each permit exactly what their serializers expose (`country_isos`/`supported_locales` as arrays on both sides; `origin` alone for allowed origins).
- **IV. Test-Backed**: RSpec model specs exist for `Market`/`Zone`/`AllowedOrigin`/`Store` (not individually re-verified line-by-line in this pass — flagged as an assumption, not a confirmed gap). No Playwright e2e coverage was located for these settings pages during this review — flagged as a gap below.
- **V. Translations and Prefixed IDs**: Prefixed IDs confirmed (`has_prefix_id :mkt` on Market, `:ao` on AllowedOrigin, `:store` on Store, `:zone` on Zone). Dashboard i18n usage not independently audited in this pass.
- **VI. `docs/plans/` for Architectural Changes**: `docs/plans/6.0-tax-provider.md` already governs the Zone-model removal that intersects this area — any future change here MUST check that plan's "Constraints on Current Work" per Constitution Principle VI. No `docs/plans/` entry exists for Markets/AllowedOrigin themselves (see spec.md Migration Notes).

No violations requiring Complexity Tracking — this is a documentation-only migration pass, not new implementation.

## Project Structure

### Documentation (this feature)

```text
specs/018-stores-markets-zones/
├── plan.md              # This file
├── spec.md              # Reverse-engineered specification
└── tasks.md             # Reverse-engineered task record (all marked done)
```

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/
├── app/models/spree/store.rb
├── app/models/spree/market.rb
├── app/models/spree/market_country.rb          # join model (Market <-> Country), not deeply reviewed
├── app/models/spree/zone.rb
├── app/models/spree/zone_member.rb
├── app/models/spree/allowed_origin.rb
├── app/models/concerns/spree/single_store_resource.rb
├── app/models/concerns/spree/stores/markets.rb
├── app/models/concerns/spree/stores/channels.rb
├── db/migrate/20260220000000_create_spree_markets.rb
├── db/migrate/20260315000000_create_spree_allowed_origins.rb
├── db/migrate/20260403000000_add_market_to_spree_orders.rb
├── db/migrate/20260408000001_add_unique_index_to_spree_zone_members.rb
├── db/sample_data/markets.rb
└── spec/models/spree/{store,market,zone,allowed_origin}_spec.rb

# spree/api — Store & Admin REST API v3
spree/api/
├── app/controllers/spree/api/v3/admin/markets_controller.rb
├── app/controllers/spree/api/v3/admin/allowed_origins_controller.rb
├── app/controllers/spree/api/v3/admin/locales_controller.rb
├── app/controllers/spree/api/v3/store/markets_controller.rb
├── app/controllers/spree/api/v3/store/currencies_controller.rb
├── app/controllers/spree/api/v3/store/locales_controller.rb
├── app/serializers/spree/api/v3/market_serializer.rb
├── app/serializers/spree/api/v3/admin/market_serializer.rb
├── app/serializers/spree/api/v3/admin/allowed_origin_serializer.rb
└── spec/integration/{markets,allowed_origins,currencies,locales}_spec.rb

# spree/admin — legacy Rails admin (Zones only; no SPA equivalent — see Migration Notes)
spree/admin/
├── app/controllers/spree/admin/zones_controller.rb
├── app/views/spree/admin/zones/
└── app/javascript/spree/admin/controllers/zone_state_select_controller.js

# packages/dashboard — admin SPA routes/forms (Markets + Allowed Origins only)
packages/dashboard/src/
├── routes/_authenticated/$storeId/settings/markets.tsx
├── routes/_authenticated/$storeId/settings/allowed-origins.tsx
├── tables/markets.tsx
├── tables/allowed-origins.tsx
├── hooks/use-markets.ts
├── hooks/use-allowed-origins.ts
├── schemas/market.ts
├── components/spree/promotion-editors/rule-market.tsx
└── components/spree/price-list-editors/rule-market.tsx

# packages/sdk / packages/admin-sdk — generated types
packages/admin-sdk/src/types/generated/{AllowedOrigin,Market}.ts   # regenerated, not hand-edited
```

**Structure Decision**: Backend (`spree/core` + `spree/api`) owns all four models and their API surfaces; `packages/dashboard` owns Markets + Allowed Origins UI (no Zones UI exists or is planned — legacy-admin-only, pending removal per `docs/plans/6.0-tax-provider.md`).

## Complexity Tracking

*No violations identified requiring justification — see Constitution Check above.*
