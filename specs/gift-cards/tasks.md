---

description: "Task list for Gift Cards & Batches — fully shipped"
---

# Tasks: Gift Cards & Batches

**Status**: Fully shipped

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Nested controllers | `spree/api/app/controllers/spree/api/v3/admin/orders/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/promotions/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Gift Card Core ✅

### Models

- [x] T001 `spree/core/app/models/spree/gift_card.rb` — `has_prefix_id :gc`; `state_machine :state, initial: :active`; events: `cancel`, `redeem`, `partial_redeem`; `include Spree::SingleStoreResource`; `include Spree::Metafields`; money methods: `amount`, `amount_used`, `amount_authorized`; validates `code` uniqueness scoped to `store_id`
- [x] T002 `spree/core/app/models/spree/gift_card_batch.rb` — `has_prefix_id :gcb`; `belongs_to :created_by` (admin_user_class); `has_many :gift_cards`; `after_create :generate_gift_cards`; `validates :codes_count` with batch limit guard; money methods: `amount`
- [x] T003 Factory `spree/core/lib/spree/testing_support/factories/gift_card_factory.rb` — `create`, `active`, `partially_redeemed`, `redeemed`, `canceled` traits
- [x] T004 Factory `spree/core/lib/spree/testing_support/factories/gift_card_batch_factory.rb`

### Serializers

- [x] T005 [P] Store serializer `spree/api/app/serializers/spree/api/v3/gift_card_serializer.rb` — `id`, `code`, `amount`, `currency`, `state`, `expires_at`
- [x] T006 [P] Admin serializer `spree/api/app/serializers/spree/api/v3/admin/gift_card_serializer.rb` — extends Store; adds `amount_used`, `amount_authorized`, `store_id`, `batch_id`, `created_at`, `updated_at`
- [x] T007 Admin serializer `spree/api/app/serializers/spree/api/v3/admin/gift_card_batch_serializer.rb` — `id`, `prefix`, `codes_count`, `amount`, `currency`, `expires_at`, `store_id`, `created_by_id`, timestamps

### Controllers

- [x] T008 `spree/api/app/controllers/spree/api/v3/admin/gift_cards_controller.rb` — full CRUD; `cancel` custom action; `scope` filtered by `current_store`
- [x] T009 `spree/api/app/controllers/spree/api/v3/admin/gift_card_batches_controller.rb` — `index`, `show`, `create`, `destroy`; `scope` filtered by `current_store`
- [x] T010 `spree/api/app/controllers/spree/api/v3/admin/orders/gift_cards_controller.rb` — nested under orders; `index` only
- [x] T011 Store API integration: `apply_gift_card` / `remove_gift_card` in cart controller

### Specs

- [x] T012 `spree/core/spec/models/spree/gift_card_spec.rb` — state machine transitions; `amount_authorized` concurrent hold logic; code uniqueness
- [x] T013 `spree/api/spec/integration/spree/api/v3/admin/gift_cards_spec.rb` — CRUD + cancel + store scoping
- [x] T014 `spree/api/spec/integration/spree/api/v3/admin/gift_card_batches_spec.rb` — create with auto-generation; batch limit validation

### Type Pipeline

- [x] T015 `bundle exec rake typelizer:generate` — `AdminGiftCard`, `AdminGiftCardBatch` types generated
- [x] T016 `cd packages/sdk && pnpm generate:zod`
- [x] T017 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T018 [US1/US2] `packages/dashboard/src/routes/_authenticated/$storeId/promotions/gift-cards.tsx` — list with tabs (All / Active / Redeemed / Canceled); batch create sheet; individual card create sheet; cancel action
- [x] T019 [US1] `packages/dashboard/src/hooks/use-gift-cards.ts` — TanStack Query wrappers for gift cards and batches
- [x] T020 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.giftCards.*`
- [x] T021 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [x] T022 `packages/dashboard/e2e/gift-cards.spec.ts` — create individual card → apply at checkout (simulated) → verify state transition; create batch → verify card count
- [x] T023 Run `pnpm test:e2e` ✅

**Checkpoint**: all integration tests pass ✅; gift card state machine transitions correctly ✅

---

## Phase 2: 6.0 — Status Column Rename (PENDING)

- [ ] T024 Migration: rename `state` column to `status` on `spree_gift_cards` (per `6.0-normalize-state-to-status.md`)
- [ ] T025 Update state machine column: `state_machine :status, initial: :active` (was `:state`)
- [ ] T026 Update `Admin::GiftCardSerializer` — expose `status` (was `state`)
- [ ] T027 Update Ransack allowlist: `status` (was `state`)

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| `state` column name (legacy, not `status`) | Low | Rename to `status` in 6.0 per `6.0-normalize-state-to-status.md`; T024–T027 above |
| No standalone `use-gift-card-batches.ts` hook — batches handled in same hook file | Low | Intentional; batches are tightly coupled to gift card UX; single hook file is appropriate |
