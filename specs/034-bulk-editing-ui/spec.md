# Feature Specification: Bulk Editing UI

**Feature Branch**: `034-bulk-editing-ui`

**Created**: 2026-08-24

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Select rows and run a bulk action (Priority: P1)

An admin selects several rows in a resource table (products, customers) and
runs a bulk action — set status, add/remove tags, add/remove from
categories/channels/groups — without opening each record individually.

**Why this priority**: This is the core mechanism; every other bulk
capability (tags, price editing) is built on top of it.

**Independent Test**: On the Products table, select 3 rows, click "Set
status" in the floating action bar, submit the sheet, and confirm all 3
rows reflect the new status and the selection clears.

**Acceptance Scenarios**:

1. **Given** one or more rows are selected in a `<ResourceTable>` configured
   with `bulkActions`, **When** the admin clicks an action with no `form`/
   `confirm`, **Then** it runs immediately against the selected IDs.
2. **Given** an action declares `confirm`, **When** clicked, **Then** a
   confirm dialog appears (title/message interpolated with the selection
   count `{n}`) before `run` executes.
3. **Given** an action declares `form`, **When** clicked, **Then** a
   parameter-collection UI (typically a Sheet) opens and `run` is invoked
   with the resolved form values on submit.
4. **Given** a bulk action succeeds, **When** it completes, **Then** the
   table's own query key is invalidated, any `invalidate` query keys the
   action declares are also invalidated, a success toast interpolates `{n}`,
   and the selection clears (`onDone`).
5. **Given** an action declares a CanCanCan `subject` the current admin
   cannot perform `action` (default `update`) on, **When** the bar renders,
   **Then** that action is hidden entirely.

### User Story 2 - Bulk add/remove tags (Priority: P1)

An admin bulk-tags or untags a set of products or customers via the shared
`bulk_add_tags` / `bulk_remove_tags` endpoints backed by
`Spree::Tags::BulkAdd` / `Spree::Tags::BulkRemove`.

**Why this priority**: Tagging is the one bulk operation implemented
identically across the legacy Rails admin (`BulkOperationsConcern`) and the
Admin API v3 (`Spree::Api::V3::BulkOperations`), and both product and
customer resources reuse it — it is the shared mechanism the ticket asks to
document, not the product/customer specifics.

**Independent Test**: `POST /api/v3/admin/products/bulk_add_tags` with
`{ ids: [...], tags: ['sale'] }` tags every accessible product in the store
matching those IDs and returns `{ product_count, tag_count }`.

**Acceptance Scenarios**:

1. **Given** `ids` is omitted from the request body, **When** the endpoint
   is called, **Then** it responds `422 missing_ids` (an explicit empty
   array is accepted as a no-op).
2. **Given** `ids` mixes prefixed (`prod_xxx`) and raw IDs, **When**
   `bulk_collection` resolves them, **Then** both forms decode correctly and
   cross-store or inaccessible IDs are silently dropped (not 404s).
3. **Given** the same tag names already exist on some records, **When**
   `bulk_add_tags` runs, **Then** `ActsAsTaggableOn::Tagging.insert_all` is a
   no-op for existing pairs (idempotent) and touches all affected records.

### User Story 3 - Bulk price editing (Priority: P2)

An admin edits many variant prices at once in a spreadsheet-like grid,
either scoped to a price list (`<BulkPriceEditorDialog>` +
`<BulkPriceEditor>`, server-backed via `/admin/prices` +
`/admin/prices/bulk_upsert`) or scoped to one product's variants inline on
the product form (`<ProductBulkPriceEditor>`, form-state-backed, no network
call until the parent form saves).

**Why this priority**: This is a specialized bulk-editing surface (covered
in depth by `specs/011-pricing-and-price-lists`); it is listed here only to
scope the boundary against the generic `BulkActionBar` mechanism — bulk
price editing does NOT use `BulkActionBar` at all; it is a bespoke grid.

**Independent Test**: Open "Edit prices" on a price list, change two cells,
click Save, and confirm `POST /admin/prices/bulk_upsert` fires once with
both rows and both cells clear their dirty state.

**Acceptance Scenarios**:

1. **Given** unsaved edits exist, **When** the admin tries to close the
   dialog or switch currency, **Then** a destructive confirm dialog warns
   before discarding.
2. **Given** a bulk_upsert row is missing `variant_id` or `currency`,
   **When** submitted, **Then** the API responds `422 invalid_prices` with
   per-row `details`.

### Edge Cases

- What happens when the selected IDs span more than one page of results?
  `selectedIds` is a `Set` tracked in `<ResourceTable>` state independent of
  pagination — selections persist across page changes until cleared.
- How does the system handle an action's `run` throwing mid-flight? The bar
  catches the error, shows `errorMessage` or the thrown message as a toast,
  and leaves the selection intact (no `onDone`) so the admin can retry.
- What happens when the floating bar's action list overflows the available
  width? `BulkActionBarLayout` measures an offscreen mirror and moves
  overflowing actions into a `⋯` dropdown menu, recomputed on resize.
- What happens to `bulk_collection` when an ID belongs to a different
  store? Both the legacy concern's `model_class.accessible_by(...)` and the
  API concern's `model_class.for_store(current_store).accessible_by(...)`
  filter it out before any tag mutation runs — no error, just excluded.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `<ResourceTable>` MUST support an optional `bulkActions` prop;
  when non-empty (and `reorder` is not active) it enables row-selection
  checkboxes and renders `<BulkActionBar>` for the current selection.
- **FR-002**: A `BulkAction` MUST support three interaction shapes:
  immediate (`run` only), confirm (`confirm` + `run`), and form (`form`
  render-prop resolving `formValues` passed to `run`).
- **FR-003**: The bar MUST filter actions by CanCanCan (`permissions.can(action.action ?? 'update', action.subject)`)
  when `subject` is declared; actions without a `subject` are always shown.
- **FR-004**: On successful `run`, the system MUST invalidate the table's
  own query key, any additional keys in `action.invalidate`, show a
  `{n}`-interpolated success toast, and clear the selection via `onDone`.
- **FR-005**: The Admin API v3 `Spree::Api::V3::BulkOperations` concern and
  the legacy `Spree::Admin::BulkOperationsConcern` MUST both expose
  `bulk_add_tags` / `bulk_remove_tags` actions backed by
  `Spree::Tags::BulkAdd` / `Spree::Tags::BulkRemove`, gated by
  `before_action :require_ids!` (API) that 422s when `ids` key is absent.
- **FR-006**: `bulk_collection` (both concerns) MUST scope to
  `accessible_by(current_ability, :update)` (API additionally scopes to
  `for_store(current_store)`) and silently drop IDs outside that scope.
- **FR-007**: The API concern's response MUST report counts under a
  controller-supplied key (`bulk_record_count_key`, e.g. `product_count`,
  `customer_count`) plus `tag_count`.
- **FR-008**: Host controllers MAY override `after_bulk_tags_change` to run
  side effects (e.g. search reindex, automatic-taxon rematching) after a
  bulk tag mutation.
- **FR-009**: The bulk price editors (`<BulkPriceEditor>`,
  `<ProductBulkPriceEditor>`) MUST NOT go through `BulkActionBar` — they are
  a separate spreadsheet-style editing surface with their own dirty-state
  tracking and save/discard flow (see `specs/011-pricing-and-price-lists`
  for the full price contract).

### Key Entities

- **BulkAction**: Frontend-only declarative descriptor (`key`, `label`,
  `icon`, optional `subject`/`action` for CanCanCan, optional `confirm`,
  optional `form`, `run`, optional `invalidate`, `successMessage`,
  `errorMessage`). Not persisted; lives in route component code.
- **Spree::Tags::BulkAdd / BulkRemove**: Service objects operating on
  `tag_names: Array<String>` and `records: Array<Taggable>`, upserting/
  deleting `ActsAsTaggableOn::Tagging` rows and touching affected records.
- **bulk_collection**: Ability-scoped `ActiveRecord::Relation` resolved from
  inbound `ids`, shared shape between the legacy and API concerns.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Tags::BulkAdd`, `Spree::Tags::BulkRemove` (`spree/core/app/services/spree/tags/`) |
| `spree/api` (Store/Admin API v3) | Yes | `Spree::Api::V3::BulkOperations` concern; `bulk_add_tags`/`bulk_remove_tags`/`bulk_status_update`/`bulk_add_to_categories`/etc. actions on Products/Customers Admin API controllers; `Spree::Api::V3::Admin::PricesController#bulk_upsert`/`#bulk_destroy` |
| `packages/dashboard` (admin SPA) | Yes | `products/index.tsx`, `customers/index.tsx` wire `bulkActions`; `components/spree/bulk-price-editor/*` |
| `packages/dashboard-ui` / `dashboard-core` | Yes | `dashboard-core/src/components/bulk-action-bar.tsx` (the generic mechanism), `resource-table.tsx` (selection + bar wiring), `dashboard-ui/src/spree/bulk-price-table` (grid primitive, referenced from dashboard) |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated types for bulk endpoints' request/response shapes (`PriceBulkUpsertRow`, etc.) |
| `docs/plans/` | No | No `docs/plans/` entry found governing this mechanism specifically; pricing bulk-upsert falls under price-list-related plans (out of scope here per the task's focus on the generic mechanism) |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints**: `POST /api/v3/admin/products/bulk_add_tags`,
  `POST /api/v3/admin/products/bulk_remove_tags`,
  `POST /api/v3/admin/customers/bulk_add_tags`,
  `POST /api/v3/admin/customers/bulk_remove_tags`,
  `POST /api/v3/admin/prices/bulk_upsert`,
  `DELETE /api/v3/admin/prices/bulk_destroy`
  (plus resource-specific bulk actions: `bulk_status_update`,
  `bulk_add_to_categories`, `bulk_add_to_channels`,
  `bulk_add_to_groups` — not detailed here, see the products/customers specs)
- **Serializer fields (read)**: N/A — bulk endpoints return summary counts
  (`{ product_count, tag_count }`, `{ price_count }`), not serialized
  resources
- **Auth**: Admin API — secret key + scopes or JWT + CanCanCan
  (`authorize! :update, model_class` inside `bulk_add_tags`/`bulk_remove_tags`;
  `authorize! :create/:update/:destroy, Spree::Price` in the prices
  controller)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can select any number of rows on a table and apply a
  bulk action without a full-page reload (SPA tables) or with a single
  Turbo Stream round-trip (legacy admin).
- **SC-002**: A bulk tag request with an invalid/missing `ids` param is
  rejected with a `422` before any database write occurs.
- **SC-003**: A bulk action against a mix of accessible and inaccessible
  (cross-store or unauthorized) IDs completes successfully against only the
  accessible subset — no partial-failure error surfaces to the admin.
- **SC-004**: Adding a new bulk action to any `<ResourceTable>` consumer
  requires zero changes to `<BulkActionBar>` or `resource-table.tsx` — only
  a new `BulkAction` object passed via the `bulkActions` prop.

## Assumptions

- The floating action bar's positioning logic (viewport-anchored vs.
  table-anchored, overflow measurement) is UI polish and is treated as
  implementation detail, not a testable requirement, beyond "the bar is
  reachable and overflow actions are not lost."
- This spec documents the *generic* `BulkActionBar` + `bulk_operations`
  mechanism only. Product-specific bulk actions (status, categories,
  channels) are covered by the products spec; customer-specific bulk
  actions (groups) by the customers spec; price bulk-editing in full by
  `specs/011-pricing-and-price-lists`; CSV export/import bulk operations by
  `specs/022-exports`.
- The legacy Rails admin (`spree/admin/app/controllers/spree/admin/price_list_products_controller.rb`,
  `bulk_editor_controller.js` Stimulus controller) is being phased out per
  `docs/plans/6.0-admin-spa.md` — no new legacy bulk-editing surfaces should
  be built there.

## Migration Notes

- **Overlap boundary**: This spec intentionally does NOT re-describe price
  list mechanics (`specs/011-pricing-and-price-lists` owns
  `Spree::Prices::BulkUpsert`, the price-list product association, currency/
  market-locale normalization) or export mechanics (`specs/022-exports` owns
  `ExportButton`, `Spree::Export`, `record_selection`). Only the shared
  `BulkActionBar` component and the `bulk_operations` concerns are detailed
  here.
- **No dedicated tests found**: no RSpec spec files for
  `Spree::Tags::BulkAdd`/`BulkRemove` or the `bulk_operations` concerns were
  located under `spree/core/spec` or `spree/api/spec` during this
  migration; `packages/dashboard/e2e/products-bulk.spec.ts` is the only
  automated coverage located for the frontend mechanism. This is a gap —
  no `docs/plans/` entry tracks it, and it should be flagged for backfill
  rather than assumed intentional.
- **Legacy vs. v3 duplication**: `Spree::Admin::BulkOperationsConcern` and
  `Spree::Api::V3::BulkOperations` are hand-kept-in-sync duplicates (the API
  concern's comments explicitly say "mirrors the legacy concern"). No
  shared base module exists between them; a future consolidation is
  possible but out of scope for this migration.
- **`docs/plans/` gap**: no active or shipped plan in `CLAUDE.md`'s list
  specifically governs "bulk editing" as an architectural concern — it grew
  organically per-resource. If a cross-cutting redesign (e.g. a shared
  `Spree::BulkOperation` model with async processing for very large
  selections) is ever proposed, it would need a new `docs/plans/` entry per
  Constitution Principle VI.
- **Scale limits undocumented**: neither concern imposes a max on `ids.size`
  or `tags.size`; bulk_add_tags builds an in-memory attributes array before
  `insert_all`. Behavior on very large selections (e.g. "select all 50,000
  products") is unverified and not covered by the current tests.
