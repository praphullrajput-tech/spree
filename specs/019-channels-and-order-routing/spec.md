# Feature Specification: Channels & Order Routing

**Feature Branch**: `019-channels-and-order-routing`

**Created**: 2026-08-24

**Status**: migrated

**Input**: Reverse-engineered from shipped code (brownfield migration). Phase 1 of `docs/plans/6.0-order-routing.md` and Phase 1/1.5 of `docs/plans/6.0-channels-catalogs-b2b.md`, both shipped in 5.5/5.6.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merchant configures multiple distribution channels (Priority: P1)

A merchant running an online storefront plus a POS terminal and a wholesale
portal needs each surface tracked separately: which products are listed
where, which orders came from which surface, and (for wholesale) different
storefront access rules.

**Why this priority**: Without Channel as a first-class model, `Order.channel`
is a free-text string with no queryability, no per-surface product
visibility, and no per-surface access control — the foundational gap the
whole feature closes.

**Independent Test**: Create a Channel via `POST /api/v3/admin/channels`,
publish a product to it via `POST /api/v3/admin/channels/:id/add_products`,
and confirm an Order created against that channel persists `channel_id`.

**Acceptance Scenarios**:

1. **Given** a store with no channels, **When** the store is created, **Then** an "Online Store" channel is auto-created and marked `default: true`.
2. **Given** an existing default channel, **When** an admin creates a second channel and sets `default: true` on it, **Then** the previous default is demoted so exactly one channel per store remains default.
3. **Given** a channel that is the store's only/default channel, **When** an admin attempts to delete it, **Then** the deletion is rejected (`cannot_delete_default_channel`).
4. **Given** a product owned by the current store, **When** an admin calls `add_products` on one of the store's channels, **Then** a `Spree::ProductPublication` row is upserted and the product's search index is re-enqueued.

---

### User Story 2 - Store routes each order to the right stock location automatically (Priority: P1)

A merchant with multiple stock locations wants orders fulfilled from the
location the merchant prefers (e.g. closest to the customer, or explicitly
pinned), without hand-coding location selection or monkey-patching the
stock coordinator.

**Why this priority**: This is the direct replacement for the implicit,
unswappable `Spree::Stock::Coordinator` + `Prioritizer` selection logic —
the core problem statement of `docs/plans/6.0-order-routing.md`.

**Independent Test**: Create an order whose `preferred_stock_location_id` is
set to a location that stocks all requested variants; confirm
`order.order_routing_strategy.for_allocation` returns packages only from
that location (or spills to the next-ranked location when it can't cover
the full cart).

**Acceptance Scenarios**:

1. **Given** an order with `preferred_stock_location_id` set, **When** allocation runs, **Then** `Rules::PreferredLocation` ranks that location at `0` and all others abstain (`nil`), so it wins the reducer outright.
2. **Given** no preferred location and two locations each covering different subsets of the cart, **When** allocation runs, **Then** `Rules::MinimizeSplits` ranks the location covering the most line items best, and the reducer carries ties to `Rules::DefaultLocation`.
3. **Given** a tie survives every rule, **When** the reducer runs out of rules, **Then** it picks `StockLocation.default`, then lowest `id`.
4. **Given** a location can't cover the whole cart, **When** `for_allocation` runs, **Then** `Spree::Stock::Prioritizer` spills uncovered units to the next-ranked location's package (multi-location split, no regression vs. pre-5.5 Coordinator).
5. **Given** a store or channel sets `preferred_order_routing_strategy` to `'Spree::OrderRouting::Strategy::Legacy'`, **When** allocation runs, **Then** it delegates entirely to `Spree::Stock::Coordinator` (opt-out escape hatch for 5.4 customizers).

---

### User Story 3 - Merchant gates a wholesale channel behind login (Priority: P2)

A merchant wants a public B2C channel and a login-required wholesale
channel on the same store, each with its own pricing visibility and
guest-checkout policy, enforced server-side rather than only in the
storefront UI.

**Why this priority**: Closes the "explicit deny anonymous" gap the product
visibility model lacked — without it, any client hitting the Store API
directly bypasses a storefront-only gate.

**Independent Test**: Set a channel's `storefront_access` to
`login_required`, hit any gated Store API endpoint without a JWT via
`X-Spree-Channel: <that channel>`, and confirm `401`.

**Acceptance Scenarios**:

1. **Given** a channel with `storefront_access: 'login_required'`, **When** a guest (no customer JWT) requests a gated Store API endpoint, **Then** the request is rejected with `401` before any product/catalog work runs.
2. **Given** a channel with `storefront_access: 'prices_hidden'`, **When** a guest requests a priced resource (product, cart, order, line item), **Then** every money field serializes as `null`; a logged-in customer sees prices normally.
3. **Given** a channel's `storefront_access` preference is unset (`nil`), **When** resolved, **Then** it falls back to the store's `preferred_storefront_access` (default `public`).
4. **Given** a channel resolves to `prices_hidden` OR its `guest_checkout` resolves to `false`, **When** a guest attempts to complete an order on that channel, **Then** `Order#guest_checkout_disallowed?` returns `true` and checkout is blocked.
5. **Given** an endpoint explicitly opts out via `allow_guest_storefront_access!` (sign-in, password reset, pre-login reference data), **When** a guest requests it on a `login_required` channel, **Then** it is still reachable.

---

### Edge Cases

- What happens when an Order's channel is destroyed? `Channel has_many :orders, dependent: :nullify` — orders survive with `channel_id: nil`, and `Order#ensure_channel_presence` re-assigns `store.default_channel` on next validation.
- What happens when no location stocks any requested variant? `eligible_locations` returns empty, `for_allocation` returns `[]`, and today's pre-existing "no shipments created" failure mode applies unchanged (graceful `on_hold` handling is deferred to 6.0 Phase 4).
- What happens when a `type` value is persisted on `OrderRoutingRule` that isn't in the `Spree.order_routing.rules` registry (e.g. after a plugin is uninstalled)? The record fails `type_must_be_registered` validation on next save; existing unsaved-but-persisted rows are simply skipped by nothing extra — the registry is validated at write time, not read time, so a stale row still loads and dispatches via STI.
- What happens when a strategy class is unregistered or a stale preference value no longer resolves? `Order#order_routing_strategy` falls back to the default `Rules` strategy rather than raising (per `HasStrategyPreference` validation + resolver design).
- What happens when a channel's `store_id` and the rule's `store_id` disagree? `OrderRoutingRule#channel_belongs_to_store` validation rejects it.
- What happens to reservations while a routing decision is made? Not addressed in this phase — `Spree::StockReservations::Reserve#select_stock_item` picks a location independently of the routing strategy (documented gap, Phase 3 of the order-routing plan).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `Spree::Channel` model, `belongs_to :store`, with a unique `code` per store and exactly one `default: true` channel per store at all times.
- **FR-002**: System MUST auto-create a default "Online Store" channel when a Store is created, and auto-promote the first channel created on a store to default.
- **FR-003**: System MUST prevent deletion of a store's default channel.
- **FR-004**: System MUST provide `Channel#add_products` / `#remove_products` as the canonical bulk publish/unpublish API, upserting/destroying `Spree::ProductPublication` rows and re-enqueuing search indexing.
- **FR-005**: System MUST expose Admin API endpoints for Channel CRUD plus `add_products` / `remove_products` action endpoints, scoped to the current store and to products the caller can update.
- **FR-006**: System MUST resolve the active channel per Store API request from the `X-Spree-Channel` header (matching `code` or a prefixed `ch_` ID), falling back to the store's default channel.
- **FR-007**: System MUST provide a two-tier order-routing extension: a registered `Strategy::Base` subclass (algorithm) selected per Store (with optional per-Channel override), and STI `OrderRoutingRule` subclasses (signals) walked by the default `Rules` strategy.
- **FR-008**: System MUST ship exactly one concrete strategy in core, `Strategy::Rules`, plus the `Strategy::Legacy` escape hatch that delegates to the pre-5.5 `Stock::Coordinator`.
- **FR-009**: System MUST seed every Channel with three default `OrderRoutingRule` rows on creation: `PreferredLocation` (position 1), `MinimizeSplits` (position 2), `DefaultLocation` (position 3).
- **FR-010**: System MUST reduce rule rankings via "first non-tie wins": drop abstentions (`rank: nil`), take the lowest-rank location(s) per rule, return immediately on a unique winner, otherwise carry the tied set to the next rule; when all rules are exhausted, prefer `StockLocation.default` then lowest `id`.
- **FR-011**: System MUST validate that a rule's persisted `type` is present in the `Spree.order_routing.rules` registry and that a strategy preference (Store or Channel) is present in the `Spree.order_routing.strategies` registry, allowing blank values to fall back through the resolution chain.
- **FR-012**: System MUST validate that every `OrderRoutingRule`'s `channel.store_id` matches its own `store_id`.
- **FR-013**: System MUST resolve `Order#order_routing_strategy` as channel preference → store preference → default `Rules`, and never instantiate an unregistered class.
- **FR-014**: System MUST provide `Order#inferred_preferred_stock_location_id` as a cascade: explicit `preferred_stock_location_id` → (Phase 2 inputs not yet built) → present-day terminal fallback.
- **FR-015**: System MUST provide a per-Channel storefront access posture (`public` / `prices_hidden` / `login_required`) that falls back to a per-Store default (`public`), enforced in the v3 Store API (not the storefront layer).
- **FR-016**: System MUST return `401` for any gated Store API endpoint requested by a guest (no authenticated customer) on a `login_required` channel, except endpoints explicitly opted out via `allow_guest_storefront_access!`.
- **FR-017**: System MUST null every money-serialized field for guest requests on a `prices_hidden` channel, while serializing normally for authenticated customers.
- **FR-018**: System MUST provide a per-Channel `guest_checkout` override (`nil` → store fallback) and reject guest order completion whenever the resolved value is `false` or the channel hides prices.

### Key Entities *(include if feature involves data)*

- **Spree::Channel**: Distribution surface within a Store (online, POS, wholesale). Attributes: `name`, `code`, `active`, `default`. Preferences: `order_routing_strategy`, `storefront_access`, `guest_checkout` (all nullable, store-fallback). Relationships: `belongs_to :store`; `has_many :orders`, `:order_routing_rules`, `:publications` (`Spree::ProductPublication`), `:products through: :publications`.
- **Spree::OrderRoutingRule**: STI base for a routing "signal." Attributes: `type`, `position` (`acts_as_list scope: :channel_id`), `active`, `preferences` (typed via subclass `preference` declarations). Relationships: `belongs_to :store`, `belongs_to :channel`. Contract: `#rank(order, locations) → Array<LocationRanking>` (`LocationRanking = Struct(:location, :rank)`, `rank: nil` = abstain).
- **Spree::OrderRouting::Strategy::Base**: Abstract four-method contract (`for_allocation`, `for_sale`, `for_release`, `for_cancellation`) — no default implementations, total-replacement subclassing.
- **Spree::OrderRouting::Strategy::Rules**: The one concrete core strategy. Walks `channel.order_routing_rules.active.ordered`, ranks all eligible locations via `Reducer#rank_all`, packs each location, hands packages to `Spree::Stock::Prioritizer`, attaches shipping rate estimates.
- **Spree::OrderRouting::Strategy::Legacy**: Thin wrapper delegating to `Spree::Stock::Coordinator` — 5.x opt-out escape hatch, dropped in 6.0.
- **Spree::OrderRouting::Strategy::Reducer**: Stateless ranking engine — `pick(locations)` (single winner) and `rank_all(locations)` (full best-first ordering for multi-location split fallback).

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Channel` + `Spree::Channel::Gating` concern, `Spree::OrderRoutingRule` STI base + 3 built-in rule subclasses, `Spree::OrderRouting::Strategy::{Base,Rules,Legacy,Reducer}`, `Spree::OrderRouting::HasStrategyPreference` concern, `Order` gains `channel_id`/`preferred_stock_location_id` FKs + resolver methods, `Spree::ProductPublication` model, `Product` single-store ownership |
| `spree/api` (Store/Admin API v3) | Yes | `Admin::ChannelsController` (CRUD + `add_products`/`remove_products`), `ChannelSerializer` + `Admin::ChannelSerializer`, `ChannelResolution` concern (`X-Spree-Channel` header), `StorefrontGating` concern (401 gate + price-nulling), Admin Order endpoint exposes `preferred_stock_location_id` |
| `packages/dashboard` (admin SPA) | Yes | Settings → "Sales channels" route/table (`settings/channels.tsx`, `tables/channels.tsx`), `use-channels.ts` hook, `channel.ts` schema, `<ChannelSelect>` component, channel-scoped rule editors in promotion/price-list rule pickers |
| `packages/dashboard-ui` / `dashboard-core` | No | No new headless primitives or registries specific to this feature beyond the standard table registration |
| `packages/sdk` / `packages/admin-sdk` | Yes | Regenerated `Channel` types (`admin-sdk/src/types/generated/Channel.ts`) from the serializer changes |
| `docs/plans/` | Yes | `docs/plans/6.0-order-routing.md` (Phase 1 shipped 5.5) and `docs/plans/6.0-channels-catalogs-b2b.md` (Phase 1 shipped 5.5, gating Phase 1.5 shipped 5.6) already govern this area — this spec documents what those plans record as shipped, it does not introduce a new plan |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints**:
  - `GET/POST/PATCH/DELETE /api/v3/admin/channels[/:id]`
  - `POST /api/v3/admin/channels/:id/add_products` (body: `product_ids`, optional `published_at`/`unpublished_at`)
  - `POST /api/v3/admin/channels/:id/remove_products` (body: `product_ids`)
  - `PATCH /api/v3/admin/orders/:id` gains `preferred_stock_location_id`
- **Serializer fields (read)**: Store `ChannelSerializer` — `name`, `code`, `active`, `default`. Admin `ChannelSerializer` extends it with `preferred_order_routing_strategy`, `preferred_storefront_access`, `preferred_guest_checkout`, `created_at`, `updated_at`. Admin controller's `permitted_params` accepts exactly `name, code, active, default, preferred_order_routing_strategy` (read/write symmetry note: `preferred_storefront_access` / `preferred_guest_checkout` are exposed on read but not yet in `permitted_params` — see Migration Notes gap below).
- **Auth**: Admin API — secret key + scopes or JWT + CanCanCan (`Admin::ChannelsController` uses standard `ResourceController` auth). Store API gating (`StorefrontGating`) applies to publishable-key/guest-token/customer-JWT requests on Store API controllers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A store with N stock locations and a configured `preferred_stock_location_id` on an order always allocates from that location when it covers the cart — zero manual coordinator monkey-patches required.
- **SC-002**: Multi-location split behavior is unchanged from the pre-5.5 `Stock::Coordinator` baseline for existing merchants (verified by the plan's parity spec running shared examples against `Legacy` and `Rules`).
- **SC-003**: A `login_required` channel returns `401` for 100% of gated guest requests, with zero product/catalog work performed on the rejected path.
- **SC-004**: A `prices_hidden` channel nulls 100% of money-typed serializer fields for guest requests across product, cart, order, and line-item serializers.
- **SC-005**: Plugin authors can add a new routing signal by subclassing `Spree::OrderRoutingRule` and registering it, without modifying `Strategy::Rules` or `Reducer` (`Constraints on Current Work` in the plan: "Don't add `if rule.is_a?(Foo)` branches").

## Assumptions

- This spec documents Phase 1 (`6.0-order-routing.md`) and Phase 1 + Phase 1.5 (`6.0-channels-catalogs-b2b.md`) as shipped in 5.5/5.6 — it is a reverse-engineered record, not a forward-looking design.
- Catalog, Company/CompanyLocation/CompanyContact, and the reservation/routing handoff (Phase 3 of order-routing) are real gaps in the current codebase, not omissions from this spec — they are out of scope by design (see Migration Notes).
- `Spree::Current.channel` is assumed to be set by the API layer (`ChannelResolution` concern) for request-scoped code; jobs/rake tasks fall back to a legacy-column path where documented in the plan.
- The existing `docs/plans/6.0-order-routing.md` and `docs/plans/6.0-channels-catalogs-b2b.md` remain the authoritative design documents; this spec does not supersede them, per Constitution Principle VI.

## Migration Notes

**This is a two-tier pluggable-strategy extension point**, not a single
algorithm. The two axes exist for genuinely different extension needs and
must not be collapsed into one:

1. **Strategy (`Spree::OrderRouting::Strategy::Base`)** — a complete,
   self-contained allocation *algorithm*. Four required methods
   (`for_allocation`, `for_sale`, `for_release`, `for_cancellation`), no
   default implementations — a subclass either implements all four or
   raises `NotImplementedError`. Selected per Store (`preferred_order_routing_strategy`)
   with an optional per-Channel override; validated against the
   `Spree.order_routing.strategies` allowlist registry, never selected by
   loose `is_a?` checks. This tier is for a different *shape* of decision
   process entirely (an OMS delegator, an ML ranking model, a solver) — rare
   in practice, a handful of plugins ever.
2. **Rule (`Spree::OrderRoutingRule` STI subclass)** — a single ranking
   *signal* consumed by the one concrete core strategy, `Strategy::Rules`.
   Implements `#rank(order, locations) → Array<LocationRanking>` only.
   Persists via Rails STI (`type` column); the `Spree.order_routing.rules`
   registry is the curated allowlist for admin pickers and the `type`
   inclusion validation, not the dispatch mechanism (STI already dispatches
   via the `type` column read). Plugins add new *signals* — a metafield
   check, a day-of-week rule, a proximity rule — as ordinary
   `acts_as_list`-scoped STI rows without ever touching `Strategy::Rules` or
   `Reducer`. This is the dominant, expected extension path.

Both extension points are validated at write-time (model validations reject
an unregistered class name) and read gracefully at run-time (an
unregistered/stale persisted value falls back to the default `Rules`
strategy rather than raising) — this asymmetry is intentional per the
plan's Resolved Questions.

**Phase 2 (Catalog, Company/CompanyLocation/CompanyContact) is NOT built.**
Per `docs/plans/6.0-channels-catalogs-b2b.md`, only Channel +
ProductPublication + single-store Product (Phase 1, shipped 5.5) and the
storefront access/guest-checkout gating (Phase 1.5, shipped 5.6) exist
today. Confirmed absent from the codebase during this migration:

- No `Spree::Catalog`, `Spree::CatalogProduct`, `Spree::CatalogAssignment` models or `spree_catalogs`/`spree_catalog_products`/`spree_catalog_assignments` tables.
- No `Spree::Company`, `Spree::CompanyLocation`, `Spree::CompanyContact` models or corresponding tables; `Order.company_location` FK does not exist.
- No `Channel.default_catalog_id` column.
- `Order#inferred_preferred_stock_location_id`'s cascade (`company_location&.preferred_stock_location_id`) inputs beyond the direct `preferred_stock_location_id` column are Phase 2 placeholders in the plan text — verify against the live `order.rb` cascade before building against it, since the referenced `company_location` association does not exist yet.

This confirms the explicit feature-list exclusion: **B2B Company/Catalog work is out of scope for this migrated spec** and belongs to a future `020`-series (or later) feature once `6.0-channels-catalogs-b2b.md` Phase 2 ships.

**Other gaps surfaced during reverse-engineering** (not blocking, flagged for awareness):

- Admin `ChannelsController#permitted_params` does not yet include `preferred_storefront_access` / `preferred_guest_checkout`, even though the Admin serializer exposes both on read — a read/write asymmetry relative to Constitution Principle III that should be closed when the Channels settings page grows storefront-access controls.
- Reservation/routing handoff (Phase 3 of `6.0-order-routing.md`) is unbuilt: `Spree::StockReservations::Reserve#select_stock_item` still picks a location independently of the routing strategy — a documented, accepted gap in the shipped code, not a regression.
