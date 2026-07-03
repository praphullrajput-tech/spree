---

description: "Task list for Store Credits — fully shipped; no dedicated E2E tests"
---

# Tasks: Store Credits

**Status**: Fully shipped; no dedicated E2E tests

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Order concern | `spree/core/app/models/spree/order/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/customers/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core + API + SPA ✅

### Models

- [x] T001 `spree/core/app/models/spree/store_credit.rb` — `has_prefix_id :credit`; `Spree::SingleStoreResource`; `acts_as_paranoid`; three-column balance: `amount`, `amount_used`, `amount_authorized`; action constants: VOID, CANCEL, CREDIT, CAPTURE, ELIGIBLE, AUTHORIZE, ALLOCATION; lifecycle events
- [x] T002 `spree/core/app/models/spree/store_credit_event.rb` — `has_prefix_id :scevt`; immutable audit log; `action`, `amount`, `user_total_amount`, `originator_id`/`originator_type`; `exposed_events` scope (filters ELIGIBLE + AUTHORIZE)
- [x] T003 `spree/core/app/models/spree/store_credit_category.rb` — `has_prefix_id :sccat`; `GIFT_CARD_CATEGORY_NAME` constant; name, description
- [x] T004 `spree/core/app/models/spree/store_credit_type.rb` — `has_prefix_id`; `CREDIT_TYPE_NAME_STORE_CREDIT`, `CREDIT_TYPE_NAME_GIFT_CARD`
- [x] T005 `spree/core/app/models/spree/payment_method/store_credit.rb` — PaymentMethod subclass integrating StoreCredit with checkout payment flow: `authorize`, `capture`, `void`
- [x] T006 `spree/core/app/models/spree/order/store_credit.rb` — order concern: `store_credit_total`, `covered_by_store_credit?`, `using_store_credits?`

### Serializers

- [x] T007 `spree/api/app/serializers/spree/api/v3/admin/store_credit_serializer.rb` — `credit_` prefix ID; amount, amount_used, amount_authorized, balance, expires_at, memo, category, events (via `exposed_events`), timestamps
- [x] T008 `spree/api/app/serializers/spree/api/v3/admin/store_credit_category_serializer.rb` — `sccat_` prefix ID; name, description, timestamps

### Controllers

- [x] T009 `spree/api/app/controllers/spree/api/v3/admin/customers/store_credits_controller.rb` — nested under customers; full CRUD; `void` action
- [x] T010 `spree/api/app/controllers/spree/api/v3/admin/orders/store_credits_controller.rb` — nested under orders; `create` (add store credit to order), `destroy` (remove store credit)
- [x] T011 `spree/api/app/controllers/spree/api/v3/admin/store_credit_categories_controller.rb` — top-level; full CRUD

### Specs

- [x] T012 `spree/core/spec/models/spree/store_credit_spec.rb` — three-column balance arithmetic; authorize → capture flow; void releases authorized; `GIFT_CARD_CATEGORY_NAME` behavior
- [x] T013 `spree/api/spec/integration/spree/api/v3/admin/customers/store_credits_spec.rb` — CRUD; void action
- [x] T014 `spree/api/spec/integration/spree/api/v3/admin/store_credit_categories_spec.rb` — CRUD

### Type Pipeline

- [x] T015 `bundle exec rake typelizer:generate`
- [x] T016 `cd packages/sdk && pnpm generate:zod`
- [x] T017 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T018 Store credit section in `packages/dashboard/src/routes/_authenticated/$storeId/customers/$customerId.tsx` — list credits, add credit dialog, void action, events timeline
- [x] T019 `packages/dashboard/src/hooks/use-customer-store-credits.ts` — TanStack Query wrappers
- [x] T020 `packages/dashboard/src/hooks/use-store-credit-categories.ts` — TanStack Query wrappers
- [x] T021 Store credit categories settings page in `packages/dashboard/src/routes/_authenticated/$storeId/settings/` (or integrated into customer settings)
- [x] T022 Add i18n keys under `admin.store_credits.*` and `admin.store_credit_categories.*` in all locale files

**Checkpoint**: full store credit CRUD + events audit trail; integrated with customer detail; categories management ✅

---

## Phase 2: E2E Coverage (PENDING)

- [ ] T023 `packages/dashboard/e2e/store-credits.spec.ts` — add credit to customer; void credit; view events; add credit to order; remove from order; category CRUD
- [ ] T024 Run `pnpm test:e2e`

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No dedicated E2E tests for store credit flows | Medium | T023–T024; credit management is critical for gift card + loyalty use cases |
| Orders surface (add/remove credit on order) not visually testable without order fixture | Low | E2E setup should seed an order in `placed` status with store credit payment method enabled |
