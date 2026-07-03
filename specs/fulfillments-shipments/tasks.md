---

description: "Task list for Fulfillments & Shipments — models + API shipped; SPA/hooks/E2E entirely PENDING"
---

# Tasks: Fulfillments & Shipments

**Status**: Models + API + legacy admin shipped; SPA PENDING; 6.0 rename pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Shipment services | `spree/core/app/services/spree/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/orders/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core + API ✅

### Models

- [x] T001 `spree/core/app/models/spree/shipment.rb` — `has_prefix_id :ful`; state machine: `pending → ready → shipped`; `cancel!`, `resume!`; `cost`, `tracking`; `ship_date` timestamp; belongs_to stock_location, shipping_method, order
- [x] T002 `spree/core/app/models/spree/inventory_unit.rb` — `has_prefix_id :fi`; per-line-item granularity; `on_hand → backordered → shipped → returned`; belongs_to shipment, line_item, variant
- [x] T003 `spree/core/app/services/spree/shipment_update_service.rb` — complex update propagation: recalculates rates, updates order shipment_state, coordinates inventory

### Serializers

- [x] T004 `spree/api/app/serializers/spree/api/v3/admin/shipment_serializer.rb` — status, tracking, ship_date, cost, stock_location, shipping_method, inventory_units, timestamps
- [x] T005 `spree/api/app/serializers/spree/api/v3/admin/inventory_unit_serializer.rb` — status, variant_id, line_item_id, timestamps

### Controllers

- [x] T006 `spree/api/app/controllers/spree/api/v3/admin/shipments_controller.rb` — nested under orders; index, show, update; action endpoints: `fulfill`, `cancel`, `resume`, `split`

### Specs

- [x] T007 `spree/core/spec/models/spree/shipment_spec.rb` — state machine transitions; cancel/resume guards; tracking updates
- [x] T008 `spree/api/spec/integration/spree/api/v3/admin/shipments_spec.rb` — fulfill action; split action; cancel/resume

### Type Pipeline

- [x] T009 `bundle exec rake typelizer:generate`
- [x] T010 `cd packages/sdk && pnpm generate:zod`
- [x] T011 `bundle exec rake rswag:specs:swaggerize`

**Checkpoint**: models + API fully shipped; legacy admin provides fulfillment management ✅

---

## Phase 2: SPA (PENDING)

- [ ] T012 [US1] `packages/dashboard/src/routes/_authenticated/$storeId/orders/$orderId.tsx` — shipments panel: list per-order shipments, status badge, tracking input, fulfill/cancel/resume buttons
- [ ] T013 `packages/dashboard/src/hooks/use-shipments.ts` — TanStack Query wrappers: `useOrderShipments`, `useFulfillShipment`, `useCancelShipment`, `useResumeShipment`
- [ ] T014 Add i18n keys under `admin.shipments.*` and `admin.inventory_units.*` in all locale files
- [ ] T015 `packages/dashboard/e2e/shipments.spec.ts` — fulfill flow; split flow; cancel + resume; tracking entry
- [ ] T016 Run `pnpm test:e2e`

---

## Phase 3: 6.0 — Fulfillment Rename (PENDING)

Per `6.0-fulfillment-and-delivery.md`:

- [ ] T017 Rename `Spree::Shipment` → `Spree::Fulfillment`; prefix `ful_` is already forward-compatible
- [ ] T018 Rename `Spree::InventoryUnit` → `Spree::FulfillmentItem`; prefix `fi_` already forward-compatible
- [ ] T019 Introduce `Spree::FulfillmentProvider` STI base replacing `ShippingMethod` fulfillment logic
- [ ] T020 Pickup support: merchant `StockLocation` pickup + third-party `PickupPointProvider`

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No shipments panel in admin SPA | High | T012–T016 — blocking for merchants managing fulfillments |
| No `use-shipments.ts` hook | High | Part of T012 work; extracted hook needed for consistency |
| No E2E tests for shipment flows | High | `shipments.spec.ts` covers fulfill, split, cancel, resume |
| `split` action UI not designed | Medium | Split shipment UX needed; carry forward from legacy admin behavior |
