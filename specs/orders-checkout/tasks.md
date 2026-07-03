---

description: "Task list for Orders & Checkout — fully shipped; use-orders.ts hook missing; 6.0 Cart split pending"
---

# Tasks: Orders & Checkout

**Status**: Fully shipped; one hook gap; Phase 2 (6.0 Cart split) pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Order concerns | `spree/core/app/models/spree/order/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/orders/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core + API + SPA ✅

### Models

- [x] T001 `spree/core/app/models/spree/order.rb` — `has_prefix_id :or`; checkout DSL (`checkout_steps`, `next!`, `back!`); `status` string: `draft`/`placed`/`canceled`; `payment_state` / `shipment_state` aggregates; scopes: `placed`, `draft`, `canceled`, `complete`; currency handling; `Spree::Current.store` assignment
- [x] T002 `spree/core/app/models/spree/order/checkout.rb` — checkout DSL: states `cart → address → delivery → payment → confirm → complete`; transitions; `before_*` / `after_*` hooks; `step_name` transitions
- [x] T003 `spree/core/app/models/spree/line_item.rb` — `has_prefix_id :li`; `copy_price` callback; `copy_tax_category` callback; quantity validations; `display_total`, `display_amount`

### Serializers

- [x] T004 `spree/api/app/serializers/spree/api/v3/admin/order_serializer.rb` — extends `V3::OrderSerializer`; adds `status`, `payment_state`, `shipment_state`, `special_instructions`, `channel_id`, `approved_by_id`, `cancelled_by_id`, timestamps
- [x] T005 `spree/api/app/serializers/spree/api/v3/admin/line_item_serializer.rb` — extends `V3::LineItemSerializer`; adds `cost_price`, timestamps

### Controllers

- [x] T006 `spree/api/app/controllers/spree/api/v3/admin/orders_controller.rb` — index, show, update; action endpoints: `complete`, `cancel`, `approve`, `resume`, `resend_confirmation`
- [x] T007 `spree/api/app/controllers/spree/api/v3/admin/line_items_controller.rb` — nested under orders; CRUD

### Specs

- [x] T008 `spree/core/spec/models/spree/order_spec.rb` — checkout transitions; `payment_state`/`shipment_state` aggregation; status guards; `cancellation_reason` required on cancel
- [x] T009 `spree/core/spec/models/spree/line_item_spec.rb` — `copy_price`; `copy_tax_category`; quantity validations
- [x] T010 `spree/api/spec/integration/spree/api/v3/admin/orders_spec.rb` — index filters; show; action endpoints; 422 on invalid transitions

### Type Pipeline

- [x] T011 `bundle exec rake typelizer:generate`
- [x] T012 `cd packages/sdk && pnpm generate:zod`
- [x] T013 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T014 [US1] `packages/dashboard/src/routes/_authenticated/$storeId/orders/index.tsx` — list with ResourceTable; filters by status, payment_state, shipment_state, date range; export
- [x] T015 [US2] `packages/dashboard/src/routes/_authenticated/$storeId/orders/$orderId.tsx` — detail: line items, totals, payments panel, shipments panel, customer info, address, timeline
- [x] T016 Add i18n keys under `admin.orders.*` and `admin.line_items.*` in all locale files

### E2E

- [x] T017 `packages/dashboard/e2e/orders.spec.ts`
- [x] T018 Run `pnpm test:e2e` ✅

**Checkpoint**: full order management; checkout action endpoints; filters; detail view ✅

---

## Phase 2: 6.0 — Cart/Order Split (PENDING)

Per `6.0-cart-order-split.md`:

- [ ] T019 Introduce `Spree::Cart` as a distinct model — checkout-in-progress state extracted from `Spree::Order`
- [ ] T020 `Spree::Order` becomes placed orders only; `status` values adjusted
- [ ] T021 Polymorphic `LineItem` to work across both Cart and Order contexts
- [ ] T022 API: `POST /carts` + `PATCH /carts/:id` for cart mutations; orders are read-only after placement

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No `use-orders.ts` dedicated hook — `adminClient.orders.list()` called inline in component | Low | Extract into `src/hooks/use-orders.ts` for consistency with other resources |
| No E2E for cancel + approve + resume action endpoints | Low | Add assertions in `orders.spec.ts` for each action |
