# Feature Specification: Orders & Checkout

**Feature Branch**: `main` (fully shipped; 6.0 Cart/Order split pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `6.0-cart-order-split.md`, `5.5-6.0-order-cancellation-and-approval.md`

---

## User Scenarios & Testing

### User Story 1 — View and Manage Orders (Priority: P1)

An admin views the order list with filtering by status, date, customer, and channel. Admin opens an order to see line items, totals, payment state, shipment state, and customer details.

**Why this priority**: Order management is the primary daily task for operations teams — processing, fulfillment, and support all start here.

**Independent Test**: Admin GETs `/api/v3/admin/orders`. Response includes paginated orders with `id: "or_…"`, `number`, `status`, `total`, `payment_state`, `shipment_state`, `customer_id`.

**Acceptance Scenarios**:

1. **Given** completed orders, **When** admin lists with `status=placed`, **Then** only placed orders are returned
2. **Given** an order with 3 line items, **When** admin views it, **Then** all line items with quantities and prices are shown
3. **Given** an order belonging to Store A, **When** Store B admin lists orders, **Then** Store A's order is not returned
4. **Given** an order with a channel, **When** listed, **Then** `channel_id` is included in the response

---

### User Story 2 — Complete or Cancel an Order (Priority: P1)

Admin manually completes a pending order (e.g., phone order) or cancels an order with optional restocking and refund.

**Acceptance Scenarios**:

1. **Given** a `cart` status order, **When** admin calls complete, **Then** order transitions through checkout and reaches `complete`
2. **Given** a `placed` order, **When** admin cancels, **Then** order status becomes `canceled`; `canceled_at` is set
3. **Given** a canceled order with `restock_items: true`, **When** canceled, **Then** stock is returned to inventory

---

### User Story 3 — Approve an Order (Priority: P2)

For stores requiring approval before fulfillment, admin approves or rejects an order.

**Acceptance Scenarios**:

1. **Given** an order with `requires_approval: true`, **When** admin approves, **Then** fulfillment is unblocked
2. **Given** an order already approved, **When** approval is requested again, **Then** 422 is returned

---

### User Story 4 — Resend Order Confirmation (Priority: P2)

Admin resends the order confirmation email to the customer.

**Acceptance Scenarios**:

1. **Given** a completed order, **When** admin calls resend_confirmation, **Then** confirmation email is sent and `confirmation_delivered: true`

---

### Edge Cases

- What if checkout flow is incomplete (missing address or payment)? → Order remains in the appropriate checkout state; `complete` action returns 422
- What if an order's payment fails? → `payment_state: failed`; order is not completed
- _(6.0)_ Cart/Order split: current `Spree::Order` with `status: cart` becomes a distinct `Spree::Cart` model per `6.0-cart-order-split.md`

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::Order` prefix `or_`; number generator (prefix `R`); `include Spree::SingleStoreResource`
- **FR-002**: Checkout flow: `cart → address → delivery → payment → confirm → complete`
- **FR-003**: `status` column: `draft`, `placed`, `canceled` (separate from checkout state)
- **FR-004**: `payment_state`: `balance_due`, `credit_owed`, `failed`, `paid`, `void`
- **FR-005**: `shipment_state`: `backorder`, `canceled`, `partial`, `pending`, `ready`, `shipped`
- **FR-006**: Concerns: `Checkout`, `CurrencyUpdater`, `Digital`, `Payments`, `StoreCredit`, `AddressBook`, `Webhooks`, `NumberIdentifier`, `SingleStoreResource`, `MemoizedData`, `Metafields`, `Metadata`, `Searchable`
- **FR-007**: `Spree::LineItem` prefix `li_`; belongs_to order + variant; auto-copies price and tax_category from variant
- **FR-008**: Admin API: `index`, `show`, `create`, `complete`, `cancel`, `approve`, `resume`, `resend_confirmation`
- **FR-009**: Money display methods: `display_total`, `display_item_total`, `display_ship_total`, `display_promo_total`, `display_tax_total`
- **FR-010**: _(6.0)_ `status: cart` orders become `Spree::Cart`; `Spree::Order` represents placed orders only

### Key Entities

- **Order** (`Spree::Order`): checkout state, status, payment_state, shipment_state, email, bill_address, ship_address, item_total, ship_total, promo_total, tax_total, total. Prefix: `or_`.
- **LineItem** (`Spree::LineItem`): quantity, price, variant_id, order_id, tax_category_id. Prefix: `li_`.

---

## Backend Requirements

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/orders` | List orders (Ransack, paginated) |
| POST | `/api/v3/admin/orders` | Create order |
| GET | `/api/v3/admin/orders/:id` | Show order |
| PATCH | `/api/v3/admin/orders/:id` | Update order |
| POST | `/api/v3/admin/orders/:id/complete` | Complete order |
| POST | `/api/v3/admin/orders/:id/cancel` | Cancel order |
| POST | `/api/v3/admin/orders/:id/approve` | Approve order |
| POST | `/api/v3/admin/orders/:id/resume` | Resume canceled order |
| POST | `/api/v3/admin/orders/:id/resend_confirmation` | Resend confirmation email |

### Serializer Fields

**Admin OrderSerializer** (extends Store OrderSerializer):
- `id` (or_…), `number`, `status`, `state`, `payment_state`, `shipment_state`, `email`, `total`, `item_total`, `ship_total`, `promo_total`, `tax_total`, `adjustment_total`, `customer_id` (cus_…), `channel_id` (ch_…), `internal_note`, `considered_risky`, `confirmation_delivered`, `approver_id`, `canceler_id`, `created_by_id`, `created_at`, `updated_at`, `completed_at`

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/orders/index.tsx` — list with export, filter by status/date/channel; default params include `complete=1`
- `packages/dashboard/src/routes/_authenticated/$storeId/orders/$orderId.tsx` — detail with line items, payments, fulfillments, cancellations, approvals

### Hooks (PARTIAL)

- No `use-orders.ts` hook — orders index uses `adminClient.orders.list()` inline; should be extracted to hook for consistency

---

## Success Criteria

- **SC-001**: Admin can list orders filtered by status, date range, and channel
- **SC-002**: Admin can complete a phone order manually
- **SC-003**: Admin can cancel an order; cancellation record is created and stock optionally restocked
- **SC-004**: Orders are store-scoped; cross-store access is blocked
- **SC-005**: _(6.0)_ Cart/Order split ships; `Spree::Cart` is a distinct model from `Spree::Order`

---

## Assumptions

- Checkout state machine is defined via a DSL in the `Checkout` concern; it is not `state_machines-activerecord`
- `status` (draft/placed/canceled) is an admin-level classification separate from the low-level checkout state
- `internal_note` is a rich text field (ActionText in 5.x; plain text column in 6.0 per rich-text plan)
