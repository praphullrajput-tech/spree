# Feature Specification: Price Lists

**Feature Branch**: `main` (fully shipped)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: None (no plan doc — reverse-engineered from code)

---

## User Scenarios & Testing

### User Story 1 — Manage Price Lists (Priority: P1)

An admin operator creates price lists to offer alternative pricing to specific customer segments (e.g., wholesale, VIP, staff). They can create a price list, set its name and match policy, activate or deactivate it, and schedule it for a date range.

**Why this priority**: Price lists are the foundation of multi-tier pricing. Without them, the system has a single price per currency.

**Independent Test**: Admin creates a price list named "Wholesale" with match policy `all`, activates it, and sees it listed as `active` with a prefixed ID (`pl_…`). Admin then deactivates it and status changes to `inactive`.

**Acceptance Scenarios**:

1. **Given** no price lists exist, **When** admin creates one with `name: "Wholesale"`, **Then** it appears with status `draft` and a prefixed ID
2. **Given** a draft price list, **When** admin activates it, **Then** status transitions to `active`
3. **Given** an active price list, **When** admin deactivates it, **Then** status transitions to `inactive`
4. **Given** a price list with date range `starts_at` / `ends_at`, **When** the current time is within the range, **Then** the price list is eligible for application
5. **Given** a 422 response, **When** `name` is blank, **Then** field-level error appears inline

---

### User Story 2 — Assign Prices to Products (Priority: P1)

An admin operator bulk-assigns prices to products within a price list. They can upload a spreadsheet, use the bulk price editor, or assign prices individually. Products are associated with the price list via `PriceListProduct` membership.

**Why this priority**: A price list without prices is useless. Price assignment is the core value of the feature.

**Independent Test**: Admin opens the "Wholesale" price list, adds 3 products, sets a price for each via the bulk editor, and saves. The price list's `prices_count` shows 3 and each product returns the wholesale price when queried with the price list context.

**Acceptance Scenarios**:

1. **Given** an active price list, **When** admin adds a product via the `prices` action, **Then** the product appears in the price list's product membership
2. **Given** a price list with products, **When** admin uploads a spreadsheet, **Then** prices are bulk-upserted via `upsert_all` for performance
3. **Given** a product belonging to a different store, **When** admin tries to add it to the price list, **Then** a 422 is returned ("foreign membership rejected")
4. **Given** a price list with products, **When** admin removes a product, **Then** its price record is removed and `prices_count` decrements

---

### User Story 3 — Configure Price Rules (Priority: P2)

An admin operator attaches price rules to a price list to define which customers or conditions qualify for the alternate pricing (e.g., customer group membership, order total threshold). The match policy (`all`/`any`) determines whether all rules or any rule must match.

**Why this priority**: Without rules, price lists apply universally. Rules make the pricing contextual and accurate.

**Independent Test**: Admin adds a `CustomerGroup` rule to the "Wholesale" price list requiring `match_policy: all`. Only customers in the "Wholesale" group see the alternate prices.

**Acceptance Scenarios**:

1. **Given** a price list, **When** admin adds a price rule via the nested form, **Then** the rule is saved and returned in the `price_rules` array on the serializer
2. **Given** a price list with `rules_match_policy: "all"`, **When** a customer matches all rules, **Then** the price list is applied
3. **Given** a price list with `rules_match_policy: "any"`, **When** a customer matches at least one rule, **Then** the price list is applied
4. **Given** a rule deletion, **When** admin removes a rule, **Then** it is destroyed and the price list's `rules_match_policy` check is re-evaluated

---

### Edge Cases

- What if a price list has no rules? → Applied universally (all customers qualify unless filtered elsewhere)
- What if two price lists are active simultaneously for the same product? → Priority/conflict resolution is handled by the pricing engine (outside this feature's scope)
- What if `starts_at` is in the future? → Price list is `scheduled` state; prices not applied until `starts_at` passes
- What if a bulk price import contains invalid rows? → Valid rows are upserted; invalid rows surface errors per-row

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::PriceList` must have a state machine with states: `draft`, `active`, `inactive`, `scheduled`
- **FR-002**: Match policies: `all` (all rules must match), `any` (any rule must match)
- **FR-003**: Price lists must be store-scoped (`belongs_to :store`)
- **FR-004**: Admin API must expose `activate` and `deactivate` custom actions
- **FR-005**: Admin API must expose a `prices` action for product price assignment (bulk upsert via `upsert_all`)
- **FR-006**: Admin API must expose a `price_rule_types` action returning available rule class names
- **FR-007**: Price lists support date-range scheduling via `starts_at` / `ends_at` columns
- **FR-008**: Price list membership must reject products from a different store (foreign membership guard)
- **FR-009**: `PriceRule` subtypes are registered via `Spree.pricing.rules` (plugin-registry pattern) — not hardcoded
- **FR-010**: All IDs in API responses must be prefixed (`pl_…` for price lists)
- **FR-011**: No store API surface — price lists are admin-managed only; pricing is applied via the pricing engine, not directly consumed by storefronts
- **FR-012**: Price lists support nested `price_rules` via `accepts_nested_attributes_for`

### Key Entities

- **PriceList**: Alternate price schedule for a customer segment. Attributes: `name`, `status` (state machine), `match_policy`, `starts_at`, `ends_at`, `store_id`. Has many `prices` and `price_rules`.
- **PriceRule** (STI base): Defines a condition for price list eligibility (e.g., customer group, order total). Subclasses registered via `Spree.pricing.rules`. Attributes: `type`, `value`, `match_policy`.

---

## Backend Requirements

### Data Model

- **Model**: `Spree::PriceList` — `Spree.base_class`; state machine on `status`; store-scoped
- **Columns**: `name` (string, required), `status` (string, state machine), `match_policy` (string), `starts_at` / `ends_at` (datetime), `store_id`, counter caches for `products_count`, `prices_count`
- **Soft delete**: Not applicable

### API Surface

#### Store API

None — price lists are admin-managed only.

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/price_lists` | List price lists |
| GET | `/api/v3/admin/price_lists/:id` | Show price list |
| POST | `/api/v3/admin/price_lists` | Create price list |
| PATCH | `/api/v3/admin/price_lists/:id` | Update price list |
| DELETE | `/api/v3/admin/price_lists/:id` | Delete price list |
| PATCH | `/api/v3/admin/price_lists/:id/activate` | Transition to `active` |
| PATCH | `/api/v3/admin/price_lists/:id/deactivate` | Transition to `inactive` |
| GET/POST | `/api/v3/admin/price_lists/:id/prices` | List or bulk-assign product prices |
| GET | `/api/v3/admin/price_lists/price_rule_types` | Available rule types |

### Serializer Fields

**Admin serializer** (`Spree::Api::V3::Admin::PriceListSerializer` — admin-only, no store serializer):
- `id`: prefixed string (`pl_…`)
- `name`: string
- `status`: string
- `match_policy`: string
- `starts_at`, `ends_at`: datetime | null
- `products_count`, `prices_count`: number
- `product_ids`: array of prefixed strings
- `price_rules`: nested array
- `created_at`, `updated_at`

### Authorization

- CanCanCan: `can :manage, Spree::PriceList` for admin
- Ransack allowlist: `name`, `status`, `starts_at`, `ends_at`

### i18n (Rails)

- Keys in `spree/core/config/locales/en.yml` under `spree.price_list.*`

---

## Frontend Requirements

### SPA Routes

- `products/price-lists/index.tsx` — list page
- `products/price-lists/new.tsx` — create form
- `products/price-lists/$priceListId/index.tsx` — edit form (prices, rules, status)

### Resource Hook

- `packages/dashboard/src/hooks/use-price-lists.ts`

### Table

- `packages/dashboard/src/tables/price-lists.tsx`

### i18n Keys

Under `admin.priceLists.*` in all 6 locale files: page title, column headers (name, status, products, starts_at, ends_at), status badge labels, button labels, empty state, toast messages, confirm dialogs.

### Date/time fields

`starts_at` and `ends_at` — use `<StoreDatePicker includeTime>` for datetime selection.

---

## Success Criteria

- **SC-001**: Admin can create a price list, assign products with prices, and activate it in under 5 steps
- **SC-002**: `GET /api/v3/admin/price_lists` returns paginated list with prefixed IDs, status, and product/price counts
- **SC-003**: `PATCH /api/v3/admin/price_lists/:id/activate` transitions status to `active` and returns updated resource
- **SC-004**: Bulk price assignment via the `prices` action uses `upsert_all` (single SQL query per batch)
- **SC-005**: A product from a different store cannot be added to a price list (422 returned)

---

## Assumptions

- Price lists are admin-managed only — there is no customer-facing endpoint for price lists
- The pricing engine (outside this feature's scope) applies price lists based on the current customer context
- `PriceRule` subclasses are loaded via `Spree.pricing.rules` registry — not all subtypes are defined in core
- `starts_at` / `ends_at` define eligibility windows; the state machine (`draft`/`active`/`scheduled`/`inactive`) is the primary activation gate
