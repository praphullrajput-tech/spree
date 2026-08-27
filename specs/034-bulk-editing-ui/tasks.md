---
description: "Task list template for feature implementation"
---

# Tasks: Bulk Editing UI

**Input**: Design documents from `specs/034-bulk-editing-ui/`

**Prerequisites**: plan.md, spec.md

**Note**: This feature is already implemented (brownfield migration). All
tasks below are marked complete and describe the shipped implementation for
traceability, not forward-looking work.

**Organization**: Tasks are grouped by user story from spec.md.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core`, `spree/api` build/test cleanly with the tag
      services + bulk_operations concern present
- [x] T002 [P] Confirm `pnpm typecheck && pnpm lint` passes with
      `bulk-action-bar.tsx` + `resource-table.tsx` selection wiring present

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T003 [spree/core] `Spree::Tags::BulkAdd` service in
      `spree/core/app/services/spree/tags/bulk_add.rb` —
      `insert_all`-based tagging, idempotent, touches affected records
- [x] T004 [spree/core] `Spree::Tags::BulkRemove` service in
      `spree/core/app/services/spree/tags/bulk_remove.rb` —
      `delete_all`-based untagging, touches affected records
- [x] T005 [spree/api] `Spree::Api::V3::BulkOperations` concern in
      `spree/api/app/controllers/concerns/spree/api/v3/bulk_operations.rb`
      — `bulk_add_tags`/`bulk_remove_tags` actions, `require_ids!` guard,
      `bulk_collection` (store + ability scoped), `decode_ids` (prefixed ID
      support), `bulk_tags_response`, overridable `bulk_record_count_key`
      and `after_bulk_tags_change` hooks
- [x] T006 [spree/admin] `Spree::Admin::BulkOperationsConcern` in
      `spree/admin/app/controllers/concerns/spree/admin/bulk_operations_concern.rb`
      — legacy Turbo-Stream equivalent, mirrors the API concern's shape
- [x] T007 [spree/api] `collection` bulk_* routes registered in
      `spree/api/config/routes.rb` under `resources :products` and
      `resources :customers`
- [x] T008 [packages/dashboard-core] `BulkAction<T>` type + `BulkActionBar`
      + `BulkActionBarLayout` in
      `packages/dashboard-core/src/components/bulk-action-bar.tsx` —
      immediate/confirm/form action shapes, CanCanCan visibility filter,
      success/error toast + query invalidation, overflow-menu layout,
      viewport/anchor-based positioning via `createPortal`
- [x] T009 [packages/dashboard-core] `<ResourceTable>` selection state
      (`selectedIds`, `selectionEnabled`) and `<BulkActionBar>` rendering in
      `packages/dashboard-core/src/components/resource-table.tsx`
- [x] T010 [packages/dashboard] i18next keys for
      `admin.components.bulk_action_bar.*` and `admin.actions.*` in
      `packages/dashboard/src/locales/en.json` /
      `packages/dashboard-core/src/locales/en.json`

**Checkpoint**: Foundation (generic mechanism, both sides) complete.

---

## Phase 3: User Story 1 - Select rows and run a bulk action (Priority: P1) 🎯 MVP

**Goal**: Any `<ResourceTable>` consumer can attach bulk actions via the
`bulkActions` prop with zero changes to the bar/table internals.

**Independent Test**: Select 3 products, run "Set status" via the sheet,
confirm all 3 update and selection clears.

### Tests for User Story 1

- [x] T011 [P] [US1] Playwright e2e in
      `packages/dashboard/e2e/products-bulk.spec.ts` covering selection,
      confirm/form action flows, and post-run state

### Implementation for User Story 1

- [x] T012 [US1] `bulkActions` wiring (status, categories, channels, tags)
      in `packages/dashboard/src/routes/_authenticated/$storeId/products/index.tsx`
- [x] T013 [US1] `bulkActions` wiring (customer groups, tags) in
      `packages/dashboard/src/routes/_authenticated/$storeId/customers/index.tsx`

**Checkpoint**: Generic mechanism proven against two real resources.

---

## Phase 4: User Story 2 - Bulk add/remove tags (Priority: P1)

**Goal**: Shared `bulk_add_tags`/`bulk_remove_tags` endpoints work
identically for Products and Customers via the shared concern.

**Independent Test**: `POST /api/v3/admin/products/bulk_add_tags` tags the
resolved `bulk_collection` and returns `{ product_count, tag_count }`.

### Tests for User Story 2

- [ ] T014 [P] [US2] RSpec service spec for `Spree::Tags::BulkAdd` in
      `spree/core/spec/services/spree/tags/bulk_add_spec.rb` — **NOT
      FOUND**, gap flagged in spec.md Migration Notes
- [ ] T015 [P] [US2] RSpec service spec for `Spree::Tags::BulkRemove` in
      `spree/core/spec/services/spree/tags/bulk_remove_spec.rb` — **NOT
      FOUND**, gap flagged in spec.md Migration Notes
- [ ] T016 [P] [US2] API integration spec for `bulk_add_tags`/
      `bulk_remove_tags` (missing-`ids` 422, cross-store ID exclusion) —
      **NOT FOUND**, gap flagged in spec.md Migration Notes

### Implementation for User Story 2

- [x] T017 [US2] `bulk_record_count_key` override (`product_count`) on the
      Admin API Products controller
- [x] T018 [US2] `bulk_record_count_key` override (`customer_count`) on the
      Admin API Customers controller
- [x] T019 [US2] `after_bulk_tags_change` override hooks where a controller
      needs post-tag side effects (e.g. search reindex)

**Checkpoint**: Tag bulk mutation confirmed shared and working end-to-end;
automated backend test gap explicitly recorded rather than silently closed.

---

## Phase 5: User Story 3 - Bulk price editing (Priority: P2)

**Goal**: Document the boundary — bulk price editing is a separate,
non-`BulkActionBar` mechanism (full detail lives in
`specs/011-pricing-and-price-lists`).

**Independent Test**: N/A here — see `specs/011-pricing-and-price-lists`.

### Implementation for User Story 3

- [x] T020 [US3] `<BulkPriceEditor>` (server-backed grid) in
      `packages/dashboard/src/components/spree/bulk-price-editor/bulk-price-editor.tsx`
- [x] T021 [US3] `<BulkPriceEditorDialog>` (modal wrapper) in
      `packages/dashboard/src/components/spree/bulk-price-editor/bulk-price-editor-dialog.tsx`
- [x] T022 [US3] `<ProductBulkPriceEditor>` (form-state-backed grid) in
      `packages/dashboard/src/components/spree/bulk-price-editor/product-bulk-price-editor.tsx`
- [x] T023 [US3] `Spree::Api::V3::Admin::PricesController#bulk_upsert` /
      `#bulk_destroy` in
      `spree/api/app/controllers/spree/api/v3/admin/prices_controller.rb`
      (cross-referenced, not re-implemented here — owned by
      `specs/011-pricing-and-price-lists`)

**Checkpoint**: Boundary between the generic bulk-action mechanism and the
bespoke price grid is documented; no duplicate spec content created.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T024 Verify `bulk_collection` scoping (store + CanCanCan) is
      consistent between the legacy concern and the API v3 concern
- [ ] T025 Backfill RSpec coverage for `Spree::Tags::BulkAdd`/`BulkRemove`
      and the `bulk_operations` concerns (gap — see spec.md Migration
      Notes; not part of this migration's scope, recorded for follow-up)
- [x] T026 Confirm all locale files (not just `en.json`) carry the
      `admin.components.bulk_action_bar.*` keys in both
      `packages/dashboard/src/locales/` and
      `packages/dashboard-core/src/locales/`

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** blocks all user stories.
- **US1** (generic mechanism proof) and **US2** (shared tag endpoints) are
  the P1 stories and were delivered together, since US1's `products/index.tsx`
  wiring exercises US2's endpoints directly.
- **US3** is documented for boundary clarity only; its real implementation
  and tasks live in `specs/011-pricing-and-price-lists`.
- **Polish (Phase 6)** identifies the one open gap (RSpec backend coverage)
  as a follow-up, not blocking this migration's "Status: migrated" mark.

## Notes

- This tasks.md reflects a **already-shipped** feature; checked boxes
  record what exists in the codebase today, not a forward plan.
- The two unchecked test tasks (T014-T016) and T025 are genuine gaps
  identified during migration, intentionally left unchecked rather than
  marked done to avoid overstating test coverage.
