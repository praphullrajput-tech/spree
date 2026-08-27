# Implementation Plan: Admin Table/Navigation Framework

**Branch**: `030-admin-table-navigation-framework` | **Date**: 2026-08-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/030-admin-table-navigation-framework/spec.md`

**Note**: This module is frozen — documented for historical/migration reference only. Per the project constitution, no new features should be added here; new admin work belongs in packages/dashboard.

**Note**: This plan is reverse-engineered from already-shipped code (`/speckit.brownfield.migrate`). There is no forward implementation work; it documents the plan a from-scratch build would have followed, mapped onto the actual file layout.

## Summary

`spree/admin` ships a self-contained, config-driven framework for two recurring legacy-admin needs: (1) sortable/filterable/paginated index tables with a visual AND/OR query builder and generic bulk operations, and (2) a nested, permission-aware sidebar/tab navigation tree. Both are Ruby object registries (`Spree::Admin::Table`, `Spree::Admin::Navigation`) held in `Rails.application.config.spree_admin`, populated at boot via `Spree.admin.tables.register` / `Spree.admin.navigation.register_context`, and rendered through view helpers (`TableHelper`, `NavigationHelper`) plus one Stimulus controller (`query_builder_controller.js`) for the client-side filter-tree UI. No new API endpoints, models, or migrations — purely server-rendered ERB + Ransack.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/admin`) + Stimulus/JavaScript for the query-builder widget only.

**Primary Dependencies**: Ransack (filter param translation), Pagy (pagination, consumed by the same index pages, not by this framework directly), CanCanCan (`can?` inside navigation/row-action visibility conditions), ActiveModel::Model + ActiveModel::Attributes (`Table::Column`, `Table::BulkAction`), Stimulus.js (`query_builder_controller.js`), `active_link_to` gem (nav active-state rendering).

**Storage**: None owned by this framework — it operates purely on in-memory Ruby objects (registries) and the ActiveRecord collections passed in by each controller; no migrations.

**Testing**: RSpec (model/helper/controller specs under `spree/admin/spec/`) — no Vitest/Playwright involvement since this ships no TypeScript.

**Target Platform**: Rails engine (`spree/admin`), server-rendered Turbo/Stimulus admin, not consumed by the React SPA.

**Project Type**: Single Ruby gem (`spree/admin`) — no cross-package frontend work.

**Performance Goals**: N/A — inherited from the standard Rails/Ransack/Pagy request cycle; no framework-specific perf target beyond "registry lookups are O(1) hash access, not re-computed per request beyond what Rails config caching already provides."

**Constraints**: Must not introduce a hard dependency from `spree/core` or `spree/api` on this framework (it is `spree/admin`-only); must degrade gracefully (no-ops, not exceptions) when a table/nav key isn't found for common accessor paths used by the concern (`table` returns `nil`), while registry lookups (`tables.get`, `navigation.get_context`) raise `NoMethodError` with a descriptive message when a *context/table itself* was never registered at all.

**Scale/Scope**: Every legacy admin index page (~dozens of resources: products, orders, promotions, customers, etc.) and the full sidebar/settings/tab navigation tree.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches only `spree/admin`. It does not reach into `spree/core` models directly except through normal ActiveRecord collections/scopes handed to it by controllers, and it exposes no cross-module extension point of its own beyond the `Spree.admin.tables` / `Spree.admin.navigation` registries, which are themselves internal to `spree/admin`. PASS — no boundary crossing.
- **II. Admin API Is the Only Frontend Data Source**: N/A — this is server-rendered legacy admin, not `packages/dashboard`; it does not go through the Admin API at all (it queries ActiveRecord directly, which is the pre-6.0 legacy pattern this framework predates the API-only rule for).
- **III. Read/Write Field Symmetry**: N/A — no Alba serializers or API controllers involved.
- **IV. Test-Backed**: Covered by RSpec specs in `spree/admin/spec/models/spree/admin/` (table/navigation/filter/query_builder) and `spree/admin/spec/helpers/spree/admin/` (table_helper/navigation_helper); no Vitest/Playwright since no TypeScript beyond the one Stimulus controller (not currently unit-tested per the source files reviewed — flagged as a gap, see Migration Notes in spec.md).
- **V. Translations and Prefixed IDs**: Labels/status/confirm text go through `Spree.t`/`I18n.t` (see `Column#resolve_label` pattern via `Navigation::Item#resolve_label`, `Table::Filter.translate_operator`, `resolve_bulk_action_confirm`) — consistent with the legacy admin's `Spree.t` convention (not i18next, which is `packages/dashboard`-only). No prefixed IDs are exposed by this framework since it emits no API responses.
- **VI. `docs/plans/` for Architectural Changes**: N/A — no new architectural change proposed; this is a historical spec for existing, frozen code. Per Module Impact table in spec.md, no `docs/plans/` entry is warranted.

No violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/030-admin-table-navigation-framework/
├── spec.md               # Feature specification (this feature's /speckit-specify output)
├── plan.md                # This file
└── tasks.md               # Task breakdown (all marked complete — code already shipped)
```

### Source Code (repository root)

```text
# spree/admin — legacy Rails admin (frozen; sole module touched by this feature)
spree/admin/
├── app/models/spree/admin/table.rb                          # Table registry: columns, bulk actions, index-page config
├── app/models/spree/admin/table/column.rb                   # Column definition (type, sort/filter flags, ransack attribute)
├── app/models/spree/admin/table/bulk_action.rb               # Bulk action definition (label, icon, method, confirm, modal form)
├── app/models/spree/admin/table/filter.rb                    # Single filter condition -> ransack param
├── app/models/spree/admin/table/filter_group.rb              # AND/OR filter tree node -> ransack params (incl. `g` grouping)
├── app/models/spree/admin/table/query_builder.rb              # Owns root FilterGroup; JSON state <-> ransack params; available_fields
├── app/models/spree/admin/table/builder.rb                    # DSL builder used inside `table.add(:key) { ... }` blocks
├── app/models/spree/admin/table/visibility.rb                 # Shared `condition`/`visible?` concern for Column + BulkAction
├── app/models/spree/admin/navigation.rb                       # Navigation registry: items, tree building, visible_items
├── app/models/spree/admin/navigation/item.rb                  # Single nav item (url/label/icon/position/parent/condition/children)
├── app/models/spree/admin/navigation/builder.rb                # DSL builder used inside `navigation.add(:key) { ... }` blocks
├── app/controllers/concerns/spree/admin/table_concern.rb       # `use_table`, `table`, `apply_table_sort`, `process_table_query_state`
├── app/helpers/spree/admin/table_helper.rb                     # `render_table`, per-column-type cell renderers, sort dropdown, bulk-action rendering
├── app/helpers/spree/admin/navigation_helper.rb                 # `render_navigation`, nav item/section/submenu rendering, misc admin UI helpers
├── app/javascript/spree/admin/controllers/query_builder_controller.js  # Stimulus controller: client-side filter-tree UI, serializes to query_state
└── lib/spree/admin/engine.rb                                    # `TablesEnvironment`/`NavigationEnvironment`, `Spree.admin.tables`/`Spree.admin.navigation` accessors, default nav contexts registered on boot
```

**Structure Decision**: Single-module plan — everything lives in `spree/admin` per the Module Impact table in spec.md. No `spree/core`, `spree/api`, or `packages/*` changes; this is a self-contained legacy-admin rendering framework with no cross-module extension surface beyond its own two registries.

## Complexity Tracking

*No violations — table intentionally left empty.*
