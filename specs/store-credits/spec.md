# Feature Specification: Store Credits

**Feature Branch**: `main` (fully shipped; no dedicated E2E)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: None dedicated

---

## User Scenarios & Testing

### User Story 1 — Issue Store Credit to a Customer (Priority: P1)

An admin manually issues store credit to a customer — as compensation, a loyalty reward, or a refund alternative. Each credit has an amount, currency, optional expiry, memo, and category.

**Why this priority**: Store credit is a primary customer retention and refund tool; support teams use this daily.

**Independent Test**: Admin POSTs to `/api/v3/admin/customers/:id/store_credits` with `{ amount: 50, currency: "USD", memo: "Compensation" }`. Response has `id: "credit_…"`. Customer can use it at checkout.

**Acceptance Scenarios**:

1. **Given** a customer, **When** admin issues $50 store credit, **Then** it appears with `credit_…` ID and `amount: 50`
2. **Given** a store credit with expiry, **When** expired, **Then** it cannot be applied at checkout
3. **Given** a store credit with `amount_used > 0`, **When** admin tries to delete, **Then** 422 (used credits cannot be deleted)
4. **Given** a store credit belonging to Store A, **When** Store B admin lists store credits, **Then** Store A's credit is not returned

---

### User Story 2 — View Store Credit History (Priority: P1)

Admin views the event log for a store credit — authorizations, captures, voids, and cancellations — to audit how the credit was used.

**Acceptance Scenarios**:

1. **Given** a partially used store credit, **When** admin views events, **Then** authorize + capture events are listed
2. **Given** a voided store credit, **When** events listed, **Then** void event appears with timestamp and acting admin
3. **Given** `ELIGIBLE` and `AUTHORIZE` internal events, **When** listed, **Then** they are filtered out (exposed_events scope)

---

### User Story 3 — Manage Store Credit Categories (Priority: P2)

Admin creates and manages store credit categories (e.g., "Gift Card", "Loyalty", "Refund"). Categories control non-expiring behavior and display labels.

**Acceptance Scenarios**:

1. **Given** no categories, **When** admin creates "Loyalty", **Then** it appears with `sccat_…` ID
2. **Given** a "Gift Card" category, **When** store credit is created with this category, **Then** non-expiring rules apply

---

### Edge Cases

- What if `amount_authorized + amount_used > amount`? → Prevented by model validation; `authorize` rejects over-authorization
- What if a store credit is voided mid-checkout? → Authorization is released; order cannot complete with that credit
- What if no category is specified on create? → Default category is used (system-defined fallback)

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::StoreCredit` prefix `credit_`; `include Spree::SingleStoreResource`; `acts_as_paranoid`; `include Spree::Metafields`; `include Spree::Metadata`; `publishes_lifecycle_events`
- **FR-002**: Actions: `VOID`, `CANCEL`, `CREDIT`, `CAPTURE`, `ELIGIBLE`, `AUTHORIZE`, `ALLOCATION` — action constants on the model
- **FR-003**: `amount`, `amount_used`, `amount_authorized` — balance tracking columns
- **FR-004**: `Spree::StoreCreditEvent` prefix `scevt_`; `acts_as_paranoid`; `exposed_events` scope filters out `ELIGIBLE`/`AUTHORIZE`
- **FR-005**: `Spree::StoreCreditCategory` prefix `sccat_`; `GIFT_CARD_CATEGORY_NAME` constant; non-expiring logic
- **FR-006**: `Spree::PaymentMethod::StoreCredit` — payment method implementation (uses credit at checkout)
- **FR-007**: Admin API: nested under customers (CRUD), nested under orders (add/remove during checkout), standalone categories
- **FR-008**: `use-customer-store-credits.ts` + `use-store-credit-categories.ts` hooks

### Key Entities

- **StoreCredit** (`Spree::StoreCredit`): amount, amount_used, amount_authorized, currency, expires_at, memo, category_id, user_id, created_by_id. Prefix: `credit_`.
- **StoreCreditEvent** (`Spree::StoreCreditEvent`): action, amount, user_total_amount, originator. Prefix: `scevt_`.
- **StoreCreditCategory** (`Spree::StoreCreditCategory`): name, non_expiring. Prefix: `sccat_`.

---

## Backend Requirements

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/customers/:id/store_credits` | List store credits for customer |
| POST | `/api/v3/admin/customers/:id/store_credits` | Issue store credit |
| PATCH | `/api/v3/admin/customers/:id/store_credits/:id` | Update memo/expiry |
| DELETE | `/api/v3/admin/customers/:id/store_credits/:id` | Void/delete (guarded by amount_used) |
| POST | `/api/v3/admin/orders/:id/store_credits` | Apply store credit to order |
| DELETE | `/api/v3/admin/orders/:id/store_credits/:id` | Remove store credit from order |
| GET | `/api/v3/admin/store_credit_categories` | List categories |
| POST | `/api/v3/admin/store_credit_categories` | Create category |
| PATCH | `/api/v3/admin/store_credit_categories/:id` | Update category |
| DELETE | `/api/v3/admin/store_credit_categories/:id` | Delete category |

### Serializer Fields

**Admin StoreCreditSerializer**:
- `id` (credit_…), `customer_id` (cus_…), `created_by_id` (admin_…), `category_id` (sccat_…), `amount`, `amount_used`, `amount_authorized`, `currency`, `expires_at`, `memo`, `metadata`, `created_at`, `updated_at`, `deleted_at`

---

## Frontend Requirements

### SPA Routes

- Store credit section in customer detail (`$customerId.tsx`) — issue, view history, void

### Hooks

- `packages/dashboard/src/hooks/use-customer-store-credits.ts` — create/update mutations with client-side money normalization
- `packages/dashboard/src/hooks/use-store-credit-categories.ts` — CRUD for categories

---

## Success Criteria

- **SC-001**: Admin can issue store credit to a customer; customer can use it at checkout
- **SC-002**: Event log shows all credit actions except internal ELIGIBLE/AUTHORIZE
- **SC-003**: Used credits cannot be deleted; validation prevents over-authorization
- **SC-004**: Credits are store-scoped; cross-store access is blocked
- **SC-005**: Categories control non-expiring behavior and display labels

---

## Assumptions

- Store credit is applied as a payment source at checkout via `PaymentMethod::StoreCredit`
- `created_by_id` references the admin user who issued the credit (audit trail)
- `polymorphic originator` on events traces the source (order, admin action, reimbursement)
