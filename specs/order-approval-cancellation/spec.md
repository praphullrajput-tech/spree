# Feature Specification: Order Approval & Cancellation

**Feature Branch**: `main` (5.5 models shipped; API and SPA pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: `docs/plans/5.5-6.0-order-cancellation-and-approval.md`

---

## User Scenarios & Testing

### User Story 1 — Cancel an Order with Reason and Actions (Priority: P1)

A merchant admin cancels a placed order, selects a reason from a standard set, optionally restocks items, optionally refunds payments, and optionally notifies the customer. The cancellation creates an `OrderCancellation` record (full history) and updates `Order#status` to `canceled`. Multiple cancel-resume-cancel cycles are preserved as separate records.

**Why this priority**: Order cancellation is a core merchant operation. The existing `canceled_at` / `canceler_id` denormalized columns cannot store reason, restock decision, or refund amount.

**Independent Test**: Admin cancels order #001 with `reason: "inventory"`, `restock_items: true`, `refund_payments: true`. An `OrderCancellation` record is created. `order.status` is `canceled`. Source stock items are restocked. The payment refund is issued (up to `refund_amount`). All of this happens in a single transaction.

**Acceptance Scenarios**:

1. **Given** a placed order, **When** admin cancels it with `reason: "inventory"`, **Then** `Order#status` is `canceled` and an `OrderCancellation` with `reason: "inventory"` is created
2. **Given** cancellation with `restock_items: true`, **When** cancelled, **Then** `StockMovement` records are written restoring inventory in the same transaction
3. **Given** cancellation with `refund_payments: true` and `refund_amount: 50.00`, **When** cancelled, **Then** payment is refunded up to the specified amount
4. **Given** a cancelled order, **When** admin cancels it again (after resuming), **Then** a new `OrderCancellation` record is created; the previous one is preserved
5. **Given** a 422 from a field error, **When** `reason` is blank, **Then** inline form error appears on the reason field

---

### User Story 2 — Approve an Order Before Fulfillment (Priority: P1)

When a store requires approval (opt-in per-store via `Order#requires_approval?`), a placed order waits for merchant approval before fulfillment begins. The admin approves or rejects the order; approval creates an `OrderApproval` record. Multi-level approval (manager / finance / admin) is deferred to 6.0.

**Why this priority**: High-value orders, fraud-check flows, and B2B merchants need a human review gate before warehouse fulfillment starts.

**Independent Test**: Store has `requires_approval?` returning `true`. Order is placed; `status: "placed"` but fulfillment is blocked. Admin approves; `OrderApproval { status: "approved" }` record created. Fulfillment proceeds.

**Acceptance Scenarios**:

1. **Given** `requires_approval?: true`, **When** order is placed, **Then** fulfillment is blocked until an `OrderApproval { status: "approved" }` record exists
2. **Given** a pending order, **When** admin approves it, **Then** `OrderApproval { status: "approved" }` is created with `decided_at` and `approver` reference
3. **Given** a pending order, **When** admin rejects it, **Then** `OrderApproval { status: "rejected" }` is created; order remains blocked
4. **Given** an approved order, **When** viewing order history, **Then** the approval record shows who approved it and when
5. **Given** a 422 when approval note is required, **When** note is blank, **Then** field error appears on `note`

---

### User Story 3 — View Cancellation and Approval History (Priority: P2)

An admin views the full history of cancellations and approvals on an order detail page. Multiple cancellation events (cancel → resume → cancel again) are listed chronologically with reason, actor, and timestamp.

**Why this priority**: Customer service and finance teams need audit history to resolve disputes and process refunds correctly.

**Independent Test**: Order that was cancelled twice: `GET /admin/orders/:id/cancellations` returns both records in chronological order, each with `reason`, `canceled_by`, `restock_items`, `refund_amount`, `created_at`.

**Acceptance Scenarios**:

1. **Given** an order with two cancellation records, **When** listing cancellations, **Then** both appear in `created_at` order
2. **Given** a cancellation record, **When** viewed, **Then** `canceled_by_id`, `canceled_by_type`, `reason`, `restock_items`, `refund_payments`, `refund_amount`, `note` are all present
3. **Given** `notify_customer: true` on the cancellation, **When** the record is created, **Then** a customer notification is triggered (webhook or email, depending on notifier implementation)

---

### Edge Cases

- What if `restock_items: true` but a variant has been deleted? → Restock skips deleted variants; cancellation still proceeds
- What if `refund_payments: true` but `refund_amount > order.payment_total`? → Refund is capped at `payment_total`; no over-refund
- What if the order is in `complete` state? → Covered by `UNACTIVATABLE_ORDER_STATES`; cancel is refused
- _(6.0)_ What if B2B cart-side approvals are needed? → Deferred to 6.0; requires `Spree::Company` + `Cart` model split

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::OrderCancellation` — append-only history; one record per cancel event; `reason` from Shopify enum (`customer`, `declined`, `fraud`, `inventory`, `staff`, `other`, `expired`)
- **FR-002**: `Spree::OrderApproval` — append-only history; `status` (`pending`, `approved`, `rejected`); polymorphic `approver`
- **FR-003**: `Order` retains denormalized columns (`canceled_at`, `canceler_id`, `approved_at`, `approver_id`) in 5.5 for backward compatibility — mirroring the latest record
- **FR-004**: `Spree::Orders::Cancel` service extended with optional `reason`, `note`, `restock_items`, `refund_payments`, `refund_amount`, `notify_customer` params — all backward-compatible
- **FR-005**: Cancellation, restocking, and refund happen in a single transaction; failures roll back the `OrderCancellation` record
- **FR-006**: Approval is opt-in per store via `Order#requires_approval?` (overridable method or per-store config)
- **FR-007**: Admin API: `POST /admin/orders/:id/cancellations` and `POST /admin/orders/:id/approvals`; `GET` for listing
- **FR-008**: All cancellation IDs prefixed `cncl_…`; all approval IDs prefixed `appr_…`
- **FR-009**: _(6.0 pending)_ Drop denormalized columns; reads come from `order.cancellations.last` / `order.approvals.last`
- **FR-010**: _(6.0 pending)_ Multi-level approvals (`level`: manager / finance / admin)

### Key Entities

- **OrderCancellation** (`Spree::OrderCancellation`): `order_id`, `reason` (string, Shopify enum), `note`, `restock_items`, `refund_payments`, `refund_amount`, `notify_customer`, `canceled_by_id`, `canceled_by_type` (polymorphic). Prefix: `cncl_`.
- **OrderApproval** (`Spree::OrderApproval`): `order_id`, `status` (pending/approved/rejected), `level` (nullable in 5.5), `note`, `approver_id`, `approver_type` (polymorphic), `decided_at`. Prefix: `appr_`.

---

## Backend Requirements

### Data Model

- **Table**: `spree_order_cancellations` — `order_id`, `reason null: false`, `note`, `restock_items boolean`, `refund_payments boolean`, `refund_amount decimal(10,2)`, `notify_customer boolean`, `canceled_by_id`, `canceled_by_type`, `metadata jsonb`, timestamps
- **Table**: `spree_order_approvals` — `order_id`, `status null: false`, `level`, `note`, `approver_id`, `approver_type`, `decided_at`, `metadata jsonb`, timestamps
- **Indexes**: `order_id` on both; `canceled_by_id+type`; `approver_id+type`; `created_at`
- **Order denormalized** (5.5): `canceled_at`, `canceler_id`, `approved_at`, `approver_id` — mirrored from latest records; dropped in 6.0

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/orders/:id/cancellations` | List cancellation history |
| POST | `/api/v3/admin/orders/:id/cancellations` | Cancel order |
| GET | `/api/v3/admin/orders/:id/cancellations/:id` | Show cancellation |
| GET | `/api/v3/admin/orders/:id/approvals` | List approval history |
| POST | `/api/v3/admin/orders/:id/approvals` | Approve or reject order |
| GET | `/api/v3/admin/orders/:id/approvals/:id` | Show approval |

### Serializer Fields

**Admin OrderCancellationSerializer**:
- `id` (cncl_…), `order_id` (prefixed), `reason`, `note`, `restock_items`, `refund_payments`, `refund_amount`, `notify_customer`, `canceled_by_id`, `canceled_by_type`, `created_at`

**Admin OrderApprovalSerializer**:
- `id` (appr_…), `order_id` (prefixed), `status`, `level`, `note`, `approver_id`, `approver_type`, `decided_at`, `created_at`

### Authorization

- CanCanCan: `can :manage, Spree::OrderCancellation` and `can :manage, Spree::OrderApproval` for admin
- Actor is polymorphic: accepts `Spree::AdminUser`, `Spree::User`, _(6.0)_ `Spree::CompanyContact`

### i18n (Rails)

- Reason labels: `spree.order_cancellation.reasons.*` for all 7 Shopify-enum values
- Approval status labels: `spree.order_approval.statuses.*`

---

## Frontend Requirements

### SPA Routes

- _(Pending)_ Order detail page: Cancellation panel — form with reason dropdown, note, restock/refund toggles; history timeline
- _(Pending)_ Order detail page: Approval panel — approve/reject buttons for pending orders; history timeline

### Hooks

- _(Pending)_ `packages/dashboard/src/hooks/use-order-cancellations.ts`
- _(Pending)_ `packages/dashboard/src/hooks/use-order-approvals.ts`

### i18n Keys

Under `admin.orders.cancellations.*` and `admin.orders.approvals.*` in all 6 locale files: reason labels, status labels, form labels, history column headers, action button labels.

---

## Success Criteria

- **SC-001**: Cancelling an order with `restock_items: true` and `refund_payments: true` atomically creates the cancellation record, restocks inventory, and issues the refund
- **SC-002**: `Order#cancellations` history is preserved across multiple cancel-resume cycles
- **SC-003**: Approval gate blocks fulfillment on `requires_approval?: true` stores until `OrderApproval { status: "approved" }` exists
- **SC-004**: All reason values from the Shopify enum are accepted and stored as strings
- **SC-005**: _(6.0)_ Denormalized columns dropped; `canceled_at` derived from `order.cancellations.last.created_at`

---

## Assumptions

- `Spree::Orders::Cancel` and `Spree::Orders::Approve` services are the only correct entry points; direct model manipulation bypasses the transactional guarantees
- `requires_approval?` is overridable by merchants; the default implementation returns `false` (opt-in, not forced)
- Reason strings follow Shopify's enum for industry-standard compatibility; stored as strings (not Rails enum) per CLAUDE.md convention
- _(6.0)_ B2B cart-side approvals (buyer-organization internal sign-off) are a separate concept and are deferred to 6.0 with `Spree::Company`
