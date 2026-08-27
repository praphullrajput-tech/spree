# Implementation Plan: Promotions & Discounts

**Branch**: `004-promotions-and-discounts` | **Date**: 2026-08-24 | **Spec**: `specs/004-promotions-and-discounts/spec.md`

**Input**: Feature specification from `/specs/004-promotions-and-discounts/spec.md`

**Note**: This is a **brownfield migration** plan — the feature is already implemented. This document reverse-engineers the design decisions from the existing code rather than proposing new ones.

## Summary

Spree's promotion engine is a rule/action STI system: a `Spree::Promotion` owns polymorphic `PromotionRule` rows (eligibility) and `PromotionAction` rows (effect), combined via a `match_policy`. Effects are realized as `Spree::Adjustment` records computed through a shared `Calculator`, or as free line items / free shipping. Coupon-code entry, validation, and removal are orchestrated by `Spree::PromotionHandler::Coupon`; automatic free-shipping promotions activate separately via `Spree::PromotionHandler::FreeShipping`. The Admin API exposes full CRUD with nested rule/action reconciliation in one request; the Store API exposes a minimal read-only view. The admin SPA (`packages/dashboard`) provides the promotion list/detail/editor UI on top of the Admin API.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`) and TypeScript (React SPA, `packages/dashboard`)

**Primary Dependencies**: Backend: CanCanCan (`Spree::Security::Promotions`, conditional), Ransack (`whitelisted_ransackable_attributes` on `Promotion`/`CouponCode`), Alba serializers, `state_machines-activerecord` (`Adjustment#state`), `paranoia` (`PromotionAction`, `CouponCode` soft delete), ActiveJob (`Spree::CouponCodes::BulkGenerateJob`). Frontend: TanStack Router/Query, React Hook Form + Zod, shadcn/ui.

**Storage**: PostgreSQL/MySQL/SQLite via ActiveRecord — `spree_promotions`, `spree_promotion_rules`, `spree_promotion_actions`, `spree_coupon_codes`, `spree_adjustments`, `spree_order_promotions` (join), `spree_promotion_action_line_items`.

**Testing**: RSpec + Factory Bot (`spree/core/spec/models/spree/promotion_rule_spec.rb`, `spree/core/spec/models/spree/adjustable/adjuster/promotion_spec.rb`) — no Vitest/Playwright coverage located for the promotion editor specifically during this migration.

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`) consumed by a Spree host app; `packages/dashboard` React SPA against the Admin API.

**Project Type**: Monorepo — `spree/core`, `spree/api`, `packages/dashboard` (+ generated `packages/sdk`/`packages/admin-sdk` types).

**Performance Goals**: N/A — not specified in source; promotion eligibility runs synchronously per order update (`eligible_rules` iterates in-memory over loaded rules, no documented SLA).

**Constraints**: Coupon code bulk-generation defers to a background job above `Spree::Config.coupon_codes_web_limit` to avoid blocking the request that created/updated the promotion (`Promotion#generate_coupon_codes`).

**Scale/Scope**: 4 promotion action types, 12 promotion rule types (extensible by plugins via `additional_permitted_attributes`), single-store scoped.

## Constitution Check

*Retroactive check against the as-built implementation — this is a migration, not new design.*

- **I. Module Boundaries**: Pass. `spree/core` owns the STI hierarchies and handlers; `spree/api` owns controller/serializers; `packages/dashboard` consumes only the Admin API (via `use-promotions.ts`, not raw model access). Plugin extension is via `additional_permitted_attributes` (a documented extension point), not direct boundary-crossing.
- **II. Admin API Is the Only Frontend Data Source**: Pass. The dashboard's promotion editor reads/writes exclusively through `Admin::PromotionsController`; no server-rendered HTML or direct model access found in `packages/dashboard`.
- **III. Read/Write Field Symmetry**: Pass. `Admin::PromotionSerializer` attributes (`name, description, code, path, starts_at, expires_at, usage_limit, match_policy, kind, multi_codes, number_of_codes, code_prefix, promotion_category_id, metadata, action_ids, rule_ids`) line up with `PromotionsController#permitted_attributes` (`name, description, code, path, starts_at, expires_at, usage_limit, match_policy, kind, multi_codes, number_of_codes, code_prefix, promotion_category_id, rules, actions`) — `action_ids`/`rule_ids` are read-only computed views of the writable `actions`/`rules` nested collections, which is the documented pattern for association fields.
- **IV. Test-Backed**: Partial. `promotion_rule_spec.rb` and `adjustable/adjuster/promotion_spec.rb` exist for rule eligibility and the adjuster path. No RSpec found for `PromotionHandler::Coupon`, `PromotionHandler::FreeShipping`, or `Spree::CouponCodes::CouponCodesHandler` in the reviewed files; no Vitest/Playwright found for the dashboard promotion editor. Flagged in spec.md Migration Notes — not a blocker for this migration (retroactive documentation), but a real gap for future changes to this feature.
- **V. Translations and Prefixed IDs**: Pass on prefixed IDs (`has_prefix_id :promo/:prorule/:pact/:coupon/:adj` on every entity; serializer `action_ids`/`rule_ids` use `.prefixed_id`). Dashboard i18n usage not verified line-by-line for this migration (see spec.md Migration Notes).
- **VI. `docs/plans/` for Architectural Changes**: N/A for this migration itself (no new architecture proposed). Forward-looking: `docs/plans/6.0-split-adjustments.md` will replace the polymorphic `Spree::Adjustment` this feature depends on — that plan's "Constraints on Current Work" apply to any future change here.

No violations requiring Complexity Tracking — this plan documents existing, already-shipped code.

## Project Structure

### Documentation (this feature)

```text
specs/004-promotions-and-discounts/
├── plan.md              # This file
├── spec.md              # Reverse-engineered specification
└── tasks.md              # Reverse-engineered task breakdown (all marked complete)
```

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/
├── app/models/spree/promotion.rb                              # Spree::Promotion — kind, match_policy, coupon codes, activate/deactivate/eligible?
├── app/models/spree/promotion_rule.rb                          # STI base — applicable?/eligible?, additional_permitted_attributes
├── app/models/spree/promotion_action.rb                        # STI base — perform, free_shipping?, additional_permitted_attributes
├── app/models/spree/promotion/rules/{item_total,product,taxon,user,user_logged_in,one_use_per_user,first_order,country,currency,market,channel,customer_group,option_value}.rb
├── app/models/spree/promotion/actions/{create_adjustment,create_item_adjustments,create_line_items,free_shipping}.rb
├── app/models/spree/promotion_handler/coupon.rb                # apply/remove coupon codes on an order
├── app/models/spree/promotion_handler/free_shipping.rb         # activates automatic FreeShipping promotions
├── app/models/spree/coupon_code.rb                              # disposable per-order code, unused/used state machine
├── app/models/spree/adjustment.rb                               # financial record of a promotion effect
├── app/models/concerns/spree/adjustment_source.rb               # create_adjustment/create_unique_adjustment(s), cleanup on source destroy
├── app/models/concerns/spree/calculated_adjustments.rb          # calculator association + calculator_type=/assign_calculator_attributes
├── app/services/spree/coupon_codes/coupon_codes_handler.rb      # marks codes used/released at order completion
├── app/services/spree/coupon_codes/bulk_generate.rb              # inline bulk code generation (referenced, not reviewed)
├── app/jobs/spree/coupon_codes/bulk_generate_job.rb               # async bulk code generation above web_limit (referenced, not reviewed)
└── spec/models/spree/{promotion_rule_spec.rb,adjustable/adjuster/promotion_spec.rb}

# spree/api — Store & Admin REST API v3
spree/api/
├── app/controllers/spree/api/v3/admin/promotions_controller.rb  # full CRUD + nested rules/actions reconciliation
├── app/serializers/spree/api/v3/promotion_serializer.rb          # Store — name, description, code only
├── app/serializers/spree/api/v3/admin/promotion_serializer.rb    # Admin — extends Store + operational fields
├── app/serializers/spree/api/v3/admin/promotion_rule_serializer.rb
├── app/serializers/spree/api/v3/admin/promotion_action_serializer.rb
└── config/routes.rb (L252 resources :promotions)

# packages/dashboard — admin SPA routes/forms
packages/dashboard/src/
├── routes/_authenticated/$storeId/promotions/$promotionId.tsx
├── tables/promotions.tsx
├── schemas/promotion.ts
├── hooks/use-promotions.ts
└── components/spree/promotion-editors/promotion-form.tsx

# packages/sdk / packages/admin-sdk — generated types (regenerated, not hand-written)
packages/admin-sdk/src/types/generated/{PromotionRule,PromotionAction,CouponCode}.ts
packages/sdk/src/zod/generated/Discount.ts
```

**Structure Decision**: Full-stack feature spanning `spree/core` (domain + handlers), `spree/api` (Admin CRUD + Store read-only), and `packages/dashboard` (editor UI) — three of the six Module Impact rows apply; `dashboard-ui`/`dashboard-core` are untouched (no new shared primitives or registries needed for this feature).

## Complexity Tracking

No Constitution violations identified — table omitted per template instructions.
