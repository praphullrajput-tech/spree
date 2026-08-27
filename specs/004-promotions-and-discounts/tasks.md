---
description: "Task list — reverse-engineered from shipped code (brownfield migration)"
---

# Tasks: Promotions & Discounts

**Input**: Design documents from `/specs/004-promotions-and-discounts/`

**Prerequisites**: plan.md, spec.md

**Note**: This feature is already implemented. Every task below is marked
complete (`[x]`) and annotated with the file(s) that satisfy it, recovered
from the existing codebase rather than written prospectively.

**Organization**: Tasks are grouped by the user stories in spec.md.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 `spree/core` and `spree/api` gems build/test against the shared dummy Rails app (standard engine setup, no feature-specific setup step found)
- [x] T002 [P] Baseline backend suite covers promotions: `spree/core/spec/models/spree/promotion_rule_spec.rb`, `spree/core/spec/models/spree/adjustable/adjuster/promotion_spec.rb`
- [x] T003 [P] `packages/dashboard` typechecks/lints with the promotions route and hook in place (`routes/_authenticated/$storeId/promotions/$promotionId.tsx`, `hooks/use-promotions.ts`)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 [spree/core] `spree_promotions`, `spree_promotion_rules`, `spree_promotion_actions`, `spree_coupon_codes`, `spree_order_promotions`, `spree_promotion_action_line_items` tables (migrations pre-date this migration pass; not individually re-audited)
- [x] T005 [spree/core] `Spree::Promotion` base model — `spree/core/app/models/spree/promotion.rb` (store-scoped via `Spree::SingleStoreResource`, `Spree::Metafields`, `Spree::Metadata`, prefix id `promo`)
- [x] T006 [spree/core] `Spree::PromotionRule` / `Spree::PromotionAction` STI bases with `additional_permitted_attributes` extension hook — `spree/core/app/models/spree/promotion_rule.rb`, `spree/core/app/models/spree/promotion_action.rb`
- [x] T007 [spree/core] `Spree::Adjustment` polymorphic financial record + `AdjustmentSource`/`CalculatedAdjustments` concerns — `spree/core/app/models/spree/adjustment.rb`, `spree/core/app/models/concerns/spree/adjustment_source.rb`, `spree/core/app/models/concerns/spree/calculated_adjustments.rb`
- [x] T008 [spree/api] Ransack allowlist on `Promotion` (`name, path, promotion_category_id, code, starts_at, expires_at`, association `coupon_codes`) and `CouponCode` (`state, code, promotion_id`, association `promotion`) — `promotion.rb:93-94`, `coupon_code.rb`
- [x] T009 [packages/dashboard] Promotions table/nav registration — `tables/promotions.tsx`, `routes/_authenticated/$storeId/promotions/$promotionId.tsx`

**Checkpoint**: Foundation in place — rule/action STI hierarchies, adjustment recording, and Admin API scaffolding all exist and are exercised by the user stories below.

---

## Phase 3: User Story 1 - Merchant configures a discount promotion (Priority: P1) 🎯 MVP

**Goal**: Admin can create/update a promotion with nested rules and actions in one request.

**Independent Test**: `POST`/`PATCH /api/v3/admin/promotions` with nested `rules`/`actions`; reload and confirm reconciliation.

### Implementation for User Story 1

- [x] T010 [US1] `Promotion#rules=` / `#actions=` flat-payload typed-association writers — `spree/core/app/models/spree/promotion.rb:125-132` (delegates to `assign_typed_association`)
- [x] T011 [US1] `after_save :apply_pending_rules_and_actions` reconciliation (insert/update/destroy) — `promotion.rb:44,306-309`
- [x] T012 [US1] 12 concrete `PromotionRule` STI subclasses — `spree/core/app/models/spree/promotion/rules/{item_total,product,taxon,user,user_logged_in,one_use_per_user,first_order,country,currency,market,channel,customer_group,option_value}.rb`
- [x] T013 [US1] 4 concrete `PromotionAction` STI subclasses — `spree/core/app/models/spree/promotion/actions/{create_adjustment,create_item_adjustments,create_line_items,free_shipping}.rb`
- [x] T014 [US1] `Admin::PromotionsController` full CRUD + nested rule/action permitted-params allowlist, merging plugin `additional_permitted_attributes` — `spree/api/app/controllers/spree/api/v3/admin/promotions_controller.rb`
- [x] T015 [US1] `Admin::PromotionSerializer` (extends Store serializer) exposing `action_ids`/`rule_ids` as prefixed-id arrays — `spree/api/app/serializers/spree/api/v3/admin/promotion_serializer.rb`
- [x] T016 [US1] `Admin::PromotionRuleSerializer` / `Admin::PromotionActionSerializer` — `spree/api/app/serializers/spree/api/v3/admin/{promotion_rule,promotion_action}_serializer.rb`
- [x] T017 [US1] Dashboard promotion editor form (rule/action builder) — `packages/dashboard/src/components/spree/promotion-editors/promotion-form.tsx`, `schemas/promotion.ts`
- [x] T018 [US1] `use-promotions.ts` hook wrapping Admin SDK calls, never calling `adminClient` directly from components — `packages/dashboard/src/hooks/use-promotions.ts`

**Checkpoint**: Merchant-facing promotion authoring is fully functional.

---

## Phase 4: User Story 2 - Customer applies a coupon code at checkout (Priority: P1)

**Goal**: A customer's coupon code resolves to an eligible promotion and produces order adjustments/line items.

**Independent Test**: Apply a valid code to an order with a satisfied `ItemTotal` rule and a `CreateAdjustment` action; assert an eligible `Spree::Adjustment` exists.

### Tests for User Story 2

- [x] T019 [P] [US2] `spree/core/spec/models/spree/adjustable/adjuster/promotion_spec.rb` — covers adjuster-side application of promotion actions to adjustments (`CustomPromotionAction` fixture)

### Implementation for User Story 2

- [x] T020 [US2] `Spree::PromotionHandler::Coupon#apply` — resolves single-code vs. multi-code promotions, checks expiry/usage/eligibility, activates — `spree/core/app/models/spree/promotion_handler/coupon.rb:13-47,140-157`
- [x] T021 [US2] `Promotion.with_coupon_code` — resolves a code against both the legacy `code` column and the `Spree::CouponCode` pool — `promotion.rb:96-106`
- [x] T022 [US2] `Promotion#eligible?` / `#eligible_rules` — match-policy-aware rule evaluation with per-rule eligibility errors — `promotion.rb:207-243`
- [x] T023 [US2] `Promotion#activate` / `#deactivate` — runs each action's `perform`/`revert`, joins the order to the promotion if any action fired — `promotion.rb:154-204`
- [x] T024 [US2] `AdjustmentSource#create_adjustment(s)` / `#create_unique_adjustment(s)` — idempotent adjustment creation used by `CreateAdjustment`/`CreateItemAdjustments` — `adjustment_source.rb:12-36`
- [x] T025 [US2] `PromotionHandler::Coupon#remove` — destroys promotion adjustments, removes promotion-created line items, frees a disposable `CouponCode` — `coupon.rb:49-83,123-138`
- [x] T026 [US2] Gift-card code sharing the same coupon-code input (`gift_cards_enabled?`, `load_gift_card_code`) — `coupon.rb:14-33,215-226`

**Checkpoint**: Coupon application/removal round-trips correctly against order totals.

---

## Phase 5: User Story 3 - Free shipping promotions apply automatically (Priority: P2)

**Goal**: Automatic (non-coupon) free-shipping promotions activate without customer input.

**Independent Test**: Create an automatic promotion with a `FreeShipping` action and no unmet rules; run the handler; confirm activation.

### Implementation for User Story 3

- [x] T027 [US3] `Spree::PromotionHandler::FreeShipping#activate` — iterates active promotions with a `FreeShipping` action, skips coupon-gated promotions not already on the order — `spree/core/app/models/spree/promotion_handler/free_shipping.rb`
- [x] T028 [US3] `Spree::Promotion::Actions::FreeShipping` action + `PromotionAction#free_shipping?` helper — `spree/core/app/models/spree/promotion/actions/free_shipping.rb`, `promotion_action.rb:35-37`

**Checkpoint**: Free shipping activates independently of the coupon-entry flow.

---

## Phase 6: User Story 4 - Coupon code lifecycle at order completion (Priority: P3)

**Goal**: Disposable coupon codes are marked used or released once an order completes.

**Independent Test**: Complete an order with one eligible and one non-eligible multi-code promotion; run the handler; confirm state split.

### Implementation for User Story 4

- [x] T029 [US4] `Spree::CouponCodes::CouponCodesHandler#use_all_codes` — finds promotions with a surviving eligible adjustment, marks their codes `used`, releases the rest — `spree/core/app/services/spree/coupon_codes/coupon_codes_handler.rb`
- [x] T030 [US4] `Spree::CouponCode` `unused`/`used` state machine + `apply_order!`/`remove_from_order` — `spree/core/app/models/spree/coupon_code.rb`
- [x] T031 [US4] `Promotion#generate_coupon_codes` / `#remove_coupons` — bulk-generates on `number_of_codes` change (inline or via `BulkGenerateJob` above the web limit), soft-deletes codes when a promotion downgrades from multi-code/coupon — `promotion.rb:346-363`

**Checkpoint**: Coupon-code bookkeeping is consistent after order completion and promotion edits.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T032 [P] Prefixed IDs on every promotion-domain entity — `has_prefix_id :promo/:prorule/:pact/:coupon/:adj` across `promotion.rb`, `promotion_rule.rb`, `promotion_action.rb`, `coupon_code.rb`, `adjustment.rb`
- [x] T033 Plugin extension point — `PromotionRule.additional_permitted_attributes` / `PromotionAction.additional_permitted_attributes`, merged by `Admin::PromotionsController#subclassed_collection_attributes`
- [x] T034 Store-scoping — `Spree::SingleStoreResource` + `Spree::LegacyMultiStoreSupport` bridge on `Promotion` per `docs/plans/5.6-6.0-single-store-promotions-payment-methods.md`

---

## Dependencies & Execution Order

Foundational STI bases (Phase 2) precede all four user stories. US1 (authoring) and US2 (application) are the two P1 stories and were both required for a usable MVP — a promotion cannot be applied (US2) until it can be authored (US1), so despite both being P1 they are not independent in practice for this domain. US3 (free shipping) and US4 (code lifecycle) layer on top of the same Adjustment/Promotion primitives established in US1/US2.

## Notes

- This tasks.md is a **retroactive record**, not a forward plan — every task cites the file(s) already implementing it.
- Gaps in test coverage (`PromotionHandler::Coupon`, `PromotionHandler::FreeShipping`, `CouponCodesHandler` have no dedicated spec files found; dashboard editor has no located Vitest/Playwright coverage) are called out in spec.md's Migration Notes rather than hidden here.
