---

description: "Task list for Store Credits & Gift Cards (brownfield migration — already implemented)"
---

# Tasks: Store Credits & Gift Cards

**Input**: Design documents from `specs/009-store-credits-and-gift-cards/`

**Prerequisites**: plan.md, spec.md

**Tests**: Existing RSpec/API-integration coverage assumed present per repo convention; not re-verified line-by-line in this migration (see spec.md Migration Notes).

**Organization**: Tasks are grouped by user story, mirroring spec.md. All tasks below are marked complete — this is a reverse-engineered record of already-shipped work, not a forward implementation plan.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core` and `spree/api` gems load `Spree::StoreCredit`, `Spree::GiftCard`, `Spree::GiftCardBatch` without error
- [x] T002 [P] Baseline backend: `cd spree/core && bundle exec rspec` covers store credit / gift card models
- [x] T003 [P] Baseline frontend: `pnpm typecheck && pnpm lint` passes for `packages/dashboard` gift-card route

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 [spree/core] `spree_store_credits`, `spree_store_credit_events`, `spree_store_credit_categories`, `spree_store_credit_types` tables (migrations pre-existing)
- [x] T005 [spree/core] `spree_gift_cards`, `spree_gift_card_batches` tables (migrations pre-existing)
- [x] T006 [spree/core] `Spree::StoreCredit < Spree.base_class` with `has_prefix_id :credit`, `Spree::SingleStoreResource`, `Spree::Metafields`, `Spree::Metadata`, `acts_as_paranoid` — `spree/core/app/models/spree/store_credit.rb`
- [x] T007 [spree/core] `Spree::GiftCard < Spree.base_class` with `has_prefix_id :gc`, `Spree::SingleStoreResource`, `Spree::Metafields`, state machine (`active`/`partially_redeemed`/`redeemed`/`canceled`) — `spree/core/app/models/spree/gift_card.rb`
- [x] T008 [spree/core] `Spree::GiftCardBatch < Spree.base_class` with `has_prefix_id :gcb`, `has_many :gift_cards, dependent: :destroy` — `spree/core/app/models/spree/gift_card_batch.rb`
- [x] T009 [spree/api] Ransack allowlists: `StoreCredit.whitelisted_ransackable_attributes = %w[user_id created_by_id amount currency type_id]`; `GiftCard.whitelisted_ransackable_attributes/_associations/_scopes` (code, user_id, state, gift_card_batch_id, created_by_id / users, orders, batch / active, expired, redeemed, partially_redeemed)
- [x] T010 [packages/dashboard] i18n keys for gift card sheet/table/toasts and store credit messages (`admin.messages.store_credit_saved`, `admin.messages.store_credit_removed`) in `packages/dashboard/src/locales/en.json`

**Checkpoint**: Foundation complete — models, tables, Ransack allowlists, i18n keys all shipped.

---

## Phase 3: User Story 1 - Admin issues a store credit to a customer (Priority: P1) 🎯 MVP

### Implementation for User Story 1

- [x] T011 [US1] `Spree::StoreCredit` lifecycle validations (`amount_used_less_than_or_equal_to_amount`, `amount_authorized_less_than_or_equal_to_amount`, `validate_no_amount_used` before destroy) — `spree/core/app/models/spree/store_credit.rb`
- [x] T012 [US1] Legacy admin controller `Spree::Admin::StoreCreditsController` (create/update/destroy nested under customer) — `spree/admin/app/controllers/spree/admin/store_credits_controller.rb`
- [x] T013 [US1] Admin API `Admin::Customers::StoreCreditsController` (`create`/`update`/`destroy`, blocks changes once `amount_used.positive?`) — `spree/api/app/controllers/spree/api/v3/admin/customers/store_credits_controller.rb`
- [x] T014 [US1] `V3::Admin::StoreCreditSerializer` extending `V3::StoreCreditSerializer` with admin-only fields (category, created_by, memo, timestamps)
- [x] T015 [US1] SPA hooks `useCreateCustomerStoreCredit`/`useUpdateCustomerStoreCredit`/`useDeleteCustomerStoreCredit` — `packages/dashboard/src/hooks/use-customer-store-credits.ts`
- [x] T016 [US1] `packages/dashboard/src/hooks/use-store-credit-categories.ts` for category dropdown data

**Checkpoint**: Store credit CRUD functional via both legacy admin and Admin API v3.

---

## Phase 4: User Story 2 - Customer applies store credit to an order (Priority: P1)

### Implementation for User Story 2

- [x] T017 [US2] `Spree::Order::StoreCredit` concern — `add_store_credit_payments`, `remove_store_credit_payments`, `total_applied_store_credit`, `covered_by_store_credit?`, display helpers — `spree/core/app/models/spree/order/store_credit.rb`
- [x] T018 [US2] `Spree.checkout_add_store_credit_service` / `Spree.checkout_remove_store_credit_service` dependency-registry services (invoked by both Store and Admin order endpoints)
- [x] T019 [US2] `Store::Carts::StoreCreditsController` (`create`/`destroy`, requires authentication) — `spree/api/app/controllers/spree/api/v3/store/carts/store_credits_controller.rb`
- [x] T020 [US2] `Admin::Orders::StoreCreditsController` (`create`/`destroy`) — `spree/api/app/controllers/spree/api/v3/admin/orders/store_credits_controller.rb`
- [x] T021 [US2] `authorize`/`capture`/`void`/`credit` lifecycle methods on `Spree::StoreCredit` backing the store-credit `Spree::PaymentMethod`

**Checkpoint**: Store credit can be applied to and removed from orders via Store and Admin API.

---

## Phase 5: User Story 3 - Admin bulk-issues gift cards via a batch (Priority: P2)

### Implementation for User Story 3

- [x] T022 [US3] `Spree::GiftCardBatch#generate_gift_cards` — inline vs. `Spree::GiftCards::BulkGenerateJob.perform_later` split on `Spree::Config[:gift_card_batch_web_limit]`
- [x] T023 [US3] `Spree::GiftCards::BulkGenerateJob` — `spree/core/app/jobs/spree/gift_cards/bulk_generate_job.rb`
- [x] T024 [US3] `Admin::GiftCardBatchesController` (`index`/`show`/`create`) — `spree/api/app/controllers/spree/api/v3/admin/gift_card_batches_controller.rb`
- [x] T025 [US3] `V3::Admin::GiftCardBatchSerializer` / `V3::GiftCardBatchSerializer`
- [x] T026 [US3] SPA `useCreateGiftCardBatch` hook + batch-creation form path in gift cards sheet — `packages/dashboard/src/hooks/use-gift-cards.ts`, `packages/dashboard/src/schemas/gift-card.ts` (`giftCardBatchValuesToParams`, `BATCH_LIMIT`)

**Checkpoint**: Bulk gift card issuance functional inline and asynchronously, with SPA batch form.

---

## Phase 6: User Story 4 - Customer redeems a gift card on an order (Priority: P1)

### Implementation for User Story 4

- [x] T027 [US4] `Spree::Order::GiftCard` concern — `apply_gift_card`/`remove_gift_card` — `spree/core/app/models/spree/order/gift_card.rb`
- [x] T028 [US4] `Spree::GiftCard` state machine + `after_redeem`/`publish_gift_card_redeemed_event`/`publish_gift_card_partially_redeemed_event` callbacks
- [x] T029 [US4] `has_many :store_credits, class_name: 'Spree::StoreCredit', as: :originator` linking redemption to spendable balance
- [x] T030 [US4] `Store::Carts::GiftCardsController` (`create`/`destroy`, code lookup + expired/redeemed/not-found error codes) — `spree/api/app/controllers/spree/api/v3/store/carts/gift_cards_controller.rb`
- [x] T031 [US4] `Admin::Orders::GiftCardsController` (mirrors Store cart controller for admin-applied gift cards) — `spree/api/app/controllers/spree/api/v3/admin/orders/gift_cards_controller.rb`
- [x] T032 [US4] `V3::GiftCardSerializer` — `display_code`, `display_state`-derived `status`, hide-prices-aware money attributes

**Checkpoint**: Gift card redemption functional on both Store and Admin order/cart surfaces.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T033 [P] `Admin::GiftCardsController` full CRUD (`index`/`show`/`create`/`update`/`destroy`) — `spree/api/app/controllers/spree/api/v3/admin/gift_cards_controller.rb`
- [x] T034 [P] `Store::Customer::{GiftCards,StoreCredits}Controller` — customer-facing read/list endpoints
- [x] T035 [P] `Admin::StoreCreditCategoriesController` + `V3::Admin::StoreCreditCategorySerializer`
- [x] T036 `Spree::CSV::GiftCardPresenter` for CSV export (`GiftCard#to_csv`)
- [x] T037 SPA `tables/gift-cards.tsx` table-registry definition (status, code, amount, expiry columns) and the `promotions/gift-cards.tsx` route (list, create single, create batch, edit, delete sheets)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: models/tables/allowlists before any controller work.
- **User Story 1** (store credit CRUD) has no dependency on other stories.
- **User Story 2** (apply to order) depends on User Story 1's `Spree::StoreCredit` existing, but is independently testable via the checkout services.
- **User Story 3** (gift card batches) depends on `Spree::GiftCard` (Foundational) but not on User Stories 1/2.
- **User Story 4** (gift card redemption) depends on both `Spree::GiftCard` (Foundational) and `Spree::StoreCredit` (US1) since redemption creates a `StoreCredit` record — this is the one cross-story integration point in the codebase.
- **Polish (Phase 7)**: full CRUD surfaces and SPA table registration layer on top of all four stories.

## Notes

- This tasks.md is a **record of completed work**, produced during a brownfield `/speckit.brownfield.migrate` pass — all items are checked `[x]` because the feature is already live in the codebase.
- No new tests, migrations, or code were written as part of generating this document.
