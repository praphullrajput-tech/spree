---

description: "Task list for Order Routing Rules — Phase 1 (5.5) shipped; Phase 2 (6.0 Catalog/Company) pending"
---

# Tasks: Order Routing Rules

**Status**: Phase 1 (5.5) fully shipped — Channel + OrderRoutingRule + strategy + built-in rules + reducer + SPA; Phase 2 (6.0) pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Strategy classes | `spree/core/app/models/spree/order_routing/strategy/` |
| Rule subclasses | `spree/core/app/models/spree/order_routing/rules/` |
| Migrations | `spree/core/db/migrate/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/settings/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: 5.5 — Channel + Rules Engine ✅

### Models

- [x] T001 `spree/core/app/models/spree/channel.rb` — `has_prefix_id :ch`; `include Spree::SingleStoreResource`; `include Spree::OrderRouting::HasStrategyPreference`; `belongs_to :store`; `belongs_to :preferred_stock_location` (class_name `Spree::StockLocation`, optional); `default` boolean; `publishes_lifecycle_events`; `scope :default, -> { where(default: true) }`
- [x] T002 `spree/core/app/models/spree/order_routing_rule.rb` — `has_prefix_id :orule`; STI base on `type` column; `acts_as_list`; `belongs_to :channel` (class_name `Spree::Channel`); `whitelisted_ransackable_attributes`; `#rank(order, locations) → Array<LocationRanking>` — raises `NotImplementedError`
- [x] T003 Update `spree/core/app/models/spree/order.rb` — add `belongs_to :channel` (class_name `Spree::Channel`, optional); add `preferred_stock_location_id` string column
- [x] T004 `spree/core/app/models/spree/order_routing/strategy/base.rb` — four `NotImplementedError` methods: `for_allocation(order:)`, `for_sale(fulfillment:)`, `for_release(order:)`, `for_cancellation(order:)`
- [x] T005 `spree/core/app/models/spree/order_routing/strategy/rules.rb` — walks `channel.order_routing_rules.order(:position)`; calls `rule.rank(order, locations)` per rule; applies reducer (first non-tie wins → default → ID)
- [x] T006 `spree/core/app/models/spree/order_routing/strategy/legacy.rb` — delegates to `Spree::Stock::Coordinator` (backward compat for existing stores)
- [x] T007 `spree/core/app/models/spree/order_routing/rules/preferred_location.rb` — ranks `preferred_stock_location_id` from channel preferences as rank 0; all others rank nil (abstain)
- [x] T008 `spree/core/app/models/spree/order_routing/rules/minimize_splits.rb` — ranks locations that can fulfill all items as rank 0; multi-location splits get higher rank
- [x] T009 `spree/core/app/models/spree/order_routing/rules/default_location.rb` — ranks `StockLocation.where(default: true)` as rank 0; all others rank nil

### Configuration

- [x] T010 `Spree.order_routing.rules` — registry; seeded with three built-in rule classes in `config.after_initialize`
- [x] T011 `Spree::OrderRouting::HasStrategyPreference` concern — `preferred_strategy` preference + `routing_strategy` method that resolves to strategy class
- [x] T012 Data migration / seed: existing stores get a default `Channel` with `PreferredLocation`, `MinimizeSplits`, `DefaultLocation` rules in priority order

### Migrations

- [x] T013 Migration: create `spree_channels` — `name string null: false`, `default boolean default false`, `preferred_stock_location_id string`, `store_id string null: false`, timestamps; index `store_id`; index `(store_id, default)`
- [x] T014 Migration: create `spree_order_routing_rules` — `type string null: false`, `position integer null: false`, `preferences jsonb/json`, `channel_id string null: false`, timestamps; index `channel_id`; index `(channel_id, position)` unique
- [x] T015 Migration: add `channel_id string` and `preferred_stock_location_id string` to `spree_orders`; index `channel_id`

### Serializers

- [x] T016 [P] Admin serializer `spree/api/app/serializers/spree/api/v3/admin/channel_serializer.rb` — `id` (ch_…), `name`, `default`, `preferred_stock_location_id` (sloc_…), `routing_strategy`, `store_id`, timestamps
- [x] T017 [P] Admin serializer `spree/api/app/serializers/spree/api/v3/admin/order_routing_rule_serializer.rb` — `id` (orule_…), `type`, `position`, `preferences`, `channel_id` (ch_…), timestamps

### Controllers

- [x] T018 `spree/api/app/controllers/spree/api/v3/admin/channels_controller.rb` — full CRUD; `scope` filtered by `current_store`; `collection_includes`: `order_routing_rules`

### Routes

- [x] T019 Routes: `resources :channels` with nested `resources :order_routing_rules`; add `member { post :reposition }` on `order_routing_rules`

### Specs

- [x] T020 `spree/core/spec/models/spree/channel_spec.rb` — `default` scope; `preferred_stock_location_id` FK; `SingleStoreResource` scoping
- [x] T021 `spree/core/spec/models/spree/order_routing_rule_spec.rb` — STI polymorphism (built-in subclasses instantiated correctly); `acts_as_list` position; `rank` raises `NotImplementedError` on base
- [x] T022 `spree/core/spec/models/spree/order_routing/strategy/rules_spec.rb` — reducer: first non-tie wins; tie → next rule; all-tie → default location → ID
- [x] T023 `spree/api/spec/integration/spree/api/v3/admin/channels_spec.rb` — CRUD; store scoping; ordering rules returned

### Type Pipeline

- [x] T024 `bundle exec rake typelizer:generate` — `AdminChannel`, `AdminOrderRoutingRule` types generated
- [x] T025 `cd packages/sdk && pnpm generate:zod`
- [x] T026 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T027 [US1/US2] `packages/dashboard/src/routes/_authenticated/$storeId/settings/channels.tsx` — channel list + create/edit `<Sheet>`; routing rules editor with drag-to-reorder (dnd-kit `verticalListSortingStrategy`); rule type `<Select>` from registry; `preferred_stock_location_id` `<Combobox>`
- [x] T028 [US1] `packages/dashboard/src/hooks/use-channels.ts` — TanStack Query wrappers for channels and routing rules
- [x] T029 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.channels.*` and `admin.orderRoutingRules.*`
- [x] T030 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [x] T031 `packages/dashboard/e2e/channels.spec.ts` — create channel → add PreferredLocation rule → reorder rules → verify position persists
- [x] T032 `packages/dashboard/e2e/channels-settings.spec.ts` — settings page: channels list; edit channel name + preferred location
- [x] T033 Run `pnpm test:e2e` ✅

**Checkpoint**: all integration tests pass ✅; routing uses channel's rules in position order ✅; `Strategy::Legacy` used as fallback for unconfigured stores ✅

---

## Phase 2: 6.0 — Catalog / Company (PENDING)

Per `6.0-channels-catalogs-b2b.md`:

- [ ] T034 `Spree::Catalog` model — per-channel product publication visibility; `CatalogProduct` join
- [ ] T035 `Spree::Company` + `CompanyLocation` + `CompanyContact` — B2B organizational models
- [ ] T036 Company-aware routing rule subclasses (e.g., `CompanyDefaultLocation` — routes B2B orders to the company's preferred location)
- [ ] T037 Channel gains `company_id` or `catalog_id` FK for B2B context
- [ ] T038 SPA: Catalog management UI; Company management UI

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No dedicated `OrderRoutingRulesController` — rules managed via Channels controller | Low | Intentional: rules are always in the context of a channel; a standalone rules controller would not be useful without channel context |
| `Strategy::Legacy` remains the default for stores that existed before 5.5 | Low | Document upgrade path clearly: run seed task to create a default Channel + three built-in rules; then switch to `Strategy::Rules` |
| Phase 2 (Catalog/Company) blocked pending `6.0-channels-catalogs-b2b.md` | High | T034–T038 above; not a gap in Phase 1 — all Phase 1 work is complete |
