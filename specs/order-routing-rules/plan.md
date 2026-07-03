# Implementation Plan: Order Routing Rules

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Phase 1 (5.5) shipped — Channel, OrderRoutingRule, strategy base + built-in rules + reducer + legacy; Phase 2+ (6.0) pending

---

## Summary

Replaces the implicit, unswappable `Spree::Stock::Coordinator` + `Prioritizer` location selection with a layered two-tier extension model: a four-method `Strategy::Base` contract for full algorithm replacement (OMS, ML, solver), and `Spree::OrderRoutingRule` STI subclasses for the common case of new signals within the built-in rules-walking strategy. `Spree::Channel` is the per-context configuration unit — Phase 1 ships `Channel`, `OrderRoutingRule` (STI base), `Strategy::Base` + `Strategy::Rules` + three built-in rule subclasses + the reducer + a `Legacy` strategy that delegates to the old Coordinator. The Admin SPA has a settings page for channels with routing rule management.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Extension point 1** | Custom `Strategy::Base` subclass — full algorithm replacement (rare) |
| **Extension point 2** | Custom `OrderRoutingRule` STI subclass registered via `Spree.order_routing.rules` (common) |
| **Ordering** | `acts_as_list` on `OrderRoutingRule` for `position`-based reducer walk |
| **Scope** | Phase 1 (5.5) fully shipped; Phase 2 (6.0 Catalog/Company) pending |

---

## Key Decisions

1. **Strategy contract is total replacement, not a hook framework.** `Strategy::Base` declares four `NotImplementedError` methods; no defaults. Partial overriding leads to subtle bugs. A custom strategy is a complete, self-contained algorithm. The `Legacy` strategy in core wraps the old Coordinator for stores that don't opt in.

2. **`Rules` is the only concrete strategy in core.** All other strategies are downstream plugins. `Rules` walks `OrderRoutingRule` rows and delegates to the reducer.

3. **Rules are STI subclasses with a config registry.** `Spree.order_routing.rules` is the allowlist for admin pickers and type validation — same pattern as `Spree::PromotionRule`, `Spree::Calculator`, and `Spree::PaymentMethod`. Plugins call `Spree.order_routing.rules << MyRule` in `config.after_initialize`.

4. **Reducer: first non-tie wins.** Each rule produces a `LocationRanking[]` — lower rank = better. The reducer walks rules in `position` order; first rule that produces a unique winner stops. Ties carry to the next rule. All-tie → `StockLocation.default`, then by ID. No weighted scoring — it makes rule interactions unpredictable.

5. **`Spree::Channel` is the routing configuration unit.** In 5.5, one channel maps to one strategy configuration. In 6.0 (Phase 2), catalog isolation and B2B company defaults layer on top of the same channel via `6.0-channels-catalogs-b2b.md`.

6. **`preferred_stock_location_id` on `Channel` feeds the `PreferredLocation` rule.** It's a first-class FK — not a preference JSON blob — because it drives DB queries and must be filterable/preloadable.

7. **`Channel#default` boolean determines the fallback channel for orders without an explicit `channel_id`.** Only one channel should be default; no DB uniqueness constraint — merchant responsibility. `Channel.default` scope returns the default channel.

8. **`Legacy` strategy for backward compat.** Stores upgrading from pre-5.5 continue using the old Coordinator behavior via the `Legacy` strategy until they configure rules. This ensures zero behavior change on upgrade for stores that don't configure routing.

---

## Constitution Check

- [x] **API-First**: Admin API for channels and routing rules precedes SPA
- [x] **Read/Write Symmetry**: `name`, `default`, `preferred_stock_location_id` serialized and accepted; `OrderRoutingRule` `position` and `preferences` symmetrical
- [x] **Prefixed IDs**: `ch_…` for channels; `orule_…` for routing rules
- [x] **Serializer Hierarchy**: `Admin::ChannelSerializer` (admin-only — no Store serializer)
- [x] **Type Pipeline**: Typelizer + Zod regen after serializer changes
- [x] **Security**: CanCanCan `can :manage, Spree::Channel`; `can :manage, Spree::OrderRoutingRule`
- [x] **Namespace**: `Spree::Channel`, `Spree::OrderRoutingRule`, `Spree::OrderRouting::Strategy::*` — `Spree` namespace throughout
- [x] **Plan Conflicts**: Reviewed `6.0-channels-catalogs-b2b.md` — Phase 2 layers Catalog/Company on Channel; no conflict with Phase 1. Reviewed `6.0-stock-reservations.md` — reservations use routing output; no conflict.

---

## Project Structure

```text
# Backend — models (Phase 1 ✅)
spree/core/app/models/spree/channel.rb                              ← default, preferred_stock_location_id, store_id
spree/core/app/models/spree/order_routing_rule.rb                   ← STI base, acts_as_list position

spree/core/app/models/spree/order_routing/strategy/base.rb          ← four NotImplementedError methods
spree/core/app/models/spree/order_routing/strategy/rules.rb         ← walks rules + reducer
spree/core/app/models/spree/order_routing/strategy/legacy.rb        ← wraps old Coordinator

spree/core/app/models/spree/order_routing/rules/preferred_location.rb
spree/core/app/models/spree/order_routing/rules/minimize_splits.rb
spree/core/app/models/spree/order_routing/rules/default_location.rb

# Backend — serializers
spree/api/app/serializers/spree/api/v3/admin/channel_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/order_routing_rule_serializer.rb

# Backend — controllers
spree/api/app/controllers/spree/api/v3/admin/channels_controller.rb

# Frontend (Phase 1 ✅)
packages/dashboard/src/routes/_authenticated/$storeId/settings/channels.tsx
packages/dashboard/src/hooks/use-channels.ts
packages/dashboard/e2e/channels.spec.ts
packages/dashboard/e2e/channels-settings.spec.ts
```

---

## Phase 1: 5.5 — Channel + Rules Engine (✅ Complete)

- `Spree::Channel` model with `default`, `preferred_stock_location_id`, `store_id`
- `Spree::OrderRoutingRule` STI base with `acts_as_list`
- Three built-in rule subclasses: `PreferredLocation`, `MinimizeSplits`, `DefaultLocation`
- `Strategy::Base` (contract), `Strategy::Rules` (reducer), `Strategy::Legacy` (backward compat)
- `Spree.order_routing.rules` registry
- `Order#channel_id` FK + `Order#preferred_stock_location_id` hint
- Admin API: full CRUD for channels + routing rules (nested)
- Admin SPA: channels settings page, routing rules editor, channels E2E tests

---

## Phase 2: 6.0 — Catalog / Company (PENDING)

Per `6.0-channels-catalogs-b2b.md`:

- Catalog model: per-channel product publication visibility
- Company / CompanyLocation / CompanyContact for B2B
- Channel → Company routing hints (B2B default location)
- `OrderRoutingRule` subclasses for company-context signals

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Two-tier extension (strategy + rules) | Strategies allow full algorithm replacement (OMS, ML); rules allow new signals within the rules-walking algorithm — different extension granularities | A single extension point covers either "replace everything" OR "add a signal" but not both. Vendure has strategy-only; Shopify has rules-only (Plus-gated). Spree needs both. |
| STI + config registry for rules | STI enables persistence and admin configuration; registry is the allowlist + type validation | Pure virtual dispatch (no persistence) would mean routing configuration resets on deploy; pure DB without registry would allow arbitrary class injection |
