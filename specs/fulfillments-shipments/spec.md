# Feature Specification: Fulfillments/Shipments

**Feature Branch**: `main` (models + API shipped; SPA pending; 6.0 rename pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `6.0-fulfillment-and-delivery.md`

---

## User Scenarios & Testing

### User Story 1 — Fulfill an Order (Priority: P1)

An admin marks a shipment as shipped, optionally entering a tracking number. The shipment transitions from `pending` → `ready` → `shipped`. The order's `shipment_state` updates accordingly.

**Why this priority**: Fulfillment is a daily warehouse operation; without the ability to mark shipments as shipped, order flow is broken.

**Independent Test**: Admin POSTs to `POST /api/v3/admin/orders/:id/fulfillments/:id/fulfill`. Shipment transitions to `shipped`. Order's `shipment_state` updates to `shipped`.

**Acceptance Scenarios**:

1. **Given** a `ready` shipment, **When** admin fulfills it, **Then** state transitions to `shipped`
2. **Given** a `pending` shipment, **When** fulfilled, **Then** 422 (must transition through `ready` first)
3. **Given** a shipped shipment with tracking, **When** customer views order, **Then** tracking number and URL are shown
4. **Given** a multi-shipment order, **When** one shipment ships, **Then** order `shipment_state` becomes `partial`

---

### User Story 2 — Cancel a Shipment (Priority: P1)

Admin cancels a shipment that has not yet shipped (e.g., items out of stock, order canceled).

**Acceptance Scenarios**:

1. **Given** a `pending` shipment, **When** admin cancels it, **Then** state transitions to `canceled`
2. **Given** a `shipped` shipment, **When** admin tries to cancel, **Then** 422 returned
3. **Given** a canceled shipment, **When** admin resumes, **Then** state returns to `pending`

---

### User Story 3 — Split a Shipment (Priority: P2)

Admin splits a shipment into two, moving some items to a new shipment (e.g., to ship from a different stock location).

**Acceptance Scenarios**:

1. **Given** a shipment with 3 line items, **When** admin splits off 1 item, **Then** two shipments exist with the items distributed
2. **Given** a split operation, **When** targeting a different stock location, **Then** the new shipment uses that location

---

### Edge Cases

- What if a shipment has no shipping rate selected? → Cannot transition to `ready`; checkout requires a selected rate
- What if the stock location is soft-deleted? → Shipment references by ID; existing shipments unaffected
- _(6.0)_ `Spree::Shipment` → `Spree::Fulfillment`; `Spree::InventoryUnit` → `Spree::FulfillmentItem` per `6.0-fulfillment-and-delivery.md`

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::Shipment` prefix `ful_` (anticipates 6.0 Fulfillment rename); number generator (prefix `H`, length 11)
- **FR-002**: State machine (via `state_machines-activerecord`): `pending → ready → shipped`; `pending/ready → canceled`; `canceled → pending` (resume)
- **FR-003**: `Spree::InventoryUnit` prefix `fi_` (anticipates 6.0 FulfillmentItem rename); tracks per-unit state for returns
- **FR-004**: Concerns: `NumberIdentifier`, `Metafields`, `Metadata`, `Webhooks`, `CustomEvents`
- **FR-005**: `belongs_to :stock_location`; selected shipping rate via `shipping_rates` association (selected: true)
- **FR-006**: Admin API nested under orders: `index`, `show`, `update` (shipment update service), `fulfill`, `cancel`, `resume`, `split`
- **FR-007**: Order locking via `OrderLock` concern during mutation operations
- **FR-008**: _(PENDING)_ Admin SPA pages for shipment management
- **FR-009**: _(6.0)_ Shipment → Fulfillment; InventoryUnit → FulfillmentItem; ShippingMethod → DeliveryMethod; ShippingRate → DeliveryRate

### Key Entities

- **Shipment** (`Spree::Shipment`): state, tracking, cost, number, stock_location_id, order_id. Prefix: `ful_`.
- **InventoryUnit** (`Spree::InventoryUnit`): state (backordered/on_hand), variant_id, order_id, shipment_id, line_item_id. Prefix: `fi_`.

---

## Backend Requirements

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/orders/:id/fulfillments` | List shipments for order |
| GET | `/api/v3/admin/orders/:id/fulfillments/:id` | Show shipment |
| PATCH | `/api/v3/admin/orders/:id/fulfillments/:id` | Update shipment (tracking, address) |
| POST | `/api/v3/admin/orders/:id/fulfillments/:id/fulfill` | Mark as shipped |
| POST | `/api/v3/admin/orders/:id/fulfillments/:id/cancel` | Cancel shipment |
| POST | `/api/v3/admin/orders/:id/fulfillments/:id/resume` | Resume canceled shipment |
| POST | `/api/v3/admin/orders/:id/fulfillments/:id/split` | Split into two shipments |

### Serializer Fields

**Admin FulfillmentSerializer** (extends Store FulfillmentSerializer):
- `id` (ful_…), `order_id` (or_…), `number`, `state`, `tracking`, `stock_location_id` (sloc_…), `cost`, `adjustment_total`, `pre_tax_amount`, `metadata`, `created_at`, `updated_at`

---

## Frontend Requirements

### SPA Routes (PENDING)

- Fulfillments are managed within order context on the order detail page — no standalone fulfillment index
- Order detail page (`$orderId.tsx`) needs a fulfillments panel with fulfill/cancel/tracking actions

### Hooks (PENDING)

- `packages/dashboard/src/hooks/use-order-fulfillments.ts` — TanStack Query for list, fulfill, cancel, resume, split

---

## Success Criteria

- **SC-001**: Admin can mark a ready shipment as shipped with a tracking number
- **SC-002**: Admin can cancel a pending/ready shipment; state transitions correctly
- **SC-003**: Multi-shipment orders update `shipment_state` correctly as individual shipments are fulfilled
- **SC-004**: _(PENDING)_ Dashboard fulfillment panel on order detail with state-aware actions
- **SC-005**: _(6.0)_ Shipment renamed to Fulfillment; InventoryUnit to FulfillmentItem

---

## Assumptions

- Fulfillment is always managed in the context of an order; no standalone fulfillment index page is planned
- `ShipmentUpdateService` handles the complex logic of updating a shipment (recalculating rates, propagating to order)
- InventoryUnit state is managed by the fulfillment flow, not directly by admin
