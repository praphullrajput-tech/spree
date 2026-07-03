---

description: "Task list for Promotions & Coupon Codes — core system complete; 5.6 single-store migration complete; 6.0 join-table drop pending"
---

# Tasks: Promotions & Coupon Codes

**Status**: Core promotions complete; 5.6 single-store migration complete; 6.0 join-table cleanup pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Store serializers | `spree/api/app/serializers/spree/api/v3/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/promotions/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core Promotions System ✅

### Models

- [x] T001 `spree/core/app/models/spree/promotion.rb` — `has_prefix_id :promo`; `enum :kind, { coupon_code: 0, automatic: 1 }`; `MATCH_POLICIES`; associations for rules, actions, coupon_codes, order_promotions; `normalizes :code, :path, :name`; lifecycle event publishing
- [x] T002 `spree/core/app/models/spree/coupon_code.rb` — `belongs_to :promotion`; `code`, `usage_limit`, `times_used`; uniqueness on `(code, promotion_id)`
- [x] T003 `spree/core/app/models/spree/promotion_rule.rb` — STI base; `belongs_to :promotion`; `eligible?` method; `whitelisted_ransackable_attributes`
- [x] T004 `spree/core/app/models/spree/promotion_action.rb` — STI base; `belongs_to :promotion`; `perform` method
- [x] T005 `spree/core/app/models/spree/promotion_category.rb` — `name`, `has_many :promotions`
- [x] T006 `spree/core/app/models/spree/order_promotion.rb` — join model; `belongs_to :order`, `belongs_to :promotion`
- [x] T007 Built-in `Spree::PromotionRules::*` subclasses: `ItemTotal`, `Product`, `Customer`, `FirstOrder`, `UserLoggedIn`, `OptionValue`, `Taxon`, `Country`, `Store` — registered in `Spree.promotions.rules`
- [x] T008 Built-in `Spree::PromotionActions::*` subclasses: `CreateAdjustment`, `CreateItemAdjustments`, `FreeShipping` — registered in `Spree.promotions.actions`

### Serializers

- [x] T009 [P] Store serializer `spree/api/app/serializers/spree/api/v3/promotion_serializer.rb` — `id`, `name`, `kind`, `code`, `multi_codes`, `match_policy`, `usage_limit`, `starts_at`, `expires_at`, `path`
- [x] T010 [P] Admin serializer `spree/api/app/serializers/spree/api/v3/admin/promotion_serializer.rb` — extends Store; adds `number_of_codes`, `store_id`, `promotion_category_id`, embedded rules/actions, timestamps
- [x] T011 Admin serializer `spree/api/app/serializers/spree/api/v3/admin/coupon_code_serializer.rb`
- [x] T012 Admin serializer `spree/api/app/serializers/spree/api/v3/admin/promotion_rule_serializer.rb`
- [x] T013 Admin serializer `spree/api/app/serializers/spree/api/v3/admin/promotion_action_serializer.rb`
- [x] T014 Admin serializer `spree/api/app/serializers/spree/api/v3/admin/promotion_category_serializer.rb`

### Controllers

- [x] T015 `spree/api/app/controllers/spree/api/v3/admin/promotions_controller.rb` — full CRUD; `scope` filtered by `current_store`
- [x] T016 `spree/api/app/controllers/spree/api/v3/admin/coupon_codes_controller.rb` — nested under promotions; `create`, `destroy`
- [x] T017 `spree/api/app/controllers/spree/api/v3/admin/promotion_rules_controller.rb` — nested under promotions; CRUD
- [x] T018 `spree/api/app/controllers/spree/api/v3/admin/promotion_actions_controller.rb` — nested under promotions; CRUD
- [x] T019 `spree/api/app/controllers/spree/api/v3/admin/promotion_categories_controller.rb` — full CRUD
- [x] T020 Store API: `spree/api/app/controllers/spree/api/v3/cart_controller.rb` — `apply_coupon_code`, `remove_coupon_code` actions

### Type Pipeline

- [x] T021 `bundle exec rake typelizer:generate` — `AdminPromotion` type generated
- [x] T022 `cd packages/sdk && pnpm generate:zod`
- [x] T023 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T024 [US1] `packages/dashboard/src/routes/_authenticated/$storeId/promotions/index.tsx` — `<ResourceTable>` with kind filter; create sheet
- [x] T025 [US1] `packages/dashboard/src/routes/_authenticated/$storeId/promotions/new.tsx` — create form
- [x] T026 [US1] `packages/dashboard/src/routes/_authenticated/$storeId/promotions/$promotionId.tsx` — edit page with rules/actions/coupon codes tabs
- [x] T027 [US1] `packages/dashboard/src/hooks/use-promotions.ts` — TanStack Query wrappers
- [x] T028 [US1] Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.promotions.*`
- [x] T029 [US1] Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [x] T030 `packages/dashboard/e2e/promotions.spec.ts` — create promotion → add rule → add action → verify discount → delete
- [x] T031 Run `pnpm test:e2e` ✅

**Checkpoint**: promotions appear store-scoped ✅; coupon application returns 422 on expired/used codes ✅

---

## Phase 2: Single-Store Ownership Migration — 5.6 ✅

- [x] T032 Migration: add `store_id` (string, nullable) to `spree_promotions`; add index
- [x] T033 Replace `include Spree::StoreScopedResource` with `include Spree::SingleStoreResource` on `Spree::Promotion`; add `belongs_to :store`; add `validates :store, presence: true`
- [x] T034 Add `Spree::Promotion::LegacyMultiStoreSupport` module (mirrors `Spree::Product::LegacyMultiStoreSupport`); include unless `SpreeMultiStore` defined
- [x] T035 Deprecate `store_ids=`, `stores=`, `stores` accessors with `Spree::Deprecation.warn`
- [x] T036 Backfill rake task `spree:promotions:backfill_store_id` — assigns `store_id` from join table; loud per-record warning on shared records
- [x] T037 Delete `ResourceController store_ids=` seam; deprecate `StoreScopedResource`
- [x] T038 Integration tests updated to verify store-scoped list responses

**Checkpoint**: Promotions no longer appear in cross-store API responses ✅

---

## Phase 3: 6.0 Cleanup (PENDING)

- [ ] T039 Migration: enforce `store_id null: false` on `spree_promotions`
- [ ] T040 Migration: drop `spree_promotions_stores` join table
- [ ] T041 Remove `LegacyMultiStoreSupport` from `Spree::Promotion`
- [ ] T042 Remove `StoreScopedResource` concern (last include removed)

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| `kind` stored as integer enum (not string) | Low | Legacy exception; normalize in 6.0 migration if prioritized — add to `6.0-normalize-state-to-status.md` scope or create a new plan |
| No store API endpoint to list available promotions | Low | Automatic promotions apply silently; no storefront "available promotions" listing currently |
| `generate_coupon_codes` runs in `after_commit` — brief window where promotion exists but codes don't | Low | Documented behavior; no fix required; API callers should handle empty coupon_codes gracefully |
