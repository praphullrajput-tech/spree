# Implementation Plan: Channels & Order Routing

**Branch**: `019-channels-and-order-routing` | **Date**: 2026-08-24 | **Spec**: `specs/019-channels-and-order-routing/spec.md`

**Input**: Feature specification from `specs/019-channels-and-order-routing/spec.md`

**Note**: This plan is reverse-engineered (`/speckit.brownfield.migrate`) from already-shipped code. It documents the as-built architecture rather than prescribing new work.

## Summary

Replace the free-text `Order.channel` string and the implicit,
unswappable `Spree::Stock::Coordinator` location selection with two
first-class concepts: `Spree::Channel` (a distribution surface within a
Store, carrying order attribution and a routing/gating preference
override) and a two-tier order-routing extension (`Strategy::Base`
subclasses as swappable algorithms; `OrderRoutingRule` STI subclasses as
swappable signals consumed by the one concrete core strategy,
`Strategy::Rules`). Channel additionally owns storefront-access gating
(`public` / `prices_hidden` / `login_required`) and a `guest_checkout`
override, both falling back to Store-level preferences and enforced
server-side in the v3 Store API.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`); TypeScript (React SPA, `packages/dashboard`) for the Settings → Sales channels page.

**Primary Dependencies**: `acts_as_list` (rule position ordering, scoped to `channel_id`), `Spree::Preferences` (typed `preference` DSL for strategy/rule config — same mechanism as `Spree::PromotionRule`/`Spree::Calculator`), CanCanCan (Admin API authorization), Alba (serializers). Frontend: TanStack Query (`use-channels.ts`), React Hook Form + Zod (`schemas/channel.ts`).

**Storage**: PostgreSQL (production) / SQLite3 (test default), via ActiveRecord. `spree_channels` (with partial unique index on `(store_id) WHERE default = TRUE` on Postgres/SQLite; model-level uniqueness validation covers MySQL), `spree_order_routing_rules` (STI `type` discriminator, `channel_id` + `position` composite index), `spree_product_publications`. `Order.channel_id` / `Order.preferred_stock_location_id` FKs on `spree_orders`. No foreign key constraints, per migration conventions.

**Testing**: RSpec + Factory Bot — `spree/core/spec/models/spree/channel_spec.rb`, `spree/core/spec/models/spree/order_routing_rule_spec.rb`, `spree/core/spec/models/spree/order_routing/strategy/*_spec.rb` (including the parity spec running shared examples against `Legacy` and `Rules`), `spree/api/spec/controllers/spree/api/v3/admin/channels_controller_spec.rb`, `spree/api/spec/integration/spree/api/v3/admin/channels_spec.rb`, `spree/api/spec/controllers/concerns/spree/api/v3/channel_resolution_spec.rb`.

**Target Platform**: Rails engine gems consumed by a Spree host app (`spree/core`, `spree/api`); React SPA (`packages/dashboard`) for the admin settings surface.

**Project Type**: Monorepo — `spree/core`, `spree/api` (Ruby gems), `packages/dashboard` + `packages/admin-sdk` (TypeScript packages).

**Performance Goals**: Rule ranking must not add per-location N+1 queries — `MinimizeSplits` batches its `StockItem` lookup into one query for the full location × variant matrix rather than looping.

**Constraints**: No FK constraints, no column defaults, explicit `null: false` per migration conventions; `Channel#add_products`/`#remove_products` must stay idempotent for bulk re-publish (documented "don't change this" constraint in the plan).

**Scale/Scope**: Backend-heavy — 1 model (`Channel` + `Gating` concern), 1 STI base + 3 built-in rule subclasses, 4 strategy classes, 1 concern (`HasStrategyPreference`), 1 Admin API controller + 2 serializers + 2 API concerns (`ChannelResolution`, `StorefrontGating`); frontend is a single Settings page + supporting hook/schema/select component.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (models, strategy/rule/reducer classes), `spree/api` (Admin controller, serializers, two API concerns), `packages/dashboard` + `packages/admin-sdk` (settings page, generated types). No direct cross-boundary reach — the SPA only calls the Admin API via `@spree/admin-sdk`; the API only reads `spree/core` models. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: The dashboard's Sales Channels page and rule pickers consume `Admin::ChannelsController` exclusively through `use-channels.ts` → `adminClient`; no Rails view/model is reached directly from the SPA. **Pass.**
- **III. Read/Write Field Symmetry**: Partially satisfied. `name`, `code`, `active`, `default`, `preferred_order_routing_strategy` are symmetric (exposed + permitted). **Gap**: `preferred_storefront_access` and `preferred_guest_checkout` are exposed on the Admin serializer's read side but absent from `permitted_params` — flagged in spec.md Migration Notes as a follow-up, not a blocker for this migrated spec since no admin UI currently writes those fields.
- **IV. Test-Backed**: RSpec covers `Channel`, `OrderRoutingRule`, each `Rules::*` subclass, `Reducer`, `Strategy::Rules`/`Strategy::Legacy` parity, and the Admin API controller/integration/concern specs listed above. No Playwright e2e exists yet for the Sales Channels settings page — gap noted below.
- **V. Translations and Prefixed IDs**: `Spree::Channel` uses `has_prefix_id :ch`; `Spree::OrderRoutingRule` uses `has_prefix_id :orule`. Dashboard Sales Channels page strings route through i18next per existing `packages/dashboard/src/locales/en.json` conventions (not independently re-verified key-by-key in this migration pass).
- **VI. `docs/plans/` for Architectural Changes**: Directly implements `docs/plans/6.0-order-routing.md` Phase 1 and `docs/plans/6.0-channels-catalogs-b2b.md` Phase 1 + Phase 1.5. Both plans' "Constraints on Current Work" sections apply and are cross-referenced in spec.md.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/019-channels-and-order-routing/
├── spec.md               # Feature spec (this migration)
├── plan.md               # This file
└── tasks.md              # Task checklist (migrated, all marked done)
```

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/
├── app/models/spree/channel.rb
├── app/models/spree/channel/gating.rb
├── app/models/spree/order_routing_rule.rb
├── app/models/spree/order_routing/has_strategy_preference.rb
├── app/models/spree/order_routing/rules/preferred_location.rb
├── app/models/spree/order_routing/rules/minimize_splits.rb
├── app/models/spree/order_routing/rules/default_location.rb
├── app/models/spree/order_routing/strategy/base.rb
├── app/models/spree/order_routing/strategy/rules.rb
├── app/models/spree/order_routing/strategy/legacy.rb
├── app/models/spree/order_routing/strategy/reducer.rb
├── app/models/spree/product_publication.rb
├── app/models/concerns/spree/stores/channels.rb
├── db/migrate/20260508204040_create_spree_channels.rb
├── db/migrate/20260601000001_create_spree_product_publications.rb
├── db/migrate/20260601000002_add_store_id_to_spree_products.rb
├── db/migrate/20260602000001_add_default_to_spree_channels.rb
└── spec/models/spree/{channel,order_routing_rule}_spec.rb, spec/models/spree/order_routing/**/*_spec.rb

# spree/api — Store & Admin REST API v3
spree/api/
├── app/controllers/spree/api/v3/admin/channels_controller.rb
├── app/controllers/concerns/spree/api/v3/channel_resolution.rb
├── app/controllers/concerns/spree/api/v3/storefront_gating.rb
├── app/serializers/spree/api/v3/channel_serializer.rb
├── app/serializers/spree/api/v3/admin/channel_serializer.rb
├── spec/controllers/spree/api/v3/admin/channels_controller_spec.rb
├── spec/controllers/concerns/spree/api/v3/channel_resolution_spec.rb
└── spec/integration/spree/api/v3/admin/channels_spec.rb

# packages/dashboard — admin SPA routes/forms
packages/dashboard/src/
├── routes/_authenticated/$storeId/settings/channels.tsx
├── tables/channels.tsx
├── hooks/use-channels.ts
├── schemas/channel.ts
└── components/spree/channel-select.tsx

# packages/admin-sdk — generated client
packages/admin-sdk/src/types/generated/Channel.ts   # regenerated, not hand-edited
```

**Structure Decision**: Backend-primary — the routing/gating logic and its
extension points live entirely in `spree/core` + `spree/api`; the dashboard
SPA carries a thin settings surface (list/create/edit channels, pick a
strategy) with no headless `dashboard-ui` primitives or `dashboard-core`
registries specific to this feature.

## Complexity Tracking

No Constitution violations requiring justification.
