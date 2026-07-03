# Feature Specification: Stock Transfers

**Feature Branch**: `main` (basic transfer shipped; 6.0 lifecycle + line items pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: `docs/plans/6.0-inventory-operations.md`

---

## User Scenarios & Testing

### User Story 1 — Transfer Stock Between Locations (Priority: P1)

An admin creates a stock transfer to move inventory from one location to another. Today's implementation is one-shot (atomic decrement + increment in one transaction). The 6.0 plan adds a draft → in_transit → received lifecycle with per-item line items and partial receive support.

**Why this priority**: Multi-location merchants cannot manage inventory without a way to move stock between locations.

**Independent Test**: Admin creates a transfer from "Brooklyn Warehouse" to "Manhattan Store" for 10 units of SKU-001. Transfer is saved with a number (T-XXXXX). Source location's `count_on_hand` decrements by 10; destination increments by 10. `GET /admin/stock_transfers/:id` shows the transfer and its stock movements.

**Acceptance Scenarios**:

1. **Given** two active stock locations, **When** admin creates a transfer with source/destination and variants/quantities, **Then** a transfer record is created with a generated number (T-prefix)
2. **Given** a completed transfer, **When** listing stock movements on the source location, **Then** a negative movement with `originator_type: "Spree::StockTransfer"` appears
3. **Given** a completed transfer, **When** listing stock movements on the destination location, **Then** a positive movement with the same `originator_id` appears
4. **Given** a transfer where source has insufficient stock, **When** submitted, **Then** 422 "Insufficient stock at source location"
5. **Given** `source_location_id == destination_location_id`, **When** submitted, **Then** 422 "Source and destination must differ"

---

### User Story 2 — Transfer Lifecycle (Priority: P1 — 6.0 Pending)

An admin manages the full lifecycle: create draft → review and confirm → mark in transit (decrement source) → receive at destination (increment destination, with optional partial receive). Partial receipts record discrepancies.

**Why this priority**: One-shot transfers cannot model "10 units left warehouse today, 8 arrived damaged" — a common real-world scenario.

**Independent Test** _(6.0)_: Admin creates a draft transfer, adds 10 units of SKU-001, marks it ready to ship, marks in transit (source decrements). On receive screen, admin enters 8 received and selects `discrepancy_reason: "damaged_in_transit"` for 2 units. Status becomes `partially_received`; destination gets +8 units.

**Acceptance Scenarios** _(6.0)_:

1. **Given** a `draft` transfer, **When** admin marks it ready, **Then** status becomes `ready_to_ship`; source stock unchanged
2. **Given** a `ready_to_ship` transfer, **When** admin marks in transit, **Then** status becomes `in_transit`; source decrements; `shipped` stock movements written
3. **Given** an `in_transit` transfer, **When** admin receives all units, **Then** status becomes `received`; destination increments; `received` stock movements written
4. **Given** an `in_transit` transfer, **When** admin receives fewer units than shipped, **Then** status becomes `partially_received`; discrepancy column captures the gap reason
5. **Given** a `draft` transfer, **When** admin cancels it, **Then** no stock movements are written; status becomes `cancelled`

---

### User Story 3 — View Transfer History (Priority: P2)

An admin views the list of all transfers with status filters (Draft / In Transit / Received / All) and can inspect each transfer's stock movements.

**Why this priority**: Inventory audits require a searchable history of what moved where and when.

**Independent Test**: `GET /admin/stock_transfers?q[source_location_id_eq]=...&q[status_eq]=received` returns received transfers from that location.

**Acceptance Scenarios**:

1. **Given** transfers with various statuses, **When** filtering by status, **Then** only matching transfers are returned
2. **Given** a completed transfer, **When** viewing its detail, **Then** all stock movements are listed with quantity, variant, and direction
3. **Given** an admin searching by transfer number, **When** filtering by `number_cont: "T-001"`, **Then** matching transfers appear

---

### Edge Cases

- What if a transfer is created from a nil source (legacy "external receive")? → Legacy path still works; 6.0 replaces with `PurchaseOrder` — `StockTransfer` will require non-nil source
- What if destination has no `StockItem` for the transferred variant? → Auto-created on transfer (or raises if `create_on_missing: false`)
- What if marking in transit fails mid-write? → Transaction rolls back; no partial stock movements written
- _(6.0)_ What if cancelling an `in_transit` transfer? → Merchant must choose: reverse source (as if it never shipped) or write off as shrinkage — no silent reversal

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::StockTransfer` has a generated number with `T` prefix (via `Spree::Core::NumberGenerator`)
- **FR-002**: Transfer creates `StockMovement` records: negative at source, positive at destination, both referencing the transfer as `originator`
- **FR-003**: Source and destination must be different active stock locations
- **FR-004**: Admin API: full CRUD for stock transfers; nested stock movements per transfer
- **FR-005**: All transfer IDs prefixed `st_…`
- **FR-006**: _(6.0 pending)_ Status machine: `draft → ready_to_ship → in_transit → partially_received → received → cancelled`
- **FR-007**: _(6.0 pending)_ First-class `StockTransferItem` line items with `quantity_shipped`, `quantity_received`, `discrepancy_reason`
- **FR-008**: _(6.0 pending)_ Two-phase stock movement: source decrements on `mark_in_transit`; destination increments on `receive`
- **FR-009**: _(6.0 pending)_ `PurchaseOrder` model replaces the legacy `source_location_id: nil` hack for vendor receives

### Key Entities

- **StockTransfer** (`Spree::StockTransfer`): `number` (T-prefix), `source_location_id`, `destination_location_id`, `reference`. Currently no status column. 6.0: `status` column + state machine. Prefix: `st_`.
- **StockMovement** (`Spree::StockMovement`): `stock_item_id`, `quantity`, `originator_type`, `originator_id`, `action`. Records the before/after of each transfer.
- _(6.0)_ **StockTransferItem**: `stock_transfer_id`, `variant_id`, `quantity_shipped`, `quantity_received`, `discrepancy_reason`, `condition`.

---

## Backend Requirements

### Data Model

- **Table**: `spree_stock_transfers`
- **Current columns**: `number`, `source_location_id`, `destination_location_id`, `reference`, `type` (STI column, currently unused), `created_at`
- **6.0 additions**: `status` string, `expected_at` datetime, line items via `spree_stock_transfer_items`
- **Number generation**: `Spree::Core::NumberGenerator` with prefix `T`

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/stock_transfers` | List transfers (Ransack-filterable) |
| POST | `/api/v3/admin/stock_transfers` | Create and execute transfer (current) |
| GET | `/api/v3/admin/stock_transfers/:id` | Show transfer |
| PATCH | `/api/v3/admin/stock_transfers/:id` | Update transfer |
| DELETE | `/api/v3/admin/stock_transfers/:id` | Delete transfer |
| _(6.0)_ POST | `/api/v3/admin/stock_transfers/:id/mark_in_transit` | Transition to in_transit |
| _(6.0)_ POST | `/api/v3/admin/stock_transfers/:id/receive` | Receive with per-item quantities |

### Serializer Fields

**Admin StockTransferSerializer**:
- `id` (st_…), `number`, `source_location_id` (sloc_…), `destination_location_id` (sloc_…), `reference`, `created_at`, `updated_at`
- _(6.0 adds)_: `status`, `expected_at`, embedded `items`

### Authorization

- CanCanCan: `can :manage, Spree::StockTransfer` for admin
- Ransack allowlist: `number`, `source_location_id`, `destination_location_id`, `reference`, `created_at`

---

## Frontend Requirements

### SPA Route

- `packages/dashboard/src/routes/_authenticated/$storeId/products/transfers.tsx` — list + create sheet

### Hooks

- `packages/dashboard/src/hooks/use-stock-transfers.ts` — TanStack Query wrappers for CRUD

### i18n Keys

Under `admin.stockTransfers.*` in all 6 locale files: page title, column headers (number, source, destination, reference, created_at), status labels _(6.0)_, form labels, toast messages, empty state.

---

## Success Criteria

- **SC-001**: Creating a transfer decrements source `count_on_hand` and increments destination `count_on_hand` atomically
- **SC-002**: Source and destination uniqueness is enforced (cannot transfer to self)
- **SC-003**: Transfer is findable by number in the admin list
- **SC-004**: _(6.0)_ Draft→in_transit→received lifecycle works with partial receive and discrepancy tracking
- **SC-005**: _(6.0)_ `PurchaseOrder` model replaces `source_location_id: nil` hack for vendor receives

---

## Assumptions

- Current implementation is one-shot — there is no `status` column today; the `type` STI column exists but is unused
- `source_location_id` can currently be `nil` for "external receive" (vendor receive hack); 6.0 makes both source and destination required
- The SPA transfers page currently creates one-shot transfers; lifecycle UI (draft/receive screens) is blocked on 6.0 typed movement primitives
