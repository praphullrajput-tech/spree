---

description: "Task list template for feature implementation"
---

# Tasks: Data Grid Component

**Input**: Design documents from `/specs/035-data-grid-component/`

**Prerequisites**: plan.md, spec.md

**Tests**: Included as already-satisfied (reverse-engineered brownfield entry — code and any tests already exist and ship on `main`).

**Organization**: Tasks are grouped by user story, matching spec.md's priorities (P1, P2, P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Could have run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All tasks are marked complete — this reflects already-shipped code, not planned work.

## Path Conventions

- Shared frontend primitive: `packages/dashboard-ui/src/spree/data-grid/...` (headless, no hooks/providers from outside this package)
- Composed consumers: `packages/dashboard-ui/src/spree/{bulk-price-table.tsx,storefront-visible-switch.tsx}`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the touched module builds/tests cleanly

- [x] T001 [P] Baseline frontend: `pnpm typecheck && pnpm lint` passes at workspace root for `packages/dashboard-ui`
- [x] T002 [P] `@tanstack/react-table` and `@tanstack/react-hotkeys` present as dependencies of `packages/dashboard-ui`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core grid infrastructure that all cell types and interactions build on

- [x] T003 [packages/dashboard-ui] Define coordinate/registration types in `packages/dashboard-ui/src/spree/data-grid/types.ts` (`CellCoords`, `CellKey`, `cellKey()`, `GridMode`, `CellRegistration`, `RenderSectionHeader<T>`)
- [x] T004 [packages/dashboard-ui] Define shared grid state context in `packages/dashboard-ui/src/spree/data-grid/context.ts` (`DataGridContext`, `DataGridContextValue`, `useDataGridContext()`, `coordsInRect()`, `modeFor()`)
- [x] T005 [packages/dashboard-ui] Implement `useStableCellRegistration` in `packages/dashboard-ui/src/spree/data-grid/use-stable-cell-registration.ts` — ref-threaded handlers/`registerCell` so the registration effect's deps are only `[row, col]`
- [x] T006 [packages/dashboard-ui] Implement `DataGrid<T>` / `DataGridShell` / `DataGridRow` / `DataGridKeyboardMount` in `packages/dashboard-ui/src/spree/data-grid/data-grid.tsx` — wraps `useReactTable` (core row model only), owns `anchor`/`extent`/`editing`/`bounds` state, section-header row rendering, and blur-to-clear-selection behavior
- [x] T007 [packages/dashboard-ui] Implement `editableRowIndex` helper in `packages/dashboard-ui/src/spree/data-grid/helpers.ts` for mapping table row ids to flat editable-only coords
- [x] T008 [packages/dashboard-ui] Export the public surface from `packages/dashboard-ui/src/spree/data-grid/index.ts` (`DataGrid`, cell components, `useDataGridContext`, `editableRowIndex`, `CellCoords`/`RenderSectionHeader` types)

**Checkpoint**: Foundation ready — cell types and interaction layers can build on the context/registration primitives

---

## Phase 3: User Story 1 - Keyboard-driven spreadsheet navigation (Priority: P1) 🎯 MVP

**Goal**: Arrow/Tab/Shift+Arrow/Enter/Escape navigation and selection scoped to the grid's DOM subtree

**Independent Test**: Render `<DataGrid>`, verify arrow keys move `anchor`, Shift+Arrow extends `extent`, Tab/Shift+Tab walk columns with row-wrap and edge hand-off to the browser, Enter enters edit mode.

### Implementation for User Story 1

- [x] T009 [US1] Implement `useDataGridKeyboard` in `packages/dashboard-ui/src/spree/data-grid/use-data-grid-keyboard.ts`: `useHotkey`-scoped bindings for ArrowUp/Down/Left/Right, Shift+Arrow*, Tab/Shift+Tab (with edge hand-off to the browser), Enter (enter edit mode), Escape (collapse extent to anchor) — all `enabled: !ctx.editing`
- [x] T010 [US1] Implement `findExistingCoords` sparse-cell fallback inside `use-data-grid-keyboard.ts` so navigation skips unregistered slots in the direction of travel
- [x] T011 [US1] Wire `onBlurCapture` on the grid `<table>` in `data-grid.tsx` to clear `anchor`/`extent`/`editing` when focus leaves the grid subtree entirely

**Checkpoint**: Keyboard navigation fully functional and independently testable

---

## Phase 4: User Story 2 - Copy, fill-down, and drag fill handle (Priority: P2)

**Goal**: Cmd/Ctrl+C/V/D bulk operations plus a pointer-drag fill handle for column fill-down

### Implementation for User Story 2

- [x] T012 [US2] Implement Delete/Backspace clear-selected in `use-data-grid-keyboard.ts` (`canWrite('')` gated)
- [x] T013 [US2] Implement Cmd/Ctrl+D fill-down (per-column top-cell broadcast, `canWrite` gated) in `use-data-grid-keyboard.ts`
- [x] T014 [US2] Implement Cmd/Ctrl+C TSV clipboard write (rectangular bounding box, blank for unregistered slots, silent catch) in `use-data-grid-keyboard.ts`
- [x] T015 [US2] Implement Cmd/Ctrl+V single-value clipboard broadcast (first line/first column only, silent catch) in `use-data-grid-keyboard.ts`
- [x] T016 [US2] Implement `FillHandle` in `packages/dashboard-ui/src/spree/data-grid/fill-handle.tsx`: position at the selection's far corner via `getElement()` + `getBoundingClientRect`, pointer-capture drag, column-constrained preview driving `ctx.setExtent`, commit-on-release write loop skipping the source row
- [x] T017 [US2] Mount `<FillHandle>` inside `DataGridShell` in `data-grid.tsx`, gated on `anchor && extent && !editing`

**Checkpoint**: Bulk copy/fill/clear operations functional independently of typed-cell specifics

---

## Phase 5: User Story 3 - Typed editable cell primitives (Priority: P2)

**Goal**: The concrete cell components consumers compose into a grid

### Implementation for User Story 3

- [x] T018 [P] [US3] Implement `NumberCell` in `packages/dashboard-ui/src/spree/data-grid/cells.tsx` — read-only-in-selection-mode input, Enter/Escape/Tab in-cell handling, integer truncation on write
- [x] T019 [P] [US3] Implement `MoneyCell` in `cells.tsx` — locale decimal-separator display formatting, currency `symbol` prefix, raw-string passthrough to `onChange` (no frontend locale parsing), `getElement` wiring for the fill handle
- [x] T020 [P] [US3] Implement `SwitchCell` in `cells.tsx` — Space/Enter toggle, `canWrite` accepting boolean-ish strings (`true/false/1/0/yes/no/''`)
- [x] T021 [P] [US3] Implement `SelectCell<V>` in `cells.tsx` — fixed `options` picker, `canWrite` restricted to the option set (or empty)
- [x] T022 [P] [US3] Implement `ReadOnlyCell` in `cells.tsx` — non-registered, non-interactive label cell
- [x] T023 [US3] Compose the above into `BulkPriceTable` in `packages/dashboard-ui/src/spree/bulk-price-table.tsx` (variant/SKU read-only columns + amount/compareAt `MoneyCell` columns, search + pagination footer, section-header grouping by product)

**Checkpoint**: All user stories independently functional; `BulkPriceTable` demonstrates the full composition

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T024 Confirm headless boundary: no import of `packages/dashboard` or `packages/dashboard-core` anywhere under `packages/dashboard-ui/src/spree/data-grid/` (constitution Principle I) — verified during this migration, no violation found
- [x] T025 [P] `pnpm typecheck && pnpm lint` clean for `packages/dashboard-ui`

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** blocks all user stories
- **US1 (Phase 3)** depends only on Foundational; independently testable (navigation alone)
- **US2 (Phase 4)** depends on Foundational + the selection state US1 exercises, but its copy/fill/clear logic is independently testable given any populated `cells` map
- **US3 (Phase 5)** depends on Foundational (`useStableCellRegistration`, context); each cell type task is parallelizable, then composed in `BulkPriceTable`
- **Polish (Phase 6)** depends on all prior phases

## Notes

- This tasks.md documents already-implemented, already-shipped code (brownfield reverse-engineering) — all tasks are checked off as historical record, not a forward execution plan.
- No RSpec/backend tasks — this feature has zero backend footprint.
- No Playwright e2e tasks scoped to this feature directly; e2e coverage of the composed `BulkPriceTable` flow belongs to whichever `packages/dashboard` route consumes it (out of scope for this spec).
