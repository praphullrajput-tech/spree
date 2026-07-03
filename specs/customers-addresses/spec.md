# Feature Specification: Customers & Addresses

**Feature Branch**: `main` (fully shipped in 5.5; 6.0 User→Customer rename pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `5.5-admin-customers-api.md`, `6.0-platform-auth.md`

---

## User Scenarios & Testing

### User Story 1 — Manage Customers (Priority: P1)

An admin views, creates, edits, and soft-deletes customer records. Each customer has a profile (name, email, phone), order statistics (`orders_count`, `total_spent`, `last_order_completed_at`), tags, internal notes, and marketing consent.

**Why this priority**: Customer management is a core CRM function; support agents access this daily to resolve issues, process returns, and apply credits.

**Independent Test**: Admin GETs `/api/v3/admin/customers`. Response includes paginated customer list with `id: "cus_…"`, `email`, `first_name`, `last_name`, `orders_count`, `total_spent`.

**Acceptance Scenarios**:

1. **Given** a customer with 3 completed orders, **When** admin views the customer, **Then** `orders_count: 3` and `total_spent` reflect the actual total
2. **Given** a customer belonging to Store A, **When** Store B admin lists customers, **Then** Store A's customer is not returned
3. **Given** admin creates a customer via API, **When** no password is provided, **Then** `skip_password_validation` allows creation without password
4. **Given** a customer with `tags: ["VIP", "wholesale"]`, **When** admin filters by tag, **Then** only tagged customers are returned
5. **Given** a soft-deleted customer, **When** listing with default scope, **Then** they are excluded

---

### User Story 2 — Manage Customer Addresses (Priority: P1)

Admin views, creates, and edits addresses for a customer. Each address has country/state validation, an optional label, and default billing/shipping flags.

**Why this priority**: Accurate addresses are needed for order fulfillment; support agents need to update addresses when customers report errors.

**Independent Test**: Admin POSTs to `/api/v3/admin/customers/:id/addresses` with a US address. Response has `id: "addr_…"`. Address appears in customer's address list.

**Acceptance Scenarios**:

1. **Given** a new customer, **When** admin adds a billing address, **Then** it is returned as the customer's default billing address
2. **Given** a customer with multiple addresses, **When** admin marks one as default shipping, **Then** previous default is updated automatically
3. **Given** a US address, **When** submitted without a state, **Then** 422 is returned (state required for US)
4. **Given** an address in a country without zipcode requirements, **When** submitted without zipcode, **Then** it is accepted

---

### User Story 3 — Bulk Operations on Customers (Priority: P2)

Admin adds or removes customers from groups in bulk, and exports customer data to CSV.

**Acceptance Scenarios**:

1. **Given** a selection of customers, **When** admin assigns them to "VIP" group in bulk, **Then** all selected customers are in the group
2. **Given** a customer list, **When** admin triggers CSV export, **Then** a file download is initiated via the export flow

---

### Edge Cases

- What if a customer email already exists on another store? → `email` uniqueness is scoped to `store_id`; same email can exist on different stores
- What if `Spree.user_class` is not LegacyUser? → Controllers reference `Spree.user_class`; the actual model can be a custom Devise user
- _(6.0)_ `Spree.user_class` → `Spree.customer_class`; URL `/customers` already in place from 5.5; prefix changes from `cus_` to `cust_` in 6.0

---

## Requirements

### Functional Requirements

- **FR-001**: Customer model is configurable via `Spree.user_class`; core ships `Spree::LegacyUser` (BCrypt, no Devise); production overrides with Devise
- **FR-002**: Prefix ID: `cus_` (5.5); renamed `cust_` in 6.0 with User→Customer rename
- **FR-003**: Computed attributes: `orders_count`, `total_spent`, `last_order_completed_at`
- **FR-004**: `tags` (array column or serialized) — filterable via Ransack
- **FR-005**: `marketing_opt_in` boolean for consent tracking
- **FR-006**: `skip_password_validation` in admin controller allows creation without password
- **FR-007**: Admin API URL: `/api/v3/admin/customers` (shipped from 5.5)
- **FR-008**: `Spree::Address` prefix `addr_`; paranoid soft-delete; country/state/zipcode validation configurable per country
- **FR-009**: Addresses nested under customers: `/api/v3/admin/customers/:id/addresses`
- **FR-010**: Address `default_billing` and `default_shipping` flags managed automatically on creation/update
- **FR-011**: `include Spree::Metafields` on Address
- **FR-012**: _(6.0)_ User→Customer rename per `6.0-platform-auth.md`; Devise dropped; own JWT stack

### Key Entities

- **Customer** (`Spree::LegacyUser` or custom via `Spree.user_class`): email, first/last name, phone, tags, internal notes, marketing opt-in. Prefix: `cus_`.
- **Address** (`Spree::Address`): first/last name, address1/2, city, state, country, zipcode, phone, label, default_billing, default_shipping. Prefix: `addr_`.

---

## Backend Requirements

### Data Model

- **Table**: `spree_users` — email, encrypted_password, first_name, last_name, phone, login, tags, internal_notes, marketing_opt_in, selected_locale, store_id, deleted_at, timestamps
- **Table**: `spree_addresses` — first_name, last_name, address1, address2, city, state_id, state_name, country_id, zipcode, phone, label, user_id, company, deleted_at, timestamps

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/customers` | List customers (paginated, Ransack) |
| POST | `/api/v3/admin/customers` | Create customer |
| GET | `/api/v3/admin/customers/:id` | Show customer |
| PATCH | `/api/v3/admin/customers/:id` | Update customer |
| DELETE | `/api/v3/admin/customers/:id` | Soft-delete customer |
| GET | `/api/v3/admin/customers/:id/addresses` | List addresses |
| POST | `/api/v3/admin/customers/:id/addresses` | Create address |
| GET | `/api/v3/admin/customers/:id/addresses/:id` | Show address |
| PATCH | `/api/v3/admin/customers/:id/addresses/:id` | Update address |
| DELETE | `/api/v3/admin/customers/:id/addresses/:id` | Soft-delete address |

### Serializer Fields

**Admin CustomerSerializer**:
- `id` (cus_…), `email`, `first_name`, `last_name`, `phone`, `login`, `sign_in_count`, `last_sign_in_at`, `orders_count`, `total_spent`, `last_order_completed_at`, `tags`, `internal_notes`, `marketing_opt_in`, `customer_group_ids`, `created_at`, `updated_at`, `deleted_at`

**Admin AddressSerializer**:
- `id` (addr_…), `customer_id` (cus_…), `first_name`, `last_name`, `address1`, `address2`, `city`, `state_id`, `state_name`, `country_id`, `zipcode`, `phone`, `label`, `default_billing`, `default_shipping`, `metadata`, `created_at`, `updated_at`, `deleted_at`

### Authorization

- CanCanCan: `can :manage, Spree.user_class`; `can :manage, Spree::Address`
- Ransack allowlist: `email`, `first_name`, `last_name`, `phone`, `tags`, `created_at`, `orders_count`

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/customers/index.tsx` — list with bulk group assignment, tag management, CSV export
- `packages/dashboard/src/routes/_authenticated/$storeId/customers/$customerId.tsx` — detail with addresses sub-section, orders list, store credits

### Hooks

- `packages/dashboard/src/hooks/use-customers.ts` — TanStack Query wrappers for CRUD + Ransack search

### i18n Keys

Under `admin.customers.*` and `admin.addresses.*` in all locale files.

---

## Success Criteria

- **SC-001**: Admin can list customers with computed order statistics
- **SC-002**: Admin can create a customer without a password via `skip_password_validation`
- **SC-003**: Address creation validates country/state requirements; returns 422 for invalid addresses
- **SC-004**: Default billing/shipping flags are managed automatically
- **SC-005**: Customers are store-scoped; Store B cannot access Store A's customers
- **SC-006**: _(6.0)_ User→Customer rename completes; prefix changes to `cust_`; Devise dropped

---

## Assumptions

- `Spree.user_class` is the indirection point; controllers never reference `Spree::User` directly
- `orders_count` and `total_spent` are computed via SQL aggregates or counters, not stored columns
- GDPR endpoints (data export, anonymization) are deferred per `5.4-6.0-eu-legal-compliance.md`
