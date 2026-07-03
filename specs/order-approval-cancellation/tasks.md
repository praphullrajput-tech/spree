---

description: "Task list for Order Approval & Cancellation — 5.5 models shipped; API controllers + SPA pending"
---

# Tasks: Order Approval & Cancellation

**Status**: 5.5 models + service extensions shipped; API controllers + SPA pending; 6.0 denormalized column drop pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Services | `spree/core/app/services/spree/orders/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Nested controllers | `spree/api/app/controllers/spree/api/v3/admin/orders/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: 5.5 — Models + Service Extensions ✅

### Models

- [x] T001 `spree/core/app/models/spree/order_cancellation.rb` — `has_prefix_id :cncl`; `belongs_to :order` (class_name `Spree::Order`); polymorphic `canceled_by` (class_name removed — accepts AdminUser/User); validates `reason` presence (Shopify enum strings: `customer declined fraud inventory staff other expired`); `include Spree::Metadata`; no state machine (append-only history model)
- [x] T002 `spree/core/app/models/spree/order_approval.rb` — `has_prefix_id :appr`; `belongs_to :order`; polymorphic `approver`; validates `status` inclusion in `%w[pending approved rejected]`; `level` string (nullable in 5.5); `decided_at` datetime (nullable when pending); `include Spree::Metadata`
- [x] T003 Update `spree/core/app/models/spree/order.rb` — add `has_many :cancellations, class_name: 'Spree::OrderCancellation', dependent: :destroy`; `has_many :approvals, class_name: 'Spree::OrderApproval', dependent: :destroy`; add `requires_approval?` method (default: `false`; overridable)

### Migrations

- [x] T004 Migration `*_create_spree_order_cancellations.rb` — create table with all columns; indexes: `order_id`, `(canceled_by_id, canceled_by_type)`, `created_at`
- [x] T005 Migration `*_create_spree_order_approvals.rb` — create table with all columns; indexes: `(order_id, status)`, `(approver_id, approver_type)`, `created_at`

### Service Extensions

- [x] T006 `spree/core/app/services/spree/orders/cancel.rb` — extend with optional kwargs: `reason: 'other'`, `note:`, `restock_items: false`, `refund_payments: false`, `refund_amount:`, `notify_customer: false`; all backward-compatible (existing callers work); creates `Spree::OrderCancellation` record inside existing transaction; updates denormalized columns `canceled_at`, `canceler_id`
- [x] T007 `spree/core/app/services/spree/orders/approve.rb` — extend with `note:`, `approver:`, `level:`; creates `Spree::OrderApproval { status: 'approved' }` record; updates denormalized `approved_at`, `approver_id`

### Specs

- [x] T008 `spree/core/spec/models/spree/order_cancellation_spec.rb` — `reason` presence validation; polymorphic `canceled_by` accepts AdminUser and User; append-only (second cancel creates second record, not updates first)
- [x] T009 `spree/core/spec/models/spree/order_approval_spec.rb` — `status` inclusion validation; `decided_at` set on approve; `level` nullable in 5.5
- [x] T010 `spree/core/spec/services/spree/orders/cancel_spec.rb` (updated) — new kwargs accepted; old callers unchanged; restock creates StockMovements; refund issues refunds; all within one transaction; cancellation record created

**Checkpoint**: models + migrations exist ✅; `Spree::Orders::Cancel` accepts new kwargs ✅; old callers unaffected ✅

---

## Phase 2: API + SPA (PENDING)

### Serializers

- [ ] T011 [P] Create `spree/api/app/serializers/spree/api/v3/admin/order_cancellation_serializer.rb` — `id` (cncl_…), `order_id` (prefixed), `reason`, `note`, `restock_items`, `refund_payments`, `refund_amount`, `notify_customer`, `canceled_by_id`, `canceled_by_type`, `created_at`
- [ ] T012 [P] Create `spree/api/app/serializers/spree/api/v3/admin/order_approval_serializer.rb` — `id` (appr_…), `order_id` (prefixed), `status`, `level`, `note`, `approver_id`, `approver_type`, `decided_at`, `created_at`

### Controllers

- [ ] T013 [US1] Create `spree/api/app/controllers/spree/api/v3/admin/orders/cancellations_controller.rb` — `index`, `show`, `create`; `scope` = `order.cancellations`; `create` delegates to `Spree::Orders::Cancel` service
- [ ] T014 [US2] Create `spree/api/app/controllers/spree/api/v3/admin/orders/approvals_controller.rb` — `index`, `show`, `create`; `scope` = `order.approvals`; `create` delegates to `Spree::Orders::Approve` service

### Routes

- [ ] T015 Add nested routes under `resources :orders`: `resources :cancellations, only: [:index, :show, :create]`; `resources :approvals, only: [:index, :show, :create]`

### Integration Specs

- [ ] T016 Write `spree/api/spec/integration/spree/api/v3/admin/orders/cancellations_spec.rb` — happy path: create with reason/restock/refund; 422 on blank reason; history list shows multiple records
- [ ] T017 Write `spree/api/spec/integration/spree/api/v3/admin/orders/approvals_spec.rb` — approve sets `decided_at`; reject returns `status: "rejected"`; list shows approval history
- [ ] T018 Run `bundle exec rake rswag:specs:swaggerize`

### Type Pipeline

- [ ] T019 `bundle exec rake typelizer:generate` — `AdminOrderCancellation`, `AdminOrderApproval` types generated
- [ ] T020 `cd packages/sdk && pnpm generate:zod`

### Frontend

- [ ] T021 [US1] Create `packages/dashboard/src/hooks/use-order-cancellations.ts` — TanStack Query: list cancellations for order, create cancellation
- [ ] T022 [US2] Create `packages/dashboard/src/hooks/use-order-approvals.ts` — TanStack Query: list approvals for order, create approval
- [ ] T023 [US1] Cancellation panel on order detail page — reason `<Select>` (7 Shopify-enum options), `note` textarea, `restock_items` checkbox, `refund_payments` toggle + `refund_amount` input; history timeline below
- [ ] T024 [US2] Approval panel on order detail page — approve/reject buttons (visible when `requires_approval: true` and status is `placed`); history timeline
- [ ] T025 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.orders.cancellations.*` and `admin.orders.approvals.*`
- [ ] T026 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [ ] T027 `packages/dashboard/e2e/order-cancellation.spec.ts` — cancel order with reason + restock → verify status canceled → verify stock movement created
- [ ] T028 `packages/dashboard/e2e/order-approval.spec.ts` — requires_approval store → place order → verify blocked → approve → verify fulfillment unblocked

---

## Phase 3: 6.0 Cleanup (PENDING)

- [ ] T029 Migration: drop `canceled_at`, `canceler_id`, `approved_at`, `approver_id` from `spree_orders`
- [ ] T030 Update `Spree::Order` serializer: derive `canceled_at` from `order.cancellations.last&.created_at`; derive `approver_id` from `order.approvals.last&.approver_id`
- [ ] T031 Update `Spree::Orders::Cancel`: remove denormalized column writes
- [ ] T032 Multi-level approvals: `level` column (`manager` / `finance` / `admin`) — admin UI for multi-level approval chains
- [ ] T033 B2B cart-side approvals: `CompanyContact` as valid `approver_type` (depends on `6.0-channels-catalogs-b2b.md`)

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No API controllers for cancellations or approvals | Critical | T011–T018 above — Phase 2 is the implementation gap; models exist but are not exposed via API |
| No SPA UI for cancellation or approval workflows | Critical | T019–T028 above — currently admin must use legacy Rails admin for cancel/approve |
| No integration specs | High | T016–T017 above — no OpenAPI spec generated; SDK types missing for these resources |
| No E2E coverage | Medium | T027–T028 above |
| Denormalized columns still on `spree_orders` | Low | By design in 5.5; planned drop in 6.0 (T029–T031) |
