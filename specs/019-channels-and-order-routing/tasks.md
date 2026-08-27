---

description: "Task list for Channels & Order Routing (reverse-engineered, migrated)"
---

# Tasks: Channels & Order Routing

**Input**: Design documents from `specs/019-channels-and-order-routing/`

**Prerequisites**: plan.md, spec.md

**Tests**: Included — RSpec + controller/integration specs already exist for the shipped feature.

**Organization**: Tasks are grouped by user story, matching spec.md. All tasks below reflect work already merged (Phase 1 of `docs/plans/6.0-order-routing.md`, Phase 1 + 1.5 of `docs/plans/6.0-channels-catalogs-b2b.md`) and are marked complete as part of this brownfield migration.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Ran in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core` and `spree/api` build/test cleanly: `bundle exec rspec` in each gem
- [x] T002 [P] Confirm `packages/dashboard` typechecks/lints: `pnpm typecheck && pnpm lint`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T003 [spree/core] Migration `spree/core/db/migrate/20260508204040_create_spree_channels.rb` — `spree_channels` table (`store_id`, `name`, `code`, `active`)
- [x] T004 [spree/core] Migration `spree/core/db/migrate/20260602000001_add_default_to_spree_channels.rb` — `default` boolean + partial unique index `(store_id) WHERE default = TRUE`
- [x] T005 [spree/core] Migration adding `channel_id` FK + `preferred_stock_location_id` FK to `spree_orders`
- [x] T006 [spree/core] Migration `spree_order_routing_rules` table — `store_id`, `channel_id`, `type` (STI), `position`, `active`, `preferences` text column, indexes on `(channel_id, position)` and `(channel_id, active, position)`
- [x] T007 [spree/core] Migration `spree/core/db/migrate/20260601000001_create_spree_product_publications.rb` — `spree_product_publications` table + unique index `(product_id, channel_id)`
- [x] T008 [spree/core] Model `spree/core/app/models/spree/channel.rb` — `Spree.base_class`, `has_prefix_id :ch`, includes `SingleStoreResource`, `Metafields`, `Metadata`, `OrderRouting::HasStrategyPreference`, `Channel::Gating`
- [x] T009 [spree/core] Concern `spree/core/app/models/spree/channel/gating.rb` — `storefront_access` + `guest_checkout` preferences, `resolved_storefront_access`/`resolved_guest_checkout`/`storefront_prices_hidden?`/`storefront_login_required?`
- [x] T010 [spree/core] Model `spree/core/app/models/spree/order_routing_rule.rb` — STI base, `LocationRanking` struct, `has_prefix_id :orule`, `acts_as_list scope: :channel_id`, `type_must_be_registered` + `channel_belongs_to_store` validations
- [x] T011 [spree/core] Concern `spree/core/app/models/spree/order_routing/has_strategy_preference.rb` — shared strategy-registry validation for `Store` + `Channel`
- [x] T012 [spree/api] Ransack allowlist on `Spree::Channel` (`name code active default store_id`) and `Spree::OrderRoutingRule` (`type position active store_id channel_id`)
- [x] T013 [packages/dashboard] i18next keys for Sales Channels settings page in `packages/dashboard/src/locales/en.json` (+ other locale files)

**Checkpoint**: Foundation complete — Channel + OrderRoutingRule schema and models exist.

---

## Phase 3: User Story 1 - Merchant configures multiple distribution channels (Priority: P1) 🎯 MVP

**Goal**: Admins can CRUD channels and publish/unpublish products to them via the Admin API and dashboard.

**Independent Test**: `POST /api/v3/admin/channels` → `POST /api/v3/admin/channels/:id/add_products` → confirm `Spree::ProductPublication` row exists and product search index re-enqueued.

### Tests for User Story 1

- [x] T014 [P] [US1] RSpec model spec `spree/core/spec/models/spree/channel_spec.rb` (default promotion/demotion, `can_be_deleted?`, `add_products`/`remove_products` idempotency)
- [x] T015 [P] [US1] Controller spec `spree/api/spec/controllers/spree/api/v3/admin/channels_controller_spec.rb`
- [x] T016 [P] [US1] Integration spec `spree/api/spec/integration/spree/api/v3/admin/channels_spec.rb` (happy path + 422s, generates OpenAPI examples)
- [x] T017 [P] [US1] Concern spec `spree/api/spec/controllers/concerns/spree/api/v3/channel_resolution_spec.rb`

### Implementation for User Story 1

- [x] T018 [P] [US1] `Spree::Channel#add_products` / `#remove_products` bulk upsert/destroy with idempotent re-publish semantics (`spree/core/app/models/spree/channel.rb`)
- [x] T019 [US1] `Spree::Channel` default-promotion/demotion callbacks (`promote_first_channel_to_default`, `demote_other_defaults`, `ensure_not_default`)
- [x] T020 [US1] `after_create :ensure_default_order_routing_rules` seeding the 3 built-in rules on every new channel
- [x] T021 [US1] `Spree::Api::V3::Admin::ChannelsController` — CRUD + `add_products`/`remove_products` actions, store-scoped, product-permission-scoped (`spree/api/app/controllers/spree/api/v3/admin/channels_controller.rb`)
- [x] T022 [US1] `Spree::Api::V3::ChannelSerializer` + `Admin::ChannelSerializer` (`spree/api/app/serializers/spree/api/v3/{,admin/}channel_serializer.rb`)
- [x] T023 [US1] `Spree::Api::V3::ChannelResolution` concern — `X-Spree-Channel` header resolution into `Spree::Current.channel` (`spree/api/app/controllers/concerns/spree/api/v3/channel_resolution.rb`)
- [x] T024 [US1] Type-generation pipeline run for `Channel` serializer changes (`admin-sdk/src/types/generated/Channel.ts`)
- [x] T025 [US1] Dashboard Settings → Sales Channels page + table + hook + schema + select component (`packages/dashboard/src/{routes/_authenticated/$storeId/settings/channels.tsx,tables/channels.tsx,hooks/use-channels.ts,schemas/channel.ts,components/spree/channel-select.tsx}`)

**Checkpoint**: User Story 1 fully functional — channels CRUD + product publishing work end to end.

---

## Phase 4: User Story 2 - Store routes each order to the right stock location automatically (Priority: P1)

**Goal**: Orders allocate stock via the `Rules` strategy walking channel-scoped `OrderRoutingRule` rows, with a `Legacy` escape hatch for 5.4 customizers.

**Independent Test**: Set `preferred_stock_location_id` on an order covering all requested variants at one location; confirm `for_allocation` returns packages only from that location.

### Tests for User Story 2

- [x] T026 [P] [US2] RSpec spec for `Spree::OrderRoutingRule` STI base (registration validation, channel/store consistency)
- [x] T027 [P] [US2] RSpec specs per built-in rule: `preferred_location_spec.rb`, `minimize_splits_spec.rb`, `default_location_spec.rb`
- [x] T028 [P] [US2] RSpec spec for `Spree::OrderRouting::Strategy::Reducer` (`pick`, `rank_all`, tie-carrying, default-location fallback)
- [x] T029 [P] [US2] Parity spec running shared examples against `Strategy::Legacy` and `Strategy::Rules` (single-location coverage, multi-location splits, backorder behavior, `track_inventory: false`)

### Implementation for User Story 2

- [x] T030 [P] [US2] `Spree::OrderRouting::Strategy::Base` — four-method `NotImplementedError` contract (`strategy/base.rb`)
- [x] T031 [US2] `Spree::OrderRouting::Strategy::Rules` — `eligible_locations`, `Reducer#rank_all`, `build_packages`, `Prioritizer#prioritized_packages`, `estimate_rates` (`strategy/rules.rb`)
- [x] T032 [US2] `Spree::OrderRouting::Strategy::Legacy` — delegates to `Spree::Stock::Coordinator` (`strategy/legacy.rb`)
- [x] T033 [US2] `Spree::OrderRouting::Strategy::Reducer` — first-non-tie-wins reduction (`strategy/reducer.rb`)
- [x] T034 [P] [US2] `Rules::PreferredLocation`, `Rules::MinimizeSplits`, `Rules::DefaultLocation` built-in STI subclasses
- [x] T035 [US2] `Order` gains `channel`/`preferred_stock_location` associations, `ensure_channel_presence` before_validation, `order_routing_strategy` resolver, `inferred_preferred_stock_location_id` cascade
- [x] T036 [US2] Replace `Order#create_proposed_shipments`'s direct `Stock::Coordinator` call with `order_routing_strategy.for_allocation`
- [x] T037 [US2] Admin Order API exposes `preferred_stock_location_id` on read/write
- [x] T038 [US2] `Spree.order_routing.rules` / `Spree.order_routing.strategies` registries registered in `spree/core/lib/spree/core.rb` (core built-ins registered at boot)

**Checkpoint**: User Stories 1 and 2 both fully functional independently.

---

## Phase 5: User Story 3 - Merchant gates a wholesale channel behind login (Priority: P2)

**Goal**: Channel-level storefront access posture and guest-checkout policy, enforced in the v3 Store API.

**Independent Test**: Set `storefront_access: 'login_required'` on a channel, hit a gated Store API endpoint as a guest via `X-Spree-Channel`, confirm `401`.

### Tests for User Story 3

- [x] T039 [P] [US3] RSpec spec for `Spree::Channel::Gating` concern (`resolved_storefront_access`, `resolved_guest_checkout`, store-fallback behavior)
- [x] T040 [P] [US3] Controller/request specs for `StorefrontGating` — 401 on `login_required`, price-nulling on `prices_hidden`, `allow_guest_storefront_access!` opt-out
- [x] T041 [P] [US3] Spec for `Order#guest_checkout_disallowed?` covering the `prices_hidden` ⇒ disallow-guest-checkout implication

### Implementation for User Story 3

- [x] T042 [US3] `Spree::Channel::Gating` concern — `storefront_access`/`guest_checkout` preferences + resolution methods (`spree/core/app/models/spree/channel/gating.rb`)
- [x] T043 [US3] `Spree::Store` gains `preferred_storefront_access` (default `public`) and retains `preferred_guest_checkout` as the channel fallback
- [x] T044 [US3] `Spree::Api::V3::StorefrontGating` concern — `before_action` 401 guard + `hide_prices?` serializer flag injection (`spree/api/app/controllers/concerns/spree/api/v3/storefront_gating.rb`)
- [x] T045 [US3] `BaseSerializer#price_for`/`price_in`/`money_attributes` honor the `hide_prices` serializer param across product, cart, order, line-item serializers
- [x] T046 [US3] `Order#guest_checkout_disallowed?` enforced in `Spree::Carts::Complete`, covering controller/payment-session/webhook completion paths
- [x] T047 [US3] Public endpoints (sign-in, register, password reset, pre-login reference data) opt out via `allow_guest_storefront_access!`

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T048 [P] `docs/plans/6.0-order-routing.md` and `docs/plans/6.0-channels-catalogs-b2b.md` updated to reflect Phase 1/1.5 shipped status
- [x] T049 Full backend suite: `spree/core` + `spree/api` `bundle exec rspec`
- [x] T050 Full frontend suite: `pnpm typecheck && pnpm lint && pnpm test` at workspace root
- [ ] T051 [P] Playwright e2e for the Sales Channels settings page (`packages/dashboard/e2e/channels.spec.ts`) — **not found in the codebase; gap, not yet done**
- [x] T052 Verify locale files have matching keys across `packages/dashboard/src/locales/` for channel/routing strings

---

## Dependencies & Execution Order

Standard: Setup → Foundational → User Stories (US1/US2 can proceed in parallel once Foundational is done; US3 depends only on Foundational, not on US1/US2) → Polish.

## Notes

- This tasks.md is a **retrospective record** of already-shipped work (brownfield migration), not a forward plan — every task reflects code found in the repository during this migration pass.
- T051 (Playwright e2e for Sales Channels) is left unchecked — no `channels.spec.ts` was found under `packages/dashboard/e2e/` during this migration. Flagged as a real coverage gap, not a documentation oversight.
- Phase 2 work (Catalog, Company, reservation/routing handoff) is intentionally excluded from this task list — see spec.md "Migration Notes."
