# Feature Specification: Returns & Refunds

**Feature Branch**: `main` (models + serializers shipped; API controller for RAs PENDING; 6.0 replaces chain)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `6.0-returns-exchanges-claims.md`

---

## User Scenarios & Testing

### User Story 1 — Authorize a Return (Priority: P1)

An admin authorizes a customer's return request. The return authorization records which items are being returned, the reason, and the stock location for restocking.

**Why this priority**: Returns are a legal obligation in many markets and a core customer service function; without RAs, returned goods cannot be processed.

**Independent Test**: Admin POSTs to `/api/v3/admin/orders/:id/return_authorizations` with items and reason. Response has `id: "ra_…"` and `state: authorized`.

**Acceptance Scenarios**:

1. **Given** a completed order, **When** admin creates a return authorization, **Then** it appears with `ra_…` ID in `authorized` state
2. **Given** a return authorization, **When** admin cancels it, **Then** state transitions to `canceled`
3. **Given** a return authorization, **When** items are received, **Then** return items are created and marked as accepted

---

### User Story 2 — Process a Reimbursement (Priority: P1)

Admin creates a reimbursement for a return authorization, selecting the reimbursement type (store credit, original payment, exchange).

**Why this priority**: Reimbursement closes the financial loop of a return; without it, customers are not compensated.

**Acceptance Scenarios**:

1. **Given** accepted return items, **When** admin creates a reimbursement with type `original_payment`, **Then** a refund is issued to the original payment method
2. **Given** a reimbursement with type `store_credit`, **Then** a `StoreCredit` is created for the customer
3. **Given** a reimbursement, **Then** it has a unique number (prefix `RI`)

---

### User Story 3 — Issue a Refund (Priority: P1)

Admin issues a direct refund on a payment (not necessarily tied to a return authorization).

**Acceptance Scenarios**:

1. **Given** a completed payment, **When** admin issues a refund, **Then** `Spree::Refund` is created and `perform!` triggers the gateway refund
2. **Given** a refund amount exceeding the captured amount, **Then** 422 is returned
3. **Given** a refund, **When** listed on the order, **Then** it appears in the refunds panel

---

### Edge Cases

- What if the gateway refund fails? → `Refund` record is not created; error propagated as 422
- What if a return item is not in returnable state? → `return_eligibility_validator` rejects it; 422 on RA creation
- _(6.0)_ Entire chain (ReturnAuthorization → ReturnItem → Reimbursement → Refund) is replaced by first-class `Return`, `Exchange`, `Claim` models per `6.0-returns-exchanges-claims.md`

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::ReturnAuthorization` prefix `ra_`; state machine: `authorized → canceled`; belongs_to order + stock_location
- **FR-002**: `Spree::ReturnItem` prefix `ri_`; `return_eligibility_validator`; `exchange_variant_engine` for variant swaps; `refund_amount_calculator`
- **FR-003**: `Spree::Reimbursement` prefix `reimb_`; number generator (prefix `RI`); nested_attributes for return_items; `Spree::ReimbursementPerformer` executes the reimbursement
- **FR-004**: `Spree::Refund` prefix `re_`; `after_create :perform!` triggers gateway refund; belongs_to payment + reimbursement (optional)
- **FR-005**: `Spree::ReturnAuthorizationReason` — named reasons for returns
- **FR-006**: `Spree::ReimbursementType` — strategy for how to reimburse (original payment, store credit, exchange)
- **FR-007**: Admin API serializers: `ReturnAuthorizationSerializer`, `ReimbursementSerializer`, `RefundSerializer` — all exist
- **FR-008**: _(PENDING)_ `return_authorizations_controller` nested under orders — does not exist in v3 admin API
- **FR-009**: Refunds controller nested under orders — exists
- **FR-010**: _(6.0)_ Return/Exchange/Claim models replace this chain per `6.0-returns-exchanges-claims.md`

### Key Entities

- **ReturnAuthorization** (`Spree::ReturnAuthorization`): state, reason, amount, order_id, stock_location_id. Prefix: `ra_`.
- **ReturnItem** (`Spree::ReturnItem`): inventory_unit_id, return_authorization_id, acceptance_status, exchange_variant_id, refund_amount. Prefix: `ri_`.
- **Reimbursement** (`Spree::Reimbursement`): number, order_id, return_items. Prefix: `reimb_`.
- **Refund** (`Spree::Refund`): amount, payment_id, reimbursement_id, reason. Prefix: `re_`.

---

## Backend Requirements

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/orders/:id/refunds` | List refunds for order |
| POST | `/api/v3/admin/orders/:id/refunds` | Issue refund |
| _(PENDING)_ GET | `/api/v3/admin/orders/:id/return_authorizations` | List RAs |
| _(PENDING)_ POST | `/api/v3/admin/orders/:id/return_authorizations` | Create RA |
| _(PENDING)_ PATCH | `/api/v3/admin/orders/:id/return_authorizations/:id` | Update RA |
| _(PENDING)_ POST | `/api/v3/admin/orders/:id/return_authorizations/:id/cancel` | Cancel RA |

### Serializer Fields

**Admin ReturnAuthorizationSerializer**:
- `id` (ra_…), `order_id` (or_…), `state`, `reason`, `amount`, `stock_location_id`, `return_items`, `created_at`, `updated_at`

**Admin RefundSerializer**:
- `id` (re_…), `payment_id` (py_…), `reimbursement_id` (reimb_…), `amount`, `reason`, `created_at`

---

## Frontend Requirements

### SPA Routes (PENDING)

- Returns panel on order detail page — create RA, list return items, trigger reimbursement
- No standalone returns index page

### Hooks (PENDING)

- `use-return-authorizations.ts`, `use-refunds.ts`

---

## Success Criteria

- **SC-001**: Admin can issue a refund on a payment; gateway refund is triggered
- **SC-002**: _(PENDING)_ Admin can create a return authorization via v3 API
- **SC-003**: _(PENDING)_ Dashboard returns panel on order detail
- **SC-004**: _(6.0)_ Return/Exchange/Claim models replace entire chain

---

## Assumptions

- `Refund#perform!` is called in an `after_create` callback; it is not a separate service call
- Reimbursement type selection determines whether refund goes to payment, store credit, or exchange
- Return eligibility rules are model-level validators, not configurable by merchants
