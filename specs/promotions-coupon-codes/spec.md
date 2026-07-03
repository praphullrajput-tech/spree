# Feature Specification: Promotions & Coupon Codes

**Feature Branch**: `main` (fully implemented; 5.6 single-store ownership migration complete; 6.0 join-table drop pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: `docs/plans/5.6-6.0-single-store-promotions-payment-methods.md`

---

## User Scenarios & Testing

### User Story 1 — Manage Promotions (Priority: P1)

An admin creates promotions with qualifying rules and discount actions. Promotions are either coupon-code-based (customer enters a code) or automatic (applied when conditions match without a code). Multi-code promotions bulk-generate unique codes — one per customer.

**Why this priority**: Promotions are a primary revenue tool. Rule/action CRUD is the foundation for all discount strategies.

**Independent Test**: Admin creates a `coupon_code` promotion with `name: "Summer Sale"`, `code: "SUMMER20"`, adds an `ItemTotal` rule (minimum $50) and a `CreateAdjustment` action (20% off). `POST /api/v3/cart/apply_coupon_code { coupon_code: "SUMMER20" }` applies the discount and the cart shows a negative adjustment.

**Acceptance Scenarios**:

1. **Given** no promotions, **When** admin creates a `coupon_code` promotion with `code: "SUMMER20"`, **Then** it appears with `kind: "coupon_code"` and a prefixed ID (`promo_…`)
2. **Given** a promotion with `match_policy: "all"`, **When** cart satisfies all rules, **Then** discount is applied
3. **Given** a promotion with `match_policy: "any"`, **When** cart satisfies at least one rule, **Then** discount is applied
4. **Given** a `multi_codes` promotion with `number_of_codes: 100`, **When** saved, **Then** 100 unique `CouponCode` records are generated via `after_commit`
5. **Given** a promotion with `expires_at` in the past, **When** cart applies the code, **Then** 422 with reason "Promotion has expired"

---

### User Story 2 — Organize and Scope Promotions (Priority: P2)

An admin groups promotions into categories for bulk management. Promotions are scoped to a single store (5.6+), so cross-store leakage is impossible.

**Why this priority**: Store owners managing dozens of promotions need filtering; single-store scoping is an integrity constraint not a UX feature.

**Independent Test**: Admin creates a `PromotionCategory` "Holiday Deals" and assigns a promotion to it. `GET /admin/promotions?q[promotion_category_id_eq]=<id>` returns only promotions in that category.

**Acceptance Scenarios**:

1. **Given** a promotion category, **When** filtering by category, **Then** only promotions in that category are returned
2. **Given** two stores, **When** admin of store A lists promotions, **Then** store B's promotions are absent
3. **Given** an `automatic` promotion with `path: "/sale"`, **When** a cart visits that path, **Then** the promotion is auto-applied without a code

---

### User Story 3 — Storefront Applies Promotions (Priority: P1)

A customer applies a coupon code during checkout. The store validates the code, checks eligibility rules, and applies the discount action to the cart. Per-code and per-promotion usage limits are enforced.

**Why this priority**: Code application is the customer-facing payoff of the entire promotions system.

**Independent Test**: `POST /api/v3/cart/apply_coupon_code { coupon_code: "SUMMER20" }` returns 200 with updated cart containing a promotion adjustment. Applying a used-up code returns 422.

**Acceptance Scenarios**:

1. **Given** a valid unused code, **When** customer applies it, **Then** promotion adjustment appears on cart totals
2. **Given** a `usage_limit` reached on the promotion, **When** customer applies it, **Then** 422 "Coupon code has been used the maximum number of times"
3. **Given** a `CouponCode` with per-code `usage_limit: 1`, **When** used once, **Then** that specific code's `times_used` reaches its limit and rejects subsequent uses
4. **Given** a 422 from coupon application, **When** rendered in the SPA, **Then** inline error shows the specific reason

---

### Edge Cases

- What if two promotions both apply to the same cart? → Both apply if independently eligible; separate `Adjustment` records appear per promotion action
- What if a promotion rule references a deleted taxon? → Eligibility check returns `false` gracefully; promotion does not apply
- What if `generate_coupon_codes` `after_commit` has not fired yet? → Brief window; codes are inaccessible; idempotent regeneration on next save
- What if a `multi_codes` promotion's `code` field is set? → `before_validation :set_code_to_nil` clears it; single `code` field is incompatible with multi-codes

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::Promotion` supports two kinds: `coupon_code` (customer enters a code) and `automatic` (no code required, applied via rules/path)
- **FR-002**: Multi-code promotions (`multi_codes?: true`) bulk-generate individual `Spree::CouponCode` records via `after_commit :generate_coupon_codes`
- **FR-003**: Eligibility is evaluated by `Spree::PromotionRule` STI subclasses; `match_policy` controls `all` vs `any` evaluation across rules
- **FR-004**: Discount is applied by `Spree::PromotionAction` STI subclasses; rule and action types are registered via `Spree.promotions.rules` and `Spree.promotions.actions`
- **FR-005**: Promotions are scoped to a single store via `store_id` FK (5.6); previously multi-store via `spree_promotions_stores` join table
- **FR-006**: `Spree::PromotionCategory` provides grouping for admin list organization
- **FR-007**: Store API: apply/remove coupon code on cart; Admin API: full CRUD for promotions, coupon codes, rules, actions, categories
- **FR-008**: All promotion IDs prefixed `promo_…`
- **FR-009**: _(6.0 pending)_ Drop `spree_promotions_stores` join table; enforce `store_id null: false` on `spree_promotions`

### Key Entities

- **Promotion** (`Spree::Promotion`): `kind` (coupon_code/automatic), `name`, `code` (single-code mode), `multi_codes` boolean, `number_of_codes`, `match_policy` (all/any), `usage_limit`, `starts_at`, `expires_at`, `path` (for automatic URL-scoped promotions), `store_id`. Prefix: `promo_`.
- **CouponCode** (`Spree::CouponCode`): `code`, `promotion_id`, `usage_limit` (per-code), `times_used`. Belongs to one Promotion.
- **PromotionRule** (`Spree::PromotionRule`): STI base — one row per rule attached to a promotion. Registered via `Spree.promotions.rules`. Built-in subclasses: `ItemTotal`, `Product`, `Customer`, `FirstOrder`, `UserLoggedIn`, `OptionValue`, `Taxon`, `Country`, `Store`.
- **PromotionAction** (`Spree::PromotionAction`): STI base — one row per action. Registered via `Spree.promotions.actions`. Built-in: `CreateAdjustment`, `CreateItemAdjustments`, `FreeShipping`.
- **PromotionCategory** (`Spree::PromotionCategory`): `name` — groups promotions in admin.
- **OrderPromotion** (`Spree::OrderPromotion`): join model linking orders to their applied promotions.

---

## Backend Requirements

### Data Model

- **Tables**: `spree_promotions`, `spree_promotion_rules`, `spree_promotion_actions`, `spree_coupon_codes`, `spree_promotion_categories`, `spree_order_promotions`
- **Join tables (drop in 6.0)**: `spree_promotions_stores`
- **Indexes**: `store_id` FK on promotions (5.6); unique `(code)` on promotions for single-code mode; unique `(code, promotion_id)` on coupon_codes
- **Note**: `kind` is stored as an integer Rails enum (`coupon_code: 0, automatic: 1`) — a legacy exception to the "use string columns" convention; CLAUDE.md mandates string columns for new work

### API Surface

#### Store API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v3/cart/apply_coupon_code` | Apply coupon code to active cart |
| DELETE | `/api/v3/cart/remove_coupon_code` | Remove coupon code from cart |

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/promotions` | List promotions (store-scoped, Ransack-filterable) |
| POST | `/api/v3/admin/promotions` | Create promotion |
| GET | `/api/v3/admin/promotions/:id` | Show promotion |
| PATCH | `/api/v3/admin/promotions/:id` | Update promotion |
| DELETE | `/api/v3/admin/promotions/:id` | Delete promotion |
| GET | `/api/v3/admin/promotions/:id/coupon_codes` | List coupon codes for promotion |
| POST | `/api/v3/admin/promotions/:id/coupon_codes` | Create single coupon code |
| DELETE | `/api/v3/admin/coupon_codes/:id` | Delete coupon code |
| GET | `/api/v3/admin/promotions/:id/promotion_rules` | List rules |
| POST | `/api/v3/admin/promotions/:id/promotion_rules` | Add rule |
| PATCH | `/api/v3/admin/promotion_rules/:id` | Update rule |
| DELETE | `/api/v3/admin/promotion_rules/:id` | Remove rule |
| GET | `/api/v3/admin/promotions/:id/promotion_actions` | List actions |
| POST | `/api/v3/admin/promotions/:id/promotion_actions` | Add action |
| DELETE | `/api/v3/admin/promotion_actions/:id` | Remove action |
| GET | `/api/v3/admin/promotion_categories` | List categories |
| POST | `/api/v3/admin/promotion_categories` | Create category |
| PATCH | `/api/v3/admin/promotion_categories/:id` | Update category |
| DELETE | `/api/v3/admin/promotion_categories/:id` | Delete category |

### Serializer Fields

**Admin PromotionSerializer** (Admin extends Store):
- Store: `id` (promo_…), `name`, `kind`, `code`, `multi_codes`, `match_policy`, `usage_limit`, `starts_at`, `expires_at`, `path`
- Admin adds: `number_of_codes`, `store_id`, `promotion_category_id`, `promotion_rules` (embedded), `promotion_actions` (embedded), `created_at`, `updated_at`

**Admin CouponCodeSerializer**:
- `id`, `code`, `usage_limit`, `times_used`, `promotion_id` (promo_…)

**Admin PromotionRuleSerializer**:
- `id`, `type` (STI class string), `promotion_id`, `preferences` (JSON), `created_at`

### Authorization

- CanCanCan: `can :manage, Spree::Promotion` for admin users
- Ransack allowlist: `name`, `code`, `kind`, `starts_at`, `expires_at`, `store_id`, `promotion_category_id`

### i18n (Rails)

- Keys under `spree.promotion.*`; rule/action type labels under `spree.promotion_rules.*` and `spree.promotion_actions.*`

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/promotions/index.tsx` — list with status filters
- `packages/dashboard/src/routes/_authenticated/$storeId/promotions/new.tsx` — create form
- `packages/dashboard/src/routes/_authenticated/$storeId/promotions/$promotionId.tsx` — edit / detail with rules, actions, coupon codes tabs

### Hooks

- `packages/dashboard/src/hooks/use-promotions.ts` — TanStack Query wrappers for promotions CRUD

### i18n Keys

Under `admin.promotions.*` in all 6 locale files: page title, column headers (name, kind, usage, dates), kind labels, match_policy labels, form labels, toast messages, empty state.

---

## Success Criteria

- **SC-001**: Admin can create a `coupon_code` promotion; customer applies it at checkout; discount adjustment appears on cart
- **SC-002**: Multi-code promotion generates individual `CouponCode` records; each is independently usage-limited
- **SC-003**: Promotions are scoped to the owning store; store B cannot access store A's promotions
- **SC-004**: Expired, invalid, or usage-exhausted codes return 422 with a human-readable reason
- **SC-005**: _(6.0)_ `spree_promotions_stores` join table dropped; `store_id null: false` enforced

---

## Assumptions

- `kind` stored as integer Rails enum (`coupon_code: 0, automatic: 1`) — legacy exception to string-column convention
- `Spree::PromotionRule` and `Spree::PromotionAction` STI subclasses are registered via `Spree.promotions.rules` and `Spree.promotions.actions` — same pattern as `Spree::Calculator` and `Spree::PaymentMethod`
- `multi_codes?` is derived from `number_of_codes.present? && number_of_codes.positive?`
- Promotion `path` applies to automatic promotions triggered when the customer visits a matching URL path (e.g., a "sale" landing page)
