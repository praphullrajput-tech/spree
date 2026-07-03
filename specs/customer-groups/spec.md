# Feature Specification: Customer Groups

**Feature Branch**: `main` (fully shipped)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: None dedicated

---

## User Scenarios & Testing

### User Story 1 — Manage Customer Groups (Priority: P1)

An admin creates and manages customer groups (e.g., "VIP", "Wholesale", "Staff"). Groups can be used to target promotions, price lists, and shipping rules. Each group has a name, optional description, and a count of assigned customers.

**Why this priority**: Customer segmentation drives pricing and promotion targeting; without groups, merchants cannot apply differentiated treatment.

**Independent Test**: Admin POSTs to `/api/v3/admin/customer_groups` with `{ name: "VIP" }`. Response has `id: "cg_…"`. Group appears in the list.

**Acceptance Scenarios**:

1. **Given** no groups, **When** admin creates "VIP", **Then** it appears with `cg_…` ID
2. **Given** a soft-deleted group, **When** listing with default scope, **Then** it is excluded
3. **Given** a group belonging to Store A, **When** Store B admin lists groups, **Then** Store A's group is not returned
4. **Given** a group, **When** admin updates its name, **Then** the new name is reflected in the response

---

### User Story 2 — Assign Customers to Groups (Priority: P1)

Admin assigns and removes individual customers from groups. Bulk assignment is supported via the customer list in the dashboard.

**Why this priority**: Groups are only useful when customers are assigned; assignment is the primary operation on groups after creation.

**Independent Test**: Admin POSTs to `/api/v3/admin/customer_groups/:id/customers` with a list of customer IDs. Those customers are now members of the group. `customers_count` on the group increments.

**Acceptance Scenarios**:

1. **Given** a group, **When** admin assigns 3 customers, **Then** `customers_count: 3`
2. **Given** a customer already in the group, **When** added again, **Then** no duplicate join record is created
3. **Given** a group member, **When** removed from the group, **Then** they no longer appear in the group's customer list
4. **Given** a group with members, **When** the group is soft-deleted, **Then** members are not deleted (only group record is soft-deleted)

---

### Edge Cases

- What if a group name is duplicated within a store? → Validated at model level; 422 returned
- What if a customer is deleted? → Join record orphaned; `customers_count` may be stale (cleaned up via `dependent: :destroy` on join)

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::CustomerGroup` prefix `cg_`; paranoid soft-delete
- **FR-002**: Many-to-many with customers via `spree_customer_group_users` join table (`Spree::CustomerGroupUser`)
- **FR-003**: `customers_count` counter cache on group
- **FR-004**: Store-scoped via `Spree::SingleStoreResource`
- **FR-005**: Admin API: full CRUD + bulk customer assignment action
- **FR-006**: `expand=customers` query param returns inline customer list (paginated separately by default)

### Key Entities

- **CustomerGroup** (`Spree::CustomerGroup`): `name`, `description`, `store_id`, `customers_count`, `deleted_at`. Prefix: `cg_`.
- **CustomerGroupUser** (`Spree::CustomerGroupUser`): `customer_group_id`, `user_id` (polymorphic user_type). Join model.

---

## Backend Requirements

### Data Model

- **Table**: `spree_customer_groups` — `name string null: false`, `description text`, `store_id string null: false`, `customers_count integer`, `deleted_at`, timestamps
- **Table**: `spree_customer_group_users` — `customer_group_id string null: false`, `user_id string null: false`, `user_type string null: false`, timestamps

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/customer_groups` | List groups (store-scoped) |
| POST | `/api/v3/admin/customer_groups` | Create group |
| GET | `/api/v3/admin/customer_groups/:id` | Show group |
| PATCH | `/api/v3/admin/customer_groups/:id` | Update group |
| DELETE | `/api/v3/admin/customer_groups/:id` | Soft-delete group |

### Serializer Fields

**Admin CustomerGroupSerializer**:
- `id` (cg_…), `name`, `description`, `customers_count`, `store_id`, `created_at`, `updated_at`, `deleted_at`

### Authorization

- CanCanCan: `can :manage, Spree::CustomerGroup`
- Ransack allowlist: `name`, `created_at`, `customers_count`

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/customers/groups.tsx` — list + create/edit groups; inline member management via autocomplete

### Hooks

- `packages/dashboard/src/hooks/use-customer-groups.ts` — TanStack Query wrappers with pagination

### i18n Keys

Under `admin.customerGroups.*` in all locale files.

---

## Success Criteria

- **SC-001**: Admin can create a customer group and assign customers
- **SC-002**: `customers_count` reflects actual membership
- **SC-003**: Groups are store-scoped; Store B cannot access Store A's groups
- **SC-004**: Soft-deleting a group does not delete its members

---

## Assumptions

- Customer group membership does not expire (no TTL on join records)
- Price list and promotion targeting via groups is managed on the promotion/price list side, not here
- Bulk member export is out of scope for this feature (CSV export covered by admin-spa-csv-export plan)
