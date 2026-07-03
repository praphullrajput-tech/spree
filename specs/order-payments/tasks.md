---

description: "Task list for Order Payments — models + API shipped; dashboard SPA pending"
---

# Tasks: Order Payments

**Status**: Phase 1 (models + API) fully shipped; Phase 2 (SPA) pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Nested controllers | `spree/api/app/controllers/spree/api/v3/admin/orders/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/orders/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Models + API ✅

### Models

- [x] T001 `spree/core/app/models/spree/payment.rb` — `has_prefix_id :py`; state machine: `checkout → processing → pending → completed / failed / void / invalid`; `amount decimal`; `captured_amount decimal`; polymorphic `source` (`source_type`, `source_id`); `avs_response`, `cvv_response_code`; `belongs_to :payment_method`; `belongs_to :order`; `include Spree::Metafields`; `publishes_lifecycle_events`
- [x] T002 `spree/core/app/models/spree/payment/processing.rb` — `capture!`, `void!`, `purchase!` gateway delegation; returns updated payment
- [x] T003 `spree/core/app/models/spree/payment/webhooks.rb` — async gateway webhook callbacks; transitions payment state on confirmation
- [x] T004 `spree/core/app/models/spree/payment/gateway_options.rb` — builds options hash for gateway calls (billing address, currency, etc.)
- [x] T005 `spree/core/app/models/spree/payment_session.rb` — `has_prefix_id :ps`; state machine: `pending → processing → completed / failed / canceled / expired`; `external_id` for gateway reference; `belongs_to :payment`
- [x] T006 `spree/core/app/models/spree/payment_setup_session.rb` — `has_prefix_id :pss`; state machine; polymorphic `payment_source`; `belongs_to :payment_method`; `belongs_to :user` (Spree.user_class)
- [x] T007 `spree/core/app/models/spree/credit_card.rb` — `has_prefix_id :card`; paranoid; `belongs_to :payment_method`; `belongs_to :user` (optional); `last_digits`, `month`, `year`, `brand`, `manual_entry`; acts as polymorphic payment source

### Serializers

- [x] T008 [P] `spree/api/app/serializers/spree/api/v3/admin/payment_serializer.rb` — `id` (py_…), `order_id` (prefixed), `payment_method_id` (pm_…), `amount`, `captured_amount`, `status` (state), `avs_response`, `cvv_response_code`, `source_type`, `source_id`, `number`, `created_at`, `updated_at`

### Controllers

- [x] T009 `spree/api/app/controllers/spree/api/v3/admin/orders/payments_controller.rb` — `index`, `show`, `create`; custom actions: `capture`, `void`; scoped to `order.payments`; `create` supports `source_id` for off-session charges

### Routes

- [x] T010 Nested routes under `resources :orders`: `resources :payments` with `member { post :capture, :void }`

### Specs

- [x] T011 `spree/core/spec/models/spree/payment_spec.rb` — state machine transitions; `captured_amount` updates on capture; `avs_response` stored; polymorphic source accepts CreditCard and StoreCredit
- [x] T012 `spree/api/spec/integration/spree/api/v3/admin/orders/payments_spec.rb` — list; show; capture transitions state; void rejects completed payments with 422

### Type Pipeline

- [x] T013 `bundle exec rake typelizer:generate` — `AdminPayment` type generated
- [x] T014 `cd packages/sdk && pnpm generate:zod`
- [x] T015 `bundle exec rake rswag:specs:swaggerize`

**Checkpoint**: admin can list payments on an order, capture authorized payments, void pending payments ✅

---

## Phase 2: SPA Dashboard (PENDING)

### Hooks

- [ ] T016 [US1] Create `packages/dashboard/src/hooks/use-order-payments.ts` — TanStack Query: list payments for order, create payment, capture, void

### Frontend

- [ ] T017 [US1/US2/US3] Payments panel on order detail page (`$orderId.tsx`) — payment history timeline; capture/void buttons (state-aware: shown only when transition is valid); AVS/CVV response display
- [ ] T018 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.orders.payments.*` (status labels, capture/void buttons, amount labels, toast messages)
- [ ] T019 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [ ] T020 `packages/dashboard/e2e/order-payments.spec.ts` — open order → verify payments panel shows payment → capture → verify status changes to completed

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No dashboard UI for capture/void — legacy admin only | Critical | T016–T020 above; support agents must use legacy Rails admin to manage payment state |
| No E2E test coverage | High | T020 above |
| `PaymentSession` not exposed in admin API | Low | Intentional — sessions are managed by Store API checkout; admin only needs Payment level visibility |
| `PaymentSetupSession` not exposed in admin API | Low | Intentional — setup sessions are customer-facing tokenization flows |
