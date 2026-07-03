# Feature Specification: Order Routing Rules

**Feature Branch**: `main` (Phase 1 shipped in 5.5; Phase 2+ pending in 6.0)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: `docs/plans/6.0-order-routing.md`

---

## User Scenarios & Testing

### User Story 1 — Configure Routing Rules for a Store (Priority: P1)

A merchant admin configures the order routing strategy for their store. The default strategy (`Rules`) walks a list of `OrderRoutingRule` rows in priority order and picks the best-matching stock location. Built-in rules: `PreferredLocation`, `MinimizeSplits`, `DefaultLocation`. Admin can reorder rules by position, configure rule preferences (e.g., which location is "preferred"), or disable rules.

**Why this priority**: Multi-location merchants cannot control stock location selection without configurable routing. Today's behavior (insertion order) is effectively random.

**Independent Test**: Admin adds a `PreferredLocation` rule on their Channel's routing strategy with `preferred_stock_location_id: <brooklyn_id>`. When an order is routed, Brooklyn Warehouse is ranked first by that rule. If it has sufficient stock, fulfillment is assigned there.

**Acceptance Scenarios**:

1. **Given** a store with multiple stock locations, **When** admin sets `PreferredLocation` rule with Brooklyn as preferred, **Then** orders route to Brooklyn if it has sufficient stock
2. **Given** two routing rules in position order, **When** the first rule produces a tie, **Then** the second rule breaks the tie (reducer pattern)
3. **Given** all rules produce a tie, **When** routing runs, **Then** the `default: true` stock location is chosen, then by ID
4. **Given** a `MinimizeSplits` rule, **When** all items can ship from one location, **Then** that location is preferred over a split across two
5. **Given** a routing rule, **When** admin reorders it via drag-and-drop, **Then** its `position` is updated and routing uses the new order

---

### User Story 2 — Manage Channels (Priority: P1)

An admin creates and manages `Spree::Channel` records that group orders by sales context (online storefront, POS, wholesale, API). Each channel carries a `preferred_stock_location_id` hint and an associated routing strategy. Orders are tagged with `channel_id` at creation time.

**Why this priority**: Channels are the organizational unit that routing is configured per. Without channels, routing configuration has no multi-context separation.

**Independent Test**: Admin creates a "Wholesale" channel with `preferred_stock_location_id: <warehouse_id>`. When a wholesale order is placed, `order.channel_id` is set to the wholesale channel. The routing strategy for that channel routes to the warehouse first.

**Acceptance Scenarios**:

1. **Given** no channels, **When** admin creates a "Wholesale" channel with a preferred location, **Then** it appears with a prefixed ID (`ch_…`)
2. **Given** a channel, **When** admin sets it as `default: true`, **Then** new orders without an explicit channel are assigned to it
3. **Given** a channel with `preferred_stock_location_id`, **When** an order for that channel is routed, **Then** the `PreferredLocation` rule resolves to that location
4. **Given** multiple channels (online, POS, wholesale), **When** listing channels, **Then** all are returned with their strategy configuration

---

### User Story 3 — Plugin Authors Register Custom Rules (Priority: P2)

A plugin author defines a custom `OrderRoutingRule` STI subclass and registers it via `Spree.order_routing.rules`. The rule appears in the admin UI's rule type picker and participates in the reducer alongside built-in rules.

**Why this priority**: The extension pattern (STI + registry) is the primary customization path for routing. It must be documented and validated.

**Independent Test**: `Spree.order_routing.rules` contains `Spree::OrderRouting::Rules::PreferredLocation`, `MinimizeSplits`, and `DefaultLocation` after initialization. A plugin that adds `AcmeFresh::Routing::RefrigeratedRule` to the registry sees it listed in the admin UI.

**Acceptance Scenarios**:

1. **Given** a plugin defines `AcmeFresh::Routing::RefrigeratedRule < Spree::OrderRoutingRule` and registers it, **When** listing available rule types, **Then** it appears alongside built-in rules
2. **Given** a registered custom rule, **When** admin adds it to their routing configuration, **Then** it participates in the reducer for that store's channel
3. **Given** an unregistered subclass (not in `Spree.order_routing.rules`), **When** admin tries to add it, **Then** it does not appear in the picker (registry is the allowlist)

---

### Edge Cases

- What if a channel has no routing rules configured? → Falls back to `DefaultLocation` rule; picks `StockLocation.default`
- What if no stock location has stock for a line item? → Routing returns an empty result; checkout raises "out of stock" error
- What if a custom strategy returns `nil` for `for_allocation`? → `raise NotImplementedError` — the strategy contract requires all four methods; partial implementation is a coding error
- What if `preferred_stock_location_id` references a soft-deleted location? → Rule abstains (`rank` returns nil) for that location; reducer passes to next rule

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::OrderRouting::Strategy::Base` declares four `NotImplementedError` methods: `for_allocation`, `for_sale`, `for_release`, `for_cancellation` — full-replacement contract, not hook framework
- **FR-002**: `Spree::OrderRouting::Strategy::Rules` is the only concrete strategy in core — walks `Spree::OrderRoutingRule` rows in `position` order via the reducer
- **FR-003**: `Spree::OrderRoutingRule` is the STI base; subclasses registered via `Spree.order_routing.rules`; built-in: `PreferredLocation`, `MinimizeSplits`, `DefaultLocation`
- **FR-004**: Reducer: first non-tie wins; ties carry to the next rule; if all rules tie, pick `default: true` location, then by ID
- **FR-005**: Strategy is chosen per-`Spree::Channel` via a store/channel preference (`strategy_class` column or `preferred_strategy`)
- **FR-006**: `Spree::Channel` has `preferred_stock_location_id`, `default` boolean, `channel_id` set on `Spree::Order` at creation
- **FR-007**: Admin API: full CRUD for channels; full CRUD for routing rules nested under a channel/store
- **FR-008**: All channel IDs prefixed `ch_…`; all routing rule IDs prefixed `orule_…`
- **FR-009**: _(6.0 pending)_ Phase 2: Catalog/Company layers on top of Channel per `6.0-channels-catalogs-b2b.md`

### Key Entities

- **Channel** (`Spree::Channel`): `name`, `default` boolean, `preferred_stock_location_id`, routing strategy preference, `store_id`. Prefix: `ch_`.
- **OrderRoutingRule** (`Spree::OrderRoutingRule`): STI base. `type` (class string), `position` (via `acts_as_list`), preferences JSON. `#rank(order, locations) → Array<LocationRanking>`. Prefix: `orule_`.
- **Built-in rules**: `Spree::OrderRouting::Rules::PreferredLocation`, `::MinimizeSplits`, `::DefaultLocation`.

---

## Backend Requirements

### Data Model

- **Table**: `spree_channels` — `name`, `default`, `preferred_stock_location_id`, `store_id`, `routing_strategy` (strategy class preference), timestamps
- **Table**: `spree_order_routing_rules` — `type` (STI), `position`, preferences JSON column, channel association FK (or store FK), timestamps
- **`acts_as_list`**: on `OrderRoutingRule` for position-based ordering

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/channels` | List channels |
| POST | `/api/v3/admin/channels` | Create channel |
| GET | `/api/v3/admin/channels/:id` | Show channel |
| PATCH | `/api/v3/admin/channels/:id` | Update channel |
| DELETE | `/api/v3/admin/channels/:id` | Delete channel |
| GET | `/api/v3/admin/channels/:id/order_routing_rules` | List rules for channel |
| POST | `/api/v3/admin/channels/:id/order_routing_rules` | Add rule to channel |
| PATCH | `/api/v3/admin/order_routing_rules/:id` | Update rule (preferences, position) |
| DELETE | `/api/v3/admin/order_routing_rules/:id` | Remove rule |
| POST | `/api/v3/admin/order_routing_rules/:id/reposition` | Reposition rule |

### Serializer Fields

**Admin ChannelSerializer**:
- `id` (ch_…), `name`, `default`, `preferred_stock_location_id` (sloc_…), `routing_strategy`, `store_id`, `created_at`, `updated_at`

**Admin OrderRoutingRuleSerializer**:
- `id` (orule_…), `type`, `position`, `preferences` (JSON), `channel_id` (ch_…), `created_at`, `updated_at`

### Authorization

- CanCanCan: `can :manage, Spree::Channel` and `can :manage, Spree::OrderRoutingRule` for admin
- Ransack allowlist: `name`, `default`, `store_id`, `created_at` on channels; `type`, `position` on rules

### i18n (Rails)

- Rule type labels: `spree.order_routing.rule_types.*` per STI class key

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/settings/channels.tsx` — list channels with routing rules editor

### Hooks

- `packages/dashboard/src/hooks/use-channels.ts` — TanStack Query wrappers for channels and routing rules

### Drag-and-Drop Ordering

- Routing rules use `acts_as_list` → drag-and-drop reorder in the rules list within a channel
- `verticalListSortingStrategy` + `PointerSensor(activationConstraint: { distance: 5 })` + `KeyboardSensor`
- On drag end: `PATCH /admin/order_routing_rules/:id/reposition { position: <new_position> }` or update via `position` field

### i18n Keys

Under `admin.channels.*` in all 6 locale files: page title, column headers, default badge, form labels, routing strategy labels, rule type labels, toast messages, empty state.

---

## Success Criteria

- **SC-001**: Admin can create a channel with a `PreferredLocation` rule; orders for that channel route to the preferred location when it has sufficient stock
- **SC-002**: Reordering rules changes their `position` and the routing reducer uses the new order
- **SC-003**: All three built-in rule types are registered in `Spree.order_routing.rules` after initialization
- **SC-004**: `Spree::Order#channel_id` is set at order creation; routing uses the channel's configured rules
- **SC-005**: _(6.0)_ Phase 2: Catalog / Company layers on channels; per-channel catalog visibility

---

## Assumptions

- `Spree::Channel` is the routing configuration unit in 5.5; full multi-channel + catalog separation lands in 6.0 per `6.0-channels-catalogs-b2b.md`
- `OrderRoutingRule` preferences are stored as JSON — each subclass interprets its own keys (e.g., `PreferredLocation` reads `preferred_stock_location_id` from preferences)
- The `Rules` strategy is the default for all new stores; migrating stores get the three built-in rules seeded via a data migration
- Phase 2 (Catalog/Company) is out of scope for this spec; this spec covers Phase 1 (Channel + Rules) only
