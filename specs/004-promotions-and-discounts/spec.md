# Feature Specification: Promotions & Discounts

**Feature Branch**: `004-promotions-and-discounts`

**Created**: 2026-08-24

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — no original user description. Source: `spree/core/app/models/spree/promotion.rb`, `promotion_rule.rb`, `promotion_action.rb`, `spree/core/app/models/spree/promotion/{rules,actions}/*.rb`, `promotion_handler/{coupon,free_shipping}.rb`, `spree/core/app/services/spree/coupon_codes/coupon_codes_handler.rb`, `spree/api/app/controllers/spree/api/v3/admin/promotions_controller.rb`, `packages/dashboard/src/{hooks/use-promotions.ts,tables/promotions.tsx,schemas/promotion.ts,components/spree/promotion-editors/promotion-form.tsx,routes/_authenticated/$storeId/promotions/**}`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merchant configures a discount promotion (Priority: P1)

A store admin creates a `Spree::Promotion` (automatic or coupon-code-gated) with one or more eligibility rules (rule types: item total, product, taxon, user, user-logged-in, one-use-per-user, first-order, country, currency, market, channel, customer group, option value) and one or more actions (create adjustment with a calculator, create item adjustments, create line items, free shipping), via the Admin API/dashboard.

**Why this priority**: Without configuration there is no discount system — this is the entire feature surface for merchants.

**Independent Test**: `POST /api/v3/admin/promotions` with `rules: [...]`, `actions: [...]` nested payload; `GET` returns the persisted rule/action ids.

**Acceptance Scenarios**:

1. **Given** an admin authenticated via JWT or a secret key with `write_promotions` scope, **When** they POST a promotion with `kind: automatic` and a `Rules::ItemTotal` rule plus a `Actions::CreateAdjustment` action with a `flat_rate` calculator, **Then** the promotion, rule, and action rows are created in one request (`Promotion#rules=`/`#actions=` reconcile the nested collections).
2. **Given** an existing promotion, **When** the admin PATCHes it with an updated `rules`/`actions` array (some rows with `id`, some without), **Then** matched rows are updated, new rows are inserted, and rows omitted from the payload are destroyed (typed-association reconciliation), applied after save via `apply_pending_rules_and_actions`.

---

### User Story 2 - Customer applies a coupon code at checkout (Priority: P1)

A customer enters a coupon code on their cart/order. `Spree::PromotionHandler::Coupon#apply` resolves the code (single fixed `code` or a disposable code from the `multi_codes` pool via `Spree::CouponCode`), checks eligibility (`Promotion#eligible?`, usage limits, blacklisted/non-promotionable products, expiry), and — if eligible — activates the promotion's actions against the order, creating `Spree::Adjustment` records or free line items.

**Why this priority**: This is the customer-facing payoff of the whole feature — the discount must actually reduce what the customer pays.

**Independent Test**: Build an order with a coupon-code promotion having a `Rules::ItemTotal` rule and a `Actions::CreateAdjustment` (flat 10% calculator); apply the code; assert an eligible `Spree::Adjustment` with `source_type: 'Spree::PromotionAction'` exists and `order.promo_total` reflects it.

**Acceptance Scenarios**:

1. **Given** a valid, unused, unexpired coupon code under its usage limit, **When** the customer applies it, **Then** `PromotionHandler::Coupon#apply` returns `successful? == true` and an eligible promotion adjustment (or free-shipping / free line items) is attached to the order.
2. **Given** an already-applied promotion, already-used single-use code, expired promotion, or ineligible order (rules not satisfied, non-promotionable products), **When** the customer applies/re-applies the code, **Then** `apply` sets one of the documented error codes (`coupon_code_not_found`, `coupon_code_expired`, `coupon_code_already_applied`, `coupon_code_used`, `coupon_code_max_usage`, `coupon_code_not_eligible`) and no adjustment is created.
3. **Given** an order with an applied promotion, **When** the customer removes the coupon code, **Then** `PromotionHandler::Coupon#remove` destroys the promotion's adjustments, removes any promotion-created line items, frees a disposable `CouponCode` back to `unused`, and re-runs `order.update_with_updater!`.

---

### User Story 3 - Free shipping promotions apply automatically (Priority: P2)

Automatic (non-coupon) promotions with a `Actions::FreeShipping` action are evaluated and activated by `PromotionHandler::FreeShipping#activate` whenever shipping rates are calculated, independent of the coupon flow.

**Why this priority**: Free shipping is a distinct action type with its own activation path (shipment-rate calculation) rather than the general order-update path — important but narrower than P1 flows.

**Independent Test**: Create an automatic promotion (`kind: automatic`, no `code`) with a `Actions::FreeShipping` action and no rules; call `PromotionHandler::FreeShipping.new(order).activate`; assert the promotion is now in `order.promotions` and shipment adjustments reflect zero shipping cost.

**Acceptance Scenarios**:

1. **Given** an automatic promotion with a `FreeShipping` action and satisfied rules, **When** `FreeShipping#activate` runs, **Then** the promotion activates against the order (skipped if the promotion is coupon-code-gated and not already on the order).

---

### User Story 4 - Coupon code lifecycle at order completion (Priority: P3)

When an order transitions to complete, `Spree::CouponCodes::CouponCodesHandler#use_all_codes` marks the `CouponCode` rows tied to promotions with confirmed eligible adjustments as `used`, and releases (`order_id: nil`) any codes attached to promotions that did not end up eligible.

**Why this priority**: Bookkeeping/cleanup step — correctness matters (double-use prevention) but it's a background reconciliation, not a primary interaction.

**Independent Test**: Complete an order carrying two multi-code promotions where only one has a surviving eligible adjustment; run `use_all_codes`; assert the used code's `CouponCode#state == 'used'` and the other's `order_id` is nilled.

**Acceptance Scenarios**:

1. **Given** an order with adjustments from `Promotion A` only, **When** `use_all_codes` runs, **Then** `Promotion A`'s coupon code for this order becomes `used` and any other order-scoped, non-eligible codes are cleared.

### Edge Cases

- Promotion `usage_limit` reached mid-checkout by a concurrent order → `usage_limit_exceeded?` re-checked at activation time (`handle_present_promotion`), not just at apply-time display.
- A promotion's rules match, but the promotable is a non-`promotionable` product or an order with only non-promotionable line items → `blacklisted?` short-circuits `eligible?` to `false`.
- `match_policy` `all` vs `any` — with `all`, any inapplicable-rule-for-this-promotable makes the whole promotion ineligible (not just skipped); with `any`, the first eligible rule wins (`eligible_rules`).
- Promotion source destroyed while an order is incomplete → adjustments destroyed outright (`for_incomplete_order.destroy_all`); if the order is already complete → adjustment kept but `source_id` nulled so the order total is unaffected (`AdjustmentSource#deals_with_adjustments_for_deleted_source`).
- Switching a promotion from `multi_codes` to single-code (or `coupon_code` kind to `automatic`) soft-deletes its generated `CouponCode` rows (`Promotion#remove_coupons`).
- `number_of_codes` above `Spree::Config.coupon_codes_web_limit` defers bulk code generation to a background job (`Spree::CouponCodes::BulkGenerateJob`) rather than inline.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support two promotion `kind`s: `coupon_code` (requires a code, entered by the customer) and `automatic` (applied without a code, subject to rules).
- **FR-002**: System MUST support both a single fixed `code` and a pool of disposable, per-order `Spree::CouponCode` rows (`multi_codes`, bounded by `number_of_codes` ≤ `Spree::Config.coupon_codes_total_limit`).
- **FR-003**: System MUST evaluate promotion eligibility through pluggable `Spree::PromotionRule` STI subclasses, combined via `match_policy` (`all`/`any`).
- **FR-004**: System MUST perform promotion effects through pluggable `Spree::PromotionAction` STI subclasses (`CreateAdjustment`, `CreateItemAdjustments`, `CreateLineItems`, `FreeShipping`), each returning a truthy/falsy "action taken" result.
- **FR-005**: System MUST record promotion effects as `Spree::Adjustment` rows polymorphically sourced from the `PromotionAction` (`source_type: 'Spree::PromotionAction'`), computed via a `Spree::Calculator` through the shared `CalculatedAdjustments`/`AdjustmentSource` concerns.
- **FR-006**: System MUST enforce `usage_limit` (total redemptions) and per-user one-use rules (`Rules::OneUsePerUser`) at both apply-time and activation-time.
- **FR-007**: System MUST prevent applying a promotion to a non-`UNACTIVATABLE_ORDER_STATES` order (`complete`, `awaiting_return`, `returned` are excluded from (re)activation).
- **FR-008**: System MUST expose promotion CRUD, with nested rules/actions in a single request, via the Admin API (`Spree::Api::V3::Admin::PromotionsController`), and a minimal read-only public surface via the Store API (`name`, `description`, `code` only).
- **FR-009**: System MUST scope promotions to a single store (`belongs_to :store`, `Spree::SingleStoreResource`), with a deprecation bridge (`Spree::LegacyMultiStoreSupport`) for historical multi-store sharing pending the `spree_multi_store` extension.
- **FR-010**: System MUST let plugins register additional rule/action STI subclasses and extend the permitted-params allowlist via `additional_permitted_attributes` on their subclass, without modifying the controller.

### Key Entities

- **Spree::Promotion**: The discount definition — name, code, kind, match policy, validity window, usage limit, multi-code config, store-scoped. Has many rules and actions; has many coupon codes; joins to orders through `OrderPromotion`.
- **Spree::PromotionRule**: STI base for eligibility conditions (`applicable?`, `eligible?`) — one row per rule type per promotion.
- **Spree::PromotionAction**: STI base for effects (`perform`) — free shipping, adjustment creation (flat/calculated), free line-item grants.
- **Spree::CouponCode**: A single disposable code belonging to a `multi_codes` promotion; `unused`/`used` state machine, tied to the order that consumed it.
- **Spree::Adjustment**: The financial record of a promotion's effect on an order/line item/shipment — polymorphic `source` (here, a `PromotionAction`), `eligible`/`open`-`closed` state.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Promotion`, `PromotionRule`/`PromotionAction` STI hierarchies, `Spree::CouponCode`, `Spree::Adjustment`, `AdjustmentSource`/`CalculatedAdjustments` concerns, `PromotionHandler::{Coupon,FreeShipping}`, `Spree::CouponCodes::{CouponCodesHandler,BulkGenerate,BulkGenerateJob}` |
| `spree/api` (Store/Admin API v3) | Yes | `Admin::PromotionsController` (full CRUD + nested rules/actions), `Store`/`Admin` `PromotionSerializer`, `Admin::PromotionRuleSerializer`, `Admin::PromotionActionSerializer` |
| `packages/dashboard` (admin SPA) | Yes | `routes/.../promotions/$promotionId.tsx`, `tables/promotions.tsx`, `schemas/promotion.ts`, `hooks/use-promotions.ts`, `components/spree/promotion-editors/promotion-form.tsx` |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated types (`PromotionRule.ts`, `PromotionAction.ts`, `CouponCode.ts`, `Discount.ts` zod schema) — regenerated from serializers, not hand-written |
| `docs/plans/` | No | No active `docs/plans/6.0-*` entry governs promotions specifically; `5.4-store-api-naming-standardization.md` touches adjacent naming but promotions are not separately tracked there |

### API Contract *(include if feature touches spree/api)*

- **Existing endpoints**: `GET/POST /api/v3/admin/promotions`, `GET/PATCH/DELETE /api/v3/admin/promotions/:id` (`spree/api/config/routes.rb:252`, standard `ResourceController` CRUD); Store API exposes only a read-only, minimal `PromotionSerializer` (no dedicated Store promotions endpoint beyond what other resources embed, e.g. applied promotions on an order/cart).
- **Serializer fields (read, Admin)**: `name`, `description`, `code`, `starts_at`, `expires_at`, `usage_limit`, `match_policy`, `path`, `kind`, `multi_codes`, `number_of_codes`, `code_prefix`, `promotion_category_id`, `metadata`, `action_ids`, `rule_ids`, `created_at`, `updated_at` — matches `permitted_params` on write (`name, description, code, path, starts_at, expires_at, usage_limit, match_policy, kind, multi_codes, number_of_codes, code_prefix, promotion_category_id, rules, actions`), read/write symmetric per Constitution Principle III.
- **Serializer fields (read, Store)**: `name`, `description`, `code` only — no write endpoint on the Store side.
- **Auth**: Admin API — secret key (scopes, presumably `read_promotions`/`write_promotions`) or Admin JWT + CanCanCan (`Spree::Security::Promotions` if defined). Store API — publishable key, read-only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A merchant can create a fully-configured promotion (rules + actions) in a single Admin API request without a follow-up call.
- **SC-002**: A customer applying a valid coupon code sees the discount reflected in the order total within the same request/response cycle (no async reconciliation needed for the happy path).
- **SC-003**: No promotion can be applied more than its `usage_limit` or bypass `one_use_per_user`, verified by existing model/service specs (`promotion_rule_spec.rb`, `adjustable/adjuster/promotion_spec.rb`).
- **SC-004**: Removing a coupon code fully reverses its financial effect (adjustments destroyed, line items removed, code returned to the `unused` pool) with no residual total drift.

## Assumptions

- This spec documents the system **as implemented**; no new behavior is proposed.
- "Discounts" in the feature name refers to the `Spree::Adjustment` records created by promotion actions, not a separate, unbuilt discount model (per `docs/plans/6.0-split-adjustments.md`, the polymorphic `Adjustment` is slated to be replaced by typed `TaxLine`/`Discount`/`Fee` models in 6.0 — that migration is tracked separately and out of scope here).
- Gift card redemption is handled by the same `PromotionHandler::Coupon#apply`/`#remove` entry points (shared coupon-code input field) but is a distinct model (`Spree::GiftCard`) not itself part of the Promotion/Adjustment domain — included here only because it shares the handler.
- Admin API secret-key scope names (`read_promotions`/`write_promotions`) are inferred from the project-wide scope convention (`docs/plans/5.5-admin-api-key-scopes.md`); the promotions controller itself does not declare scopes explicitly in the files read.

## Migration Notes

Gaps and inferences made while reverse-engineering this spec, flagged for follow-up rather than silently resolved:

- **No dedicated Store API promotions endpoint found** beyond the minimal read-only serializer — could not confirm whether/how a customer looks up a promotion by code outside the coupon-application flow (likely surfaced only via order/cart serializers showing applied promotions, not read directly).
- **CanCanCan ability class** `Spree::Security::Promotions` is conditionally included (`if defined?`) — its actual permission rules live outside the files reviewed for this migration; not inspected.
- **Admin API secret-key scopes** for promotions were not found declared in `PromotionsController`; assumed to follow the standard `read_/write_<resource>` convention from `5.5-admin-api-key-scopes.md` but not verified against `Spree::ApiKey`'s scope list.
- **`packages/dashboard` promotion editor internals** (`promotion-form.tsx`, `tables/promotions.tsx`) were located but not read line-by-line for this spec — Module Impact / API Contract sections describe them by file path and role only, not by exact field-level UI behavior.
- **No RSpec coverage found** for `PromotionHandler::FreeShipping` or `Spree::CouponCodes::CouponCodesHandler` specifically in the "starting source files" list — User Stories 3 and 4 are inferred from the handler code itself; existing test coverage (`promotion_rule_spec.rb`, `adjustable/adjuster/promotion_spec.rb`) covers rule eligibility and the adjuster/action path, not these two handlers directly.
- **6.0 split-adjustments plan** (`docs/plans/6.0-split-adjustments.md`) will replace the polymorphic `Spree::Adjustment` this feature depends on with a typed `Discount` model — this spec describes current (pre-6.0) behavior only.
