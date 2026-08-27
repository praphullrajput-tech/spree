# Implementation Plan: Bulk Editing UI

**Branch**: `034-bulk-editing-ui` | **Date**: 2026-08-24 | **Spec**: `specs/034-bulk-editing-ui/spec.md`

**Input**: Feature specification from `specs/034-bulk-editing-ui/spec.md`

**Note**: This plan is reverse-engineered from an already-shipped
implementation (brownfield migration), not written ahead of implementation.
It documents the actual architecture as built.

## Summary

A generic, declarative bulk-action mechanism for `<ResourceTable>`
(`packages/dashboard-core/src/components/bulk-action-bar.tsx`) lets any
table consumer attach immediate/confirm/form-gated bulk actions without
touching the table or bar internals. On the backend, a shared pair of
concerns — `Spree::Admin::BulkOperationsConcern` (legacy Rails admin) and
`Spree::Api::V3::BulkOperations` (Admin API v3) — provide `bulk_add_tags` /
`bulk_remove_tags`, backed by `Spree::Tags::BulkAdd` / `BulkRemove` service
objects operating on an ability-scoped `bulk_collection`. Bulk price editing
is a related but separate, non-`BulkActionBar` spreadsheet UI
(`BulkPriceEditor`, `ProductBulkPriceEditor`) covered by
`specs/011-pricing-and-price-lists`.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines) for the bulk_operations
concerns and tag services; TypeScript (React SPA) for `BulkActionBar` and
its `<ResourceTable>` integration.

**Primary Dependencies**: Backend: CanCanCan (`authorize!`,
`accessible_by`), `Spree::PrefixedId` (ID decoding), `ActsAsTaggableOn`.
Frontend: TanStack Query (`useQueryClient().invalidateQueries`), Sonner
(`toast`), CanCanCan-mirrored `usePermissions()`, `react-dom` `createPortal`,
`ResizeObserver`.

**Storage**: PostgreSQL/SQLite via ActiveRecord — no new tables; operates on
existing `taggings` (ActsAsTaggableOn) and target resource tables.

**Testing**: RSpec for `Spree::Tags::BulkAdd`/`BulkRemove` (none found —
gap, see spec.md Migration Notes); Playwright
`packages/dashboard/e2e/products-bulk.spec.ts` for the frontend mechanism.

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`) consumed
by a Spree host app; React SPA (`packages/dashboard`) served standalone.

**Project Type**: Monorepo — `spree/core`, `spree/api`,
`packages/dashboard`, `packages/dashboard-core`.

**Performance Goals**: Bulk tag mutation is a single `insert_all` /
`delete_all` plus one `touch_all` — O(1) queries regardless of selection
size (no per-record N+1). No documented upper bound on selection size (see
spec.md Migration Notes — "Scale limits undocumented").

**Constraints**: `require_ids!` (API) hard-rejects a request missing the
`ids` key with `422` before any DB write; `bulk_collection` is
ability-scoped so an admin can never mutate records outside their
CanCanCan/store scope, even if they craft the request manually.

**Scale/Scope**: Two frontend consumers today (`products/index.tsx`,
`customers/index.tsx`); two backend concerns (legacy admin, API v3) shared
across Products and Customers controllers.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (tag services),
  `spree/api` (bulk_operations concern + controllers), `packages/dashboard`
  (route wiring), `packages/dashboard-core` (the generic bar +
  `resource-table.tsx`). Frontend consumes only through the Admin API
  (`adminClient`/hooks) and the `bulkActions` prop extension point — no
  boundary violations found.
- **II. Admin API Is the Only Frontend Data Source**: Pass. `BulkActionBar`
  actions call `run: (ctx) => mutation.mutateAsync(...)` against Admin API
  endpoints exclusively (no legacy Rails admin calls from the SPA).
- **III. Read/Write Field Symmetry**: N/A for `bulk_add_tags`/
  `bulk_remove_tags` (no serializer — plain `{ tags: [...] }` body, plain
  count response). Applies to `bulk_upsert` on Prices, which is scoped to
  `specs/011-pricing-and-price-lists`.
- **IV. Test-Backed**: Playwright e2e exists
  (`products-bulk.spec.ts`); RSpec coverage for `Spree::Tags::BulkAdd`/
  `BulkRemove` and the two concerns was not found — flagged as a gap in
  spec.md, not silently assumed adequate.
- **V. Translations and Prefixed IDs**: Pass. `BulkActionBar` labels/toasts
  all route through `useTranslation()`/`t(...)`; `bulk_collection` and
  `decode_ids` accept and normalize prefixed IDs (`prod_...`) before
  querying, per `Spree::PrefixedId`.
- **VI. `docs/plans/` for Architectural Changes**: No governing
  `docs/plans/` entry exists for "bulk editing" as a cross-cutting concern
  (confirmed against the `CLAUDE.md` plan list). Because this spec
  documents already-shipped, non-architectural-in-the-forward-looking-sense
  work, no new plan entry is being created as part of this migration; a
  future redesign (e.g. async bulk ops) would need one.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/034-bulk-editing-ui/
├── plan.md              # This file
├── spec.md              # Feature specification (migrated)
└── tasks.md             # Task checklist (migrated, all complete)
```

### Source Code (repository root)

```text
# spree/core — tag bulk-mutation services
spree/core/
└── app/services/spree/tags/
    ├── bulk_add.rb
    └── bulk_remove.rb

# spree/api — Admin API v3 shared bulk-operations concern + consumers
spree/api/
├── app/controllers/concerns/spree/api/v3/bulk_operations.rb
├── app/controllers/spree/api/v3/admin/products_controller.rb        # bulk_add_tags/bulk_remove_tags + product-specific bulk actions
├── app/controllers/spree/api/v3/admin/customers_controller.rb       # bulk_add_tags/bulk_remove_tags + customer-specific bulk actions
├── app/controllers/spree/api/v3/admin/prices_controller.rb          # bulk_upsert / bulk_destroy (separate mechanism, see 011)
└── config/routes.rb                                                  # collection bulk_* routes for products/customers/prices

# legacy Rails admin — being phased out, documented as-is
spree/admin/
├── app/controllers/concerns/spree/admin/bulk_operations_concern.rb
├── app/controllers/spree/admin/price_list_products_controller.rb
└── app/javascript/spree/admin/controllers/bulk_editor_controller.js

# packages/dashboard-core — the generic BulkActionBar mechanism
packages/dashboard-core/src/components/
├── bulk-action-bar.tsx      # BulkAction type, BulkActionBar, BulkActionBarLayout
└── resource-table.tsx       # selectedIds state, selectionEnabled, renders <BulkActionBar>

# packages/dashboard — bulk action wiring per resource + bulk price editors
packages/dashboard/src/
├── routes/_authenticated/$storeId/products/index.tsx    # bulkActions: set-status, add/remove categories, tags, channels
├── routes/_authenticated/$storeId/customers/index.tsx   # bulkActions: groups, tags
├── components/spree/bulk-price-editor/
│   ├── bulk-price-editor.tsx           # server-backed grid (price lists / base prices)
│   ├── bulk-price-editor-dialog.tsx    # modal wrapper for the price-list case
│   ├── product-bulk-price-editor.tsx   # form-state-backed grid (one product's variants)
│   ├── currency-parts.ts, normalize-money.ts
└── e2e/products-bulk.spec.ts
```

**Structure Decision**: Cross-cutting across `spree/core` (service objects),
`spree/api` (shared concern + per-resource controllers), and
`packages/dashboard`/`packages/dashboard-core` (generic bar + table
integration + per-route wiring). The legacy `spree/admin` concern is
documented for completeness (it predates the SPA and is not to be extended)
per `docs/plans/6.0-admin-spa.md`.

## Complexity Tracking

No constitution violations identified; table not populated.
