# Implementation Plan: Data Grid Component

**Branch**: `035-data-grid-component` | **Date**: 2026-08-25 | **Spec**: `specs/035-data-grid-component/spec.md`

**Input**: Feature specification from `/specs/035-data-grid-component/spec.md`

**Note**: This plan is reverse-engineered from already-shipped code (brownfield migration) — it documents the implementation as built, not a forward design.

## Summary

A headless, keyboard-first spreadsheet primitive for `packages/dashboard-ui`. `DataGrid<T>` wraps a TanStack `useReactTable` core-row-model table and layers Excel-style interaction on top: arrow/Tab navigation, Shift+Arrow range selection, Cmd/Ctrl+C/V/D copy/paste/fill-down, and a draggable fill handle — all driven by a local React context (`DataGridContext`) and a self-registering cell contract (`useStableCellRegistration`). Typed cell components (`NumberCell`, `MoneyCell`, `SwitchCell`, `SelectCell`, `ReadOnlyCell`) are the extension surface; `BulkPriceTable` is the shipped consumer composing the grid into a variant-price bulk editor.

## Technical Context

**Language/Version**: TypeScript (React SPA / design-system package)

**Primary Dependencies**: `@tanstack/react-table` (core row model only, no sorting/filtering/pagination plugins), `@tanstack/react-hotkeys` (`useHotkey`, scoped to a `target` ref), React context/state, this package's own `ui/select.tsx` and `ui/switch.tsx`, `lib/utils.ts` (`cn`)

**Storage**: N/A — no persistence; all values flow in via props and out via `onChange` callbacks. Backend parsing of money strings (`Spree::LocalizedNumber`) is a documented caller responsibility, not this component's concern.

**Testing**: Vitest (frontend unit, colocated `*.test.ts` under `packages/dashboard-ui`); no Playwright e2e in this package (e2e lives in `packages/dashboard` against composed consumers, e.g. a future `variants-section` bulk-price flow)

**Target Platform**: Browser, part of the `@spree/dashboard-ui` design-system package consumed by `packages/dashboard`

**Project Type**: Monorepo — single TypeScript package, `packages/dashboard-ui`

**Performance Goals**: No virtualization; documented/accepted scale is "a few hundred cells per grid" (fill-handle hit-testing is a linear scan over the cell registry) — not spreadsheet-scale datasets

**Constraints**: Must remain headless (no provider/hook imports from `packages/dashboard` or `packages/dashboard-core`); keyboard shortcuts must not fight the browser's own Tab-based focus order at the grid's edges

**Scale/Scope**: One primitive directory (`data-grid/`) + two composed consumers (`bulk-price-table.tsx`, `storefront-visible-switch.tsx`) in the same package

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches only `packages/dashboard-ui`. Verified no import from `packages/dashboard` or `packages/dashboard-core` anywhere under `src/spree/data-grid/` — the context, state, and hooks are all local to this package. Pass.
- **II. Admin API Is the Only Frontend Data Source**: N/A — this is a presentational primitive with no data fetching; callers (in `packages/dashboard`) own fetching via the Admin API and pass rows/values in as props.
- **III. Read/Write Field Symmetry**: N/A — no serializer or API surface is touched by this feature.
- **IV. Test-Backed**: Vitest unit tests for the primitive's interaction logic (navigation clamping, `findExistingCoords`, fill-down column-broadcast, `canWrite` gating per cell type) belong in `packages/dashboard-ui`, colocated with the source. No RSpec/Playwright scope for this feature.
- **V. Translations and Prefixed IDs**: N/A — the primitive renders no hardcoded user-visible copy of its own (labels/placeholders are 100% caller-supplied props, e.g. `BulkPriceTableLabels`); no resource IDs are exposed by this component.
- **VI. `docs/plans/` for Architectural Changes**: N/A — not a new model, API surface, or cross-cutting rename; no `docs/plans/` entry governs this UI primitive.

No violations — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/035-data-grid-component/
├── plan.md              # This file
└── spec.md              # Feature spec (includes Migration Notes)
```

(No `research.md`/`data-model.md`/`contracts/`/`tasks.md` phase artifacts beyond `tasks.md`, produced separately — this is a reverse-engineered brownfield entry, not a forward `/speckit-plan` run.)

### Source Code (repository root)

```text
# packages/dashboard-ui — headless design-system primitive
packages/dashboard-ui/src/spree/data-grid/
├── data-grid.tsx                    # DataGrid<T>, DataGridShell, DataGridRow, DataGridKeyboardMount
├── context.ts                       # DataGridContext, DataGridContextValue, coordsInRect, modeFor
├── types.ts                         # CellCoords, CellKey, cellKey(), GridMode, CellRegistration, RenderSectionHeader
├── cells.tsx                        # NumberCell, MoneyCell, SwitchCell, SelectCell, ReadOnlyCell
├── fill-handle.tsx                  # FillHandle — drag-to-copy over the selection's far corner
├── use-data-grid-keyboard.ts        # useDataGridKeyboard — all useHotkey bindings
├── use-stable-cell-registration.ts  # useStableCellRegistration — ref-threaded registration effect
├── helpers.ts                       # editableRowIndex — maps a row id to its editable-only coord index
└── index.ts                         # public exports (cells, useDataGridContext, DataGrid, editableRowIndex, types)

packages/dashboard-ui/src/spree/
├── bulk-price-table.tsx             # BulkPriceTable — composed consumer (variant price spreadsheet)
└── storefront-visible-switch.tsx    # StorefrontVisibleSwitch — unrelated composed form control, same package
```

**Structure Decision**: Single-module change confined to `packages/dashboard-ui`. No `packages/dashboard`, `packages/dashboard-core`, backend gem, or SDK changes — `packages/dashboard` consumes the grid only indirectly through composed components like `BulkPriceTable`.

## Complexity Tracking

*No violations — table intentionally omitted.*
