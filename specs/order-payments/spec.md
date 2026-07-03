# Feature Specification: Order Payments

**Feature Branch**: `main` (models + API shipped; dashboard SPA pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: None dedicated; informed by `6.0-cart-order-split.md` (Cart/Order split pending)

---

## User Scenarios & Testing

### User Story 1 — View Payments on an Order (Priority: P1)

An admin views the payment history for an order — which payment methods were attempted, their current status, captured amounts, and AVS/CVV responses.

**Why this priority**: Customer support resolves payment failures daily; without visibility into payment state, agents cannot diagnose issues or initiate refunds.

**Independent Test**: Admin opens order `ord_…`. Payment section shows a Stripe payment with `status: completed`, `amount: 99.99`, `captured_amount: 99.99`.

**Acceptance Scenarios**:

1. **Given** a completed order, **When** admin opens the order detail, **Then** payments panel shows all payments with status + amounts
2. **Given** a failed payment attempt, **When** listed, **Then** AVS/CVV response codes are visible
3. **Given** multiple payment attempts on one order, **When** listed, **Then** all are shown in chronological order

---

### User Story 2 — Capture a Payment (Priority: P1)

Admin manually captures an authorized payment (for stores using auth-then-capture flow).

**Why this priority**: Some merchants authorize at order placement and capture at fulfillment; without manual capture, revenue is delayed or lost.

**Independent Test**: Admin POSTs to `POST /api/v3/admin/orders/:id/payments/:id/capture`. Payment transitions from `pending` → `completed`. `captured_amount` is updated.

**Acceptance Scenarios**:

1. **Given** a payment in `pending` state, **When** admin triggers capture, **Then** payment transitions to `completed`
2. **Given** a payment in `completed` state, **When** admin tries to capture again, **Then** 422 is returned
3. **Given** a partial capture amount, **When** captured, **Then** `captured_amount` reflects the partial amount

---

### User Story 3 — Void a Payment (Priority: P1)

Admin voids an authorized but uncaptured payment (e.g., cancelled order).

**Acceptance Scenarios**:

1. **Given** a `pending` payment, **When** admin voids it, **Then** payment transitions to `void`
2. **Given** a `completed` payment, **When** admin tries to void, **Then** 422 is returned (must refund instead)

---

### User Story 4 — Create a Payment for an Order (Priority: P2)

Admin adds a payment to an existing order (e.g., add store credit, split payment).

**Acceptance Scenarios**:

1. **Given** an order with balance due, **When** admin adds a store-credit payment, **Then** order balance decreases
2. **Given** a `source_id` pointing to a saved credit card, **When** admin creates payment, **Then** payment is created off-session

---

### Edge Cases

- What if capture fails at the gateway? → Payment remains `pending`; error message returned in 422 response
- What if void is called after capture? → State machine rejects (invalid transition); 422 returned
- What if payment method is soft-deleted? → Payment references method by ID; existing payments unaffected

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::Payment` has state machine: `checkout → processing → pending → completed / failed / void / invalid`
- **FR-002**: `captured_amount` tracks partial vs full capture; `amount` is the authorized amount
- **FR-003**: Polymorphic `source` (CreditCard, StoreCredit, GiftCard, etc.)
- **FR-004**: AVS/CVV response codes stored on payment for fraud review
- **FR-005**: `Spree::PaymentSession` (`ps_…`) tracks async gateway sessions (pending → processing → completed/failed/expired)
- **FR-006**: `Spree::PaymentSetupSession` (`pss_…`) tracks async payment source setup (tokenization)
- **FR-007**: Admin API: nested under orders (`/admin/orders/:id/payments`); actions: `index`, `show`, `create`, `capture`, `void`
- **FR-008**: All payment IDs prefixed `py_…`
- **FR-009**: _(PENDING)_ Dashboard payment panel on order detail page: capture/void buttons + payment history timeline

### Key Entities

- **Payment** (`Spree::Payment`): state machine, `amount`, `captured_amount`, `avs_response`, `cvv_response`, polymorphic `source`, `payment_method_id`. Prefix: `py_`.
- **PaymentSession** (`Spree::PaymentSession`): async gateway session tracking. Prefix: `ps_`.
- **PaymentSetupSession** (`Spree::PaymentSetupSession`): async source tokenization. Prefix: `pss_`.
- **CreditCard** (`Spree::CreditCard`): polymorphic payment source. Prefix: `card_`.

---

## Backend Requirements

### Data Model

- **Table**: `spree_payments` — `amount decimal null: false`, `captured_amount decimal`, `state string null: false`, `source_type`, `source_id`, `payment_method_id string`, `order_id string null: false`, `avs_response`, `cvv_response_code`, `number` (public reference), timestamps
- **Table**: `spree_payment_sessions` — `state string null: false`, `external_id` (gateway reference), `payment_id string null: false`, `amount decimal`, timestamps
- **Table**: `spree_payment_setup_sessions` — `state string null: false`, `external_id`, `payment_method_id`, `user_id`, timestamps

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/orders/:id/payments` | List payments for order |
| POST | `/api/v3/admin/orders/:id/payments` | Create payment |
| GET | `/api/v3/admin/orders/:id/payments/:id` | Show payment |
| POST | `/api/v3/admin/orders/:id/payments/:id/capture` | Capture authorized payment |
| POST | `/api/v3/admin/orders/:id/payments/:id/void` | Void authorized payment |

### Serializer Fields

**Admin PaymentSerializer**:
- `id` (py_…), `order_id` (prefixed), `payment_method_id` (pm_…), `amount`, `captured_amount`, `status` (state), `avs_response`, `cvv_response_code`, `source_type`, `source_id`, `number`, `created_at`, `updated_at`

### Authorization

- CanCanCan: `can :manage, Spree::Payment`
- Scoped to current store via `order.store`

---

## Frontend Requirements

### SPA Routes (PENDING)

- Order detail page (`$orderId.tsx`) needs a Payments panel — capture/void actions + payment history timeline
- No standalone payments route; payments are always in the context of an order

### Hooks (PENDING)

- `packages/dashboard/src/hooks/use-order-payments.ts` — TanStack Query wrappers for list, create, capture, void

### i18n Keys (PENDING)

Under `admin.orders.payments.*`: status labels, capture/void button labels, amount labels, toast messages.

---

## Success Criteria

- **SC-001**: Admin can list all payments for an order including state + captured amount
- **SC-002**: Admin can capture a `pending` payment; state transitions to `completed`
- **SC-003**: Admin can void a `pending` payment; state transitions to `void`
- **SC-004**: AVS/CVV response codes are visible on each payment record
- **SC-005**: _(PENDING)_ Dashboard Payments panel on order detail shows history timeline + capture/void buttons

---

## Assumptions

- Payment state machine transitions are enforced at model level; API reflects the model's current state
- `captured_amount` is updated by the gateway callback or manual capture action
- `PaymentSession` and `PaymentSetupSession` are primarily used by the Store API checkout flow, not the admin
