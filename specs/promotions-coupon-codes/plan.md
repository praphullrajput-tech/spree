# Implementation Plan: Promotions & Coupon Codes

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: 5.6 single-store ownership migration complete; 6.0 join-table drop pending

---

## Summary

Promotions have been a core Spree feature since v1. The significant recent change is the 5.6 migration of `Spree::Promotion` from multi-store (`has_many :stores` via `spree_promotions_stores` join table) to single-store ownership (`belongs_to :store`), mirroring the 5.5 Product migration described in `6.0-channels-catalogs-b2b.md`. The architecture supports pluggable promotion rules (`Spree::PromotionRule` STI) and actions (`Spree::PromotionAction` STI) registered via the `Spree.promotions` configuration object. Coupon codes are first-class records (`Spree::CouponCode`) enabling multi-code bulk generation.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Extension points** | `Spree.promotions.rules` registry + `Spree.promotions.actions` registry — STI subclasses |
| **Single-store** | `Spree::SingleStoreResource` concern (5.6) + `LegacyMultiStoreSupport` bridge |
| **Scope** | Full-stack; 5.6 store migration complete; 6.0 cleanup pending |

---

## Key Decisions

1. **Single-store ownership via FK (5.6).** Promotion gets `belongs_to :store` and includes `Spree::SingleStoreResource` — same pattern as Product (5.5). `LegacyMultiStoreSupport` bridge included unless `SpreeMultiStore` extension is present; multi-store sharing moves to `spree_multi_store`.

2. **Join table survives 5.6, drops in 6.0.** `spree_promotions_stores` is left intact in 5.6 so the extension can overlay it. The 6.0 cleanup migration drops it and enforces `store_id null: false`.

3. **Rule and action types are STI with a config registry.** `Spree::PromotionRule` and `Spree::PromotionAction` follow the same STI + `Spree.promotions.rules` registry pattern as `Spree::Calculator` and `Spree::PaymentMethod`. Plugins add subclasses and register them in an initializer.

4. **`kind` is an integer Rails enum.** `coupon_code: 0, automatic: 1` — a legacy exception to the CLAUDE.md "use string columns" rule. The enum is embedded in the schema; 6.0 may normalize, but that work is not planned.

5. **Multi-code promotions generate codes in `after_commit`.** Bulk code generation is deferred to `after_commit` to avoid blocking the save transaction. A brief window exists where the promotion is saved but codes have not been generated.

6. **`match_policy: "all"` vs `"any"`.** Stored as the string `MATCH_POLICIES = %w[all any]`. All-rules must be satisfied vs any-rule must be satisfied. This controls `eligible?` evaluation across the `promotion_rules` collection.

7. **`Spree.promotions.rules` and `.actions` are the allowlist.** Admin pickers show only registered types. Plugin authors define STI subclasses and call `Spree.promotions.rules << MyRule` in `config.after_initialize`.

8. **`store_id` nullable in 5.6, `null: false` in 6.0.** Mirrors the Product migration: the 5.6 column is nullable so installs that haven't run the backfill don't fail validations.

---

## Constitution Check

- [x] **API-First**: Admin API for promotions/coupon codes precedes SPA consumption
- [x] **Read/Write Symmetry**: Serializer exposes `name`, `kind`, `code`, `match_policy`; controller permits the same
- [x] **Prefixed IDs**: `promo_…` on all promotion IDs; association IDs (`store_id`) returned as prefixed
- [x] **Serializer Hierarchy**: `Admin::PromotionSerializer` extends `V3::PromotionSerializer`
- [x] **Type Pipeline**: Typelizer + Zod regen after serializer changes
- [x] **Security**: CanCanCan `can :manage, Spree::Promotion`; store-scoped via `SingleStoreResource`
- [x] **Namespace**: `Spree::Promotion`, `Spree::PromotionRule`, `Spree::PromotionAction`, `Spree::CouponCode` — all `Spree.base_class` subclasses
- [x] **Plan Conflicts**: Reviewed `5.6-6.0-single-store-promotions-payment-methods.md` — no conflict; this plan IS the store ownership migration for promotions

---

## Project Structure

```text
# Backend — models
spree/core/app/models/spree/promotion.rb
spree/core/app/models/spree/coupon_code.rb
spree/core/app/models/spree/promotion_rule.rb            ← STI base
spree/core/app/models/spree/promotion_action.rb          ← STI base
spree/core/app/models/spree/promotion_category.rb
spree/core/app/models/spree/order_promotion.rb

spree/core/app/models/spree/promotion_rules/           ← STI subclasses
spree/core/app/models/spree/promotion_actions/         ← STI subclasses

# Backend — serializers
spree/api/app/serializers/spree/api/v3/promotion_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/promotion_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/coupon_code_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/promotion_rule_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/promotion_action_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/promotion_category_serializer.rb

# Backend — controllers
spree/api/app/controllers/spree/api/v3/admin/promotions_controller.rb
spree/api/app/controllers/spree/api/v3/admin/coupon_codes_controller.rb
spree/api/app/controllers/spree/api/v3/admin/promotion_rules_controller.rb
spree/api/app/controllers/spree/api/v3/admin/promotion_actions_controller.rb
spree/api/app/controllers/spree/api/v3/admin/promotion_categories_controller.rb

# Frontend
packages/dashboard/src/routes/_authenticated/$storeId/promotions/index.tsx
packages/dashboard/src/routes/_authenticated/$storeId/promotions/new.tsx
packages/dashboard/src/routes/_authenticated/$storeId/promotions/$promotionId.tsx
packages/dashboard/src/hooks/use-promotions.ts
packages/dashboard/e2e/promotions.spec.ts
```

---

## Phase 1: Core Promotions System (✅ Complete)

- `Spree::Promotion` model with STI rules and actions
- `Spree::CouponCode` model — first-class code records
- `Spree::PromotionRule` and `Spree::PromotionAction` STI bases with built-in subclasses
- Store API: `apply_coupon_code` / `remove_coupon_code` on cart
- Admin API: full CRUD for promotions, rules, actions, categories, coupon codes
- Admin SPA routes and hooks shipped

---

## Phase 2: Single-Store Ownership Migration — 5.6 (✅ Complete)

- Added `store_id` column (nullable) + `belongs_to :store` to `spree_promotions`
- Included `Spree::SingleStoreResource` concern (replaces `StoreScopedResource`)
- Included `Spree::LegacyMultiStoreSupport` bridge (unless `SpreeMultiStore` defined)
- Backfill rake task: assigns `store_id` to existing promotions from their join-table entries
- Deprecated `store_ids=` and `stores=` accessors with loud `Spree::Deprecation` warnings
- Deleted `ResourceController store_ids=` seam; deprecated `StoreScopedResource`
- `spree_promotions_stores` join table left intact for the extension

---

## Phase 3: 6.0 Cleanup (PENDING)

- Migration: enforce `store_id null: false` on `spree_promotions`
- Migration: drop `spree_promotions_stores` join table
- Remove `LegacyMultiStoreSupport` bridge from `Spree::Promotion`
- Normalize `kind` from integer enum to string column (if planned — not confirmed)

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| `kind` as integer Rails enum | Legacy from pre-CLAUDE.md era; schema already in use | Rename requires a migration + data transform; deferred to 6.0 if prioritized |
| `after_commit :generate_coupon_codes` async generation | Avoids blocking save transaction on bulk code creation | Synchronous generation would make large batches timeout in web requests |
