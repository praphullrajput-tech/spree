# Feature Specification: Data Grid Component

**Feature Branch**: `035-data-grid-component`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing code (brownfield migration) — no original feature description; behavior inferred from `packages/dashboard-ui/src/spree/data-grid/{data-grid.tsx,cells.tsx,context.ts,types.ts,fill-handle.tsx,use-data-grid-keyboard.ts,use-stable-cell-registration.ts,helpers.ts,index.ts}` and its consumers `packages/dashboard-ui/src/spree/bulk-price-table.tsx` and `packages/dashboard-ui/src/spree/storefront-visible-switch.tsx`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keyboard-driven spreadsheet navigation (Priority: P1)

An admin editing a bulk table (e.g. variant prices) navigates cell-to-cell with arrow keys, Tab/Shift+Tab, extends a selection with Shift+Arrow, and enters/exits edit mode with Enter/Escape — mirroring Excel/Google Sheets conventions rather than a plain HTML table.

**Why this priority**: Without keyboard navigation the grid is just a `<table>` of inputs; the navigation model is the entire reason this primitive exists instead of a plain form grid.

**Independent Test**: Render `<DataGrid>` with a few rows/columns, focus a cell, and verify arrow keys move the anchor, Shift+Arrow extends `extent`, Tab moves to the next column (wrapping to the next row at the last column), and Enter toggles `editing` for the focused cell.

**Acceptance Scenarios**:

1. **Given** a cell is focused (the grid's `anchor`), **When** ArrowDown/ArrowUp/ArrowLeft/ArrowRight is pressed, **Then** the anchor+extent move one cell in that direction, clamped to `bounds.maxRow`/`bounds.maxCol` with no wrap-around, and the target cell's `focus()` is invoked.
2. **Given** a cell is focused, **When** Shift+Arrow is pressed, **Then** only `extent` moves (the anchor stays put), producing a growing rectangular selection.
3. **Given** the anchor is not the last cell, **When** Tab is pressed, **Then** the grid moves right one column, or wraps to column 0 of the next row when at the last column; at the true last cell, Tab is left unhandled so the browser can focus the next form field outside the grid.
4. **Given** a cell is focused and not editing, **When** Enter is pressed, **Then** `editing` is set to that cell's coords, routing subsequent keys into the cell itself.
5. **Given** a sparse row (a column index with no registered cell), **When** navigating in that direction, **Then** `findExistingCoords` walks further in the same direction until it finds a registered cell, rather than landing on a non-existent slot.

---

### User Story 2 - Copy, fill-down, and clear across a selection (Priority: P2)

An admin selects a range of cells and uses Cmd/Ctrl+C to copy as TSV, Cmd/Ctrl+V to broadcast a single clipboard value across the selection, Cmd/Ctrl+D to fill the top cell of each selected column downward, and Delete/Backspace to clear the selection — plus a drag handle (the fill handle) that performs the same fill-down interactively by dragging from the selection's bottom-right corner.

**Why this priority**: These bulk operations are what make the grid faster than editing rows one at a time; they're the primary productivity payoff over a plain table, but the grid is still usable (just slower) without them.

**Independent Test**: Select two cells in a column with different values, press Cmd/Ctrl+D, and verify the lower cell's value now equals the upper cell's (via each cell's registered `read()`), skipping cells whose `canWrite()` rejects the source value.

**Acceptance Scenarios**:

1. **Given** two or more cells selected in the same column(s), **When** Cmd/Ctrl+D is pressed, **Then** each column's top-most selected cell's value is broadcast to the rest of that column's selection, cell by cell, via `write()`, skipping any cell where `canWrite(source)` is false.
2. **Given** a selection of cells, **When** Cmd/Ctrl+C is pressed, **Then** the selection's `read()` values are serialized as tab/newline-delimited TSV (rectangular bounding box, blank for unregistered slots) and written to the OS clipboard; a clipboard failure (non-secure context, unfocused page) is swallowed silently.
3. **Given** a selection of cells, **When** Cmd/Ctrl+V is pressed, **Then** the first line/first column of clipboard text is broadcast to every selected cell that accepts it (`canWrite`) — multi-cell TSV-shaped paste is explicitly out of scope for this version.
4. **Given** a selection of cells, **When** Delete or Backspace is pressed (and not currently editing), **Then** every selected cell that accepts an empty string (`canWrite('')`) is written to `''`.
5. **Given** a selection with `anchor`/`extent` set and not editing, **When** the user pointer-drags from the fill handle (rendered at the bottom-right of the far-corner cell) down or up within the same column, **Then** the drag preview updates `extent` live, and on release the anchor cell's value is copied into every cell between the anchor and the release row (source row skipped).

---

### User Story 3 - Typed editable cell primitives (Priority: P2)

A consumer composes a grid out of typed cell components — `NumberCell` (integer quantities), `MoneyCell` (currency-formatted decimal amounts, locale-aware display), `SwitchCell` (boolean toggle, no separate edit mode), `SelectCell` (fixed-option picker), and `ReadOnlyCell` (non-interactive label/link column, not registered with the grid) — each of which self-registers its read/write/focus/canWrite contract with the grid via `useStableCellRegistration`.

**Why this priority**: The grid's navigation/fill/keyboard machinery is inert without cell types to plug into it; this is the extension surface every consumer (`BulkPriceTable`, future bulk editors) actually touches.

**Independent Test**: Render a `MoneyCell` and a `SwitchCell` standalone inside a `<DataGrid>`, verify each renders correctly formatted, and that typing/toggling calls the cell's `onChange` while the grid's registered `read()`/`write()` reflect the current value.

**Acceptance Scenarios**:

1. **Given** a `NumberCell` in selection mode (not editing), **When** the underlying `<input>` is focused, **Then** it is `readOnly` so arrow keys are forwarded to grid navigation instead of moving the caret; double-click or Enter switches it into edit mode, focusing and selecting the text.
2. **Given** a `MoneyCell` bound to a canonical decimal string (`"12.50"`), **When** rendered outside edit mode, **Then** it displays the value with the locale `decimal` separator substituted for `.` and a non-editable currency `symbol` prefix; on commit the user's raw typed string (not re-parsed) is passed to `onChange`, deferring locale parsing to the backend's `Spree::LocalizedNumber`.
3. **Given** a `SwitchCell`, **When** Space or Enter is pressed while it has focus, **Then** `onChange(!value)` fires — there is no separate edit mode since the control is a single-action toggle.
4. **Given** a `SelectCell` with a fixed `options` list, **When** a value is registered for fill/paste, **Then** `canWrite` only accepts values present in `options` (or empty string), rejecting arbitrary pasted text.
5. **Given** a `ReadOnlyCell` (e.g. variant label or SKU column), **When** the grid computes bounds/navigation, **Then** that column is skipped entirely since `ReadOnlyCell` never calls `useStableCellRegistration`.

---

### Edge Cases

- What happens when a row is rendered via `renderSectionHeader` (a group header row, e.g. "Product: Blue Hoodie")? It spans all columns, is not registered with the grid, and is skipped by keyboard navigation and `editableRowIndex` (which only counts `kind === 'item'` rows toward coords).
- How does the grid handle focus leaving it entirely (e.g. Tab out to a form field below)? `onBlurCapture` on the `<table>` checks whether `relatedTarget` is still inside the grid; if not, `anchor`/`extent`/`editing` are all cleared so a later focus-in starts clean.
- How does the fill handle behave mid-drag if the pointer moves outside the same column? The handle constrains the preview to the source (anchor) column regardless of pointer X position — fill only ever flows down/up a single column, matching Excel's default drag behavior.
- What happens if `Cmd/Ctrl+C`/`V` clipboard access throws (insecure context, unfocused document, permission denied)? Both handlers wrap the clipboard call in try/catch and no-op silently — there is no toast, since these are routine, high-frequency key combinations.
- What happens when cell registration churns on every render (e.g. a `Controller`-driven value change)? `useStableCellRegistration` reads handlers/`registerCell` through refs so the registration effect's dependency array is just `[row, col]`, avoiding unregister/re-register loops and the resulting `setState`-during-render bounds recalculation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `DataGrid<T>` MUST wrap a TanStack `useReactTable` instance (`getCoreRowModel` only — no built-in sorting/filtering) and render an ordinary `<table>`/`<thead>`/`<tbody>`, delegating cell content to the caller's `ColumnDef` definitions via `flexRender`.
- **FR-002**: The grid MUST expose selection state (`anchor`, `extent`, `editing`, cell registration map, `bounds`) through `DataGridContext`, a plain React context local to this component tree — not a cross-cutting app provider.
- **FR-003**: Cells MUST self-register their `{ coords, focus, read, write, canWrite, getElement? }` contract via `useStableCellRegistration`, and MUST unregister on unmount; the grid recomputes `bounds` (`maxRow`/`maxCol`) from the live registration map on every register/unregister.
- **FR-004**: Keyboard navigation (arrows, Shift+arrows, Tab/Shift+Tab, Enter, Escape, Delete/Backspace, Mod+C/V/D) MUST be scoped to the grid's DOM subtree via `useHotkey(..., { target: gridRef })` from `@tanstack/react-hotkeys`, and MUST be disabled (`enabled: !ctx.editing`) while a cell is in edit mode so the cell owns its own key handling.
- **FR-005**: Sparse rows (a column index with no registered cell in some rows) MUST be handled by walking further in the direction of travel (`findExistingCoords`) rather than landing on a dead slot.
- **FR-006**: The fill handle MUST render only when there is an active selection (`anchor`/`extent` both set) and the grid is not in edit mode; it MUST constrain drag-fill to the anchor's column (vertical fill only, matching Excel's default).
- **FR-007**: Each typed cell (`NumberCell`, `MoneyCell`, `SwitchCell`, `SelectCell`) MUST implement `canWrite(value: string): boolean` so paste/fill-down/clear operations can reject values the cell's type can't represent (e.g. `SelectCell` rejects values outside its `options`).
- **FR-008**: `ReadOnlyCell` MUST NOT call `useStableCellRegistration`, so it is invisible to grid navigation, selection, fill, and copy/paste.
- **FR-009**: `MoneyCell` MUST display canonical API decimal strings with the caller-supplied locale `decimal` separator, but MUST pass the user's raw typed input to `onChange` unparsed, leaving locale-aware parsing to the backend.
- **FR-010**: The package MUST NOT import any provider, hook, or singleton from `packages/dashboard` or `packages/dashboard-core` — all state is local `useState`/context created and consumed within `packages/dashboard-ui/src/spree/data-grid/`, per the dashboard-ui headless-primitive rule (Module Boundaries, constitution Principle I).

### Key Entities *(include if feature involves data)*

- **CellCoords**: `{ row: number; col: number }` — a flat row index across the rendered table (post section-header insertion) and a column index in editable order. Used for keyboard nav, selection, and the registration map's key (`cellKey`, a `${row}.${col}` template literal type).
- **CellRegistration**: The contract each editable cell registers with the grid — `coords`, `focus()`, `read(): string`, `write(value: string)`, `canWrite(value: string): boolean`, and optional `getElement(): HTMLElement | null` (used by the fill handle for hit-testing/positioning).
- **DataGridContextValue**: The grid's shared state — the live `cells` map, `bounds`, `anchor`/`extent`/`editing` coords, their setters, `registerCell`, and selector helpers (`isSelected`, `selectedCells`).
- **GridMode**: `'select' | 'edit'` — derived per-cell via `modeFor(editing, coords)`, not stored directly; determines whether a cell's input is read-only (forwarding keys to grid nav) or live-editable.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | No | — |
| `spree/api` (Store/Admin API v3) | No | — |
| `packages/dashboard` (admin SPA) | No (consumer only) | Consumes the grid indirectly through `BulkPriceTable` (e.g. `packages/dashboard/src/components/spree/products/variants-section.tsx`) — no direct import of `data-grid/*` expected from route/form code. |
| `packages/dashboard-ui` / `dashboard-core` | Yes | Primitive lives entirely in `packages/dashboard-ui/src/spree/data-grid/` (`data-grid.tsx`, `cells.tsx`, `context.ts`, `types.ts`, `fill-handle.tsx`, `use-data-grid-keyboard.ts`, `use-stable-cell-registration.ts`, `helpers.ts`, `index.ts`), plus the composed consumers `bulk-price-table.tsx` and `storefront-visible-switch.tsx` in the same package. No `dashboard-core` registry/provider involvement. |
| `packages/sdk` / `packages/admin-sdk` | No | — |
| `docs/plans/` | No | Pure UI primitive; not an architectural change to a backend model, API surface, or cross-cutting rename — no `docs/plans/` entry governs it. |

### API Contract *(include if feature touches spree/api)*

N/A — this feature does not touch `spree/api`. Cell values (e.g. money amounts) are passed in as already-fetched data and written back via caller-supplied `onChange` callbacks; the grid has no knowledge of API endpoints, serializers, or auth.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can move between every editable cell in a grid using only Tab/Shift+Tab or arrow keys, without the mouse, reaching every registered cell.
- **SC-002**: Selecting N cells in one column and pressing Cmd/Ctrl+D updates N-1 cells to match the top cell's value in a single keystroke, with no per-cell manual edits required.
- **SC-003**: Dragging the fill handle down a column previews the target range live (selection highlight follows the pointer) and commits on release with no intermediate flicker or lost keystrokes.
- **SC-004**: Cell registration churn (e.g. a value updating on every keystroke) does not cause the grid's `bounds` to recompute more than once per actual add/remove of a cell — verified by the ref-based `useStableCellRegistration` effect depending only on `[row, col]`.

## Assumptions

- The grid targets desktop pointer + full physical keyboard usage (Excel-style shortcuts); no dedicated touch/mobile interaction model is assumed or supported.
- Consumers are responsible for providing stable `getRowId` and translating any grouped/sectioned data into the flat `rows` + `renderSectionHeader` shape — the grid itself has no concept of grouping beyond "does this row render a header instead of cells."
- Only single-column vertical fill and single-value copy/paste are supported; multi-cell rectangular TSV paste (matching an Excel copy of a 2D range) is explicitly deferred, per the comment in `use-data-grid-keyboard.ts`.
- The component assumes a moderate number of rendered cells per grid (the fill handle's pointer-move hit-testing does a linear scan over the registration map, commented as "small (<a few hundred cells per grid)") — no virtualization is implemented; very large grids are out of scope for this version.

## Migration Notes

**Keyboard navigation.** `use-data-grid-keyboard.ts` binds all shortcuts through `useHotkey` from `@tanstack/react-hotkeys`, scoped to the grid's DOM node (`target: gridRef`) and gated off entirely while a cell is editing (`enabled: !ctx.editing`) so cell-local key handling (Enter/Escape/Tab inside `NumberCell`/`MoneyCell`) takes over instead. Plain arrows move `anchor`+`extent` together (clamped to `bounds`, no wrap); Shift+arrows move only `extent`, growing a rectangular selection; Tab/Shift+Tab walk column-then-row-wrap but explicitly *don't* `preventDefault` at the grid's edges, letting the browser hand focus to the next/previous form field outside the grid. Sparse columns are handled by `findExistingCoords`, which steps further in the travel direction until it finds a populated registration slot.

**Fill-handle drag-to-copy.** `fill-handle.tsx` renders a small absolutely-positioned handle at the bottom-right of the selection's far corner (measured via each cell's `getElement()` and the grid table's own bounding rect, re-measured on window resize/scroll). Pointer-down captures the pointer and records the *anchor* cell's value as the fill source (matching Excel, which always fills from the top/first cell of a selection regardless of drag direction). Pointer-move hit-tests the DOM node under the cursor by linear-scanning the cell registry (`getElement().contains(target)`), constrains the preview to the anchor's column, and drives the grid's real `extent` so the standard selection highlight tracks the drag live. Pointer-up commits: every cell between anchor and release row (excluding the source row) receives `write(sourceValue)` if its `canWrite` accepts it.

**Cell registration / no virtualization.** There is no row/column virtualization — every cell renders unconditionally and registers itself with the grid's `cells: Map<CellKey, CellRegistration>` on mount via `useStableCellRegistration`. That hook exists specifically to prevent registration churn: it threads the handlers and `registerCell` itself through refs so the registration `useEffect`'s dependency array is only `[row, col]`, meaning a value change (e.g. typing) does not unregister/re-register the cell, avoid churning `bounds`, and avoid `setState`-during-render loops. Given the linear-scan hit-testing in the fill handle and the lack of virtualization, this primitive is documented (and here confirmed) as sized for "a few hundred cells," not spreadsheet-scale data.

**Headless verification.** Confirmed: no file under `packages/dashboard-ui/src/spree/data-grid/` imports anything from `packages/dashboard` or `packages/dashboard-core`. All state (`DataGridContext`) is created and consumed within the same directory; the only external dependencies are `@tanstack/react-table`, `@tanstack/react-hotkeys`, React itself, and this package's own `ui/` primitives (`Select`, `Switch`) and `lib/utils` (`cn`). This satisfies the dashboard-ui rule (components accept data via props, no provider/hook imports from outside the package) — no violation found.
