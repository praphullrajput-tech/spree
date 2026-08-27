---

description: "Task list for feature implementation"
---

# Tasks: Admin Table/Navigation Framework

**Input**: Design documents from `/specs/030-admin-table-navigation-framework/`

**Prerequisites**: plan.md, spec.md

**Note**: This module is frozen — documented for historical/migration reference only. Per the project constitution, no new features should be added here; new admin work belongs in packages/dashboard.

**Note**: This feature is reverse-engineered from already-shipped code (`/speckit.brownfield.migrate`). All tasks below are marked complete — they describe work already done in `spree/admin`, reconstructed for traceability, not a forward implementation queue.

**Tests**: Framework-level RSpec coverage already exists in `spree/admin/spec/` for the model layer; helper/controller specs are lighter (see Phase N gap note).

**Organization**: Tasks are grouped by user story, matching spec.md's four stories (P1: table registration, P1: query builder, P2: bulk operations, P2: navigation).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Could have run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)

## Path Conventions

All paths are under `spree/admin/` (the sole module touched — see spec.md's Module Impact table).

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/admin` gem builds/tests cleanly: `cd spree/admin && bundle exec rspec`
- [x] T002 [P] Register `TablesEnvironment` and `NavigationEnvironment` on `Rails.application.config.spree_admin` in `spree/admin/lib/spree/admin/engine.rb`
- [x] T003 [P] Expose `Spree.admin.tables` / `Spree.admin.navigation` accessors in `spree/admin/lib/spree/admin.rb`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core registry/model infrastructure that every user story's index/nav pages depend on.

- [x] T004 [P] Implement `Table` registry (columns, bulk actions, search/date-range config) in `spree/admin/app/models/spree/admin/table.rb`
- [x] T005 [P] Implement `Table::Column` (ActiveModel::Attributes-based: type, sortable/filterable/displayable/default flags, position, ransack_attribute, filter metadata) in `spree/admin/app/models/spree/admin/table/column.rb`
- [x] T006 [P] Implement shared `Visibility` concern (`condition`/`visible?`) used by `Column` and `BulkAction` in `spree/admin/app/models/spree/admin/table/visibility.rb`
- [x] T007 [P] Implement `Table::Builder` DSL for `table.add(:key) { ... }` blocks in `spree/admin/app/models/spree/admin/table/builder.rb`
- [x] T008 [P] Implement `Navigation` registry (items, tree building, visible_items, sections) in `spree/admin/app/models/spree/admin/navigation.rb`
- [x] T009 [P] Implement `Navigation::Item` (url/label/icon/position/parent/condition/badge/children) in `spree/admin/app/models/spree/admin/navigation/item.rb`
- [x] T010 [P] Implement `Navigation::Builder` DSL for nested `navigation.add(:key) { ... }` blocks in `spree/admin/app/models/spree/admin/navigation/builder.rb`
- [x] T011 [spree/admin] Register default navigation contexts (`:sidebar`, `:settings`, `:tax_tabs`, `:shipping_tabs`, `:team_tabs`, `:stock_tabs`, `:returns_tabs`, `:developers_tabs`, `:audit_tabs`) in `spree/admin/lib/spree/admin/engine.rb`

**Checkpoint**: Registries exist and are populated at boot — user story implementation can proceed.

---

## Phase 3: User Story 1 - Register a sortable/filterable index table (Priority: P1) 🎯 MVP

**Goal**: Controllers get sortable/filterable/paginated index tables from a table registration + `render_table` call.

**Independent Test**: Register a table with mixed column types, call `render_table` from a controller, verify default columns, sorting, and column rendering per-type all work without extra view code.

### Implementation for User Story 1

- [x] T012 [P] [US1] `TableConcern#use_table`, `#table`, `#table_registered?` in `spree/admin/app/controllers/concerns/spree/admin/table_concern.rb`
- [x] T013 [US1] `TableConcern#apply_table_sort` / `#custom_sort_active?` — custom `sort_scope_asc`/`sort_scope_desc` escape hatch (depends on T005, T012)
- [x] T014 [US1] `TableHelper#render_table` + `session_selected_columns` (persist user column selection) in `spree/admin/app/helpers/spree/admin/table_helper.rb`
- [x] T015 [US1] Per-column-type cell renderers (`render_money_column`, `render_date_column`/`render_datetime_column`, `render_status_column` with `STATUS_BADGE_CLASSES`, `render_boolean_column`, `render_link_column`, `render_image_column`, `render_string_column`, `render_association_column`, `custom` partial dispatch) in `render_column_value` (depends on T014)
- [x] T016 [US1] `table_sort_dropdown` + header/cell CSS class helpers (`column_header_class`, `column_cell_class`) (depends on T014)
- [x] T017 [US1] Row-action permission gating via `link_to_edit`/`link_to_delete` (`can?`) in `spree/admin/app/helpers/spree/admin/navigation_helper.rb`

**Checkpoint**: Index pages render sortable/filterable tables end-to-end.

---

## Phase 4: User Story 2 - Build complex filters with the visual query builder (Priority: P1)

**Goal**: AND/OR nested filter trees round-trip through `query_state` and convert correctly to Ransack params.

**Independent Test**: Build a nested AND/OR filter tree, serialize to JSON, reload, confirm structural equality; confirm `to_ransack_params` output matches Ransack's flat vs. `g`-grouping syntax per combinator.

### Implementation for User Story 2

- [x] T018 [P] [US2] `Table::Filter` (operator table incl. `no_value` operators, `to_ransack_param`, array/autocomplete value extraction) in `spree/admin/app/models/spree/admin/table/filter.rb`
- [x] T019 [P] [US2] `Table::FilterGroup` (AND/OR combinator, nested groups, `to_ransack_params`/`to_and_ransack_params`/`to_or_ransack_params`/`build_or_grouping`) in `spree/admin/app/models/spree/admin/table/filter_group.rb`
- [x] T020 [US2] `Table::QueryBuilder` (root `FilterGroup` ownership, JSON state load/dump, `available_fields`/`available_operators`) (depends on T018, T019) in `spree/admin/app/models/spree/admin/table/query_builder.rb`
- [x] T021 [US2] `TableConcern#process_table_query_state` — merge `query_state` param into ransack `params[:q]` server-side (depends on T020) in `spree/admin/app/controllers/concerns/spree/admin/table_concern.rb`
- [x] T022 [US2] `TableHelper#query_builder_fields_json` / `#query_builder_operators_json` / `#count_applied_filters` (depends on T020)
- [x] T023 [US2] Stimulus `query_builder_controller.js` — client-side filter/group add/remove, ransack param generation mirroring the Ruby model, hidden-field state serialization in `spree/admin/app/javascript/spree/admin/controllers/query_builder_controller.js`

**Checkpoint**: Visual query builder fully functional and state-persistent across navigation.

---

## Phase 5: User Story 3 - Bulk operations on selected rows (Priority: P2)

**Goal**: Tables can register bulk actions rendered via one generic bulk-operation route/modal.

**Independent Test**: Register 3+ bulk actions with a visibility condition, confirm primary/secondary split and condition-based filtering in the rendered panel.

### Implementation for User Story 3

- [x] T024 [P] [US3] `Table::BulkAction` (key/label/icon/method/confirm/modal-form attributes) in `spree/admin/app/models/spree/admin/table/bulk_action.rb`
- [x] T025 [US3] `Table#add_bulk_action`/`#remove_bulk_action`/`#update_bulk_action`/`#visible_bulk_actions`/`#bulk_operations_enabled?` (depends on T024) in `spree/admin/app/models/spree/admin/table.rb`
- [x] T026 [US3] `TableHelper#render_bulk_action`/`#render_bulk_actions_panel`/`#render_bulk_actions_dropdown` (primary/secondary split, confirm-message resolution) (depends on T025) in `spree/admin/app/helpers/spree/admin/table_helper.rb`

**Checkpoint**: Bulk actions selectable and renderable per table, gated by visibility conditions.

---

## Phase 6: User Story 4 - Register and render sidebar/tab navigation (Priority: P2)

**Goal**: Nested nav trees render with active-state detection and permission-based visibility across contexts.

**Independent Test**: Register a parent/child nav pair, visit a child URL, confirm parent+child both report active and only permitted children render.

### Implementation for User Story 4

- [x] T027 [P] [US4] `Navigation#build_tree`/`#root_items`/`#visible_items`/`#registered_paths` (depends on T008, T009)
- [x] T028 [P] [US4] `Navigation#insert_before`/`#insert_after`/`#move`/`#replace`/`#section` positioning API (depends on T008)
- [x] T029 [US4] `Item#resolve_url` (Symbol route-helper / Proc / String resolution), `#resolve_label` (i18n), `#active?` (path + custom `active_condition` + child bubbling) (depends on T009)
- [x] T030 [US4] `Item#visible?`/`#badge_value` — `instance_exec` against view context so `can?` and route helpers are available inside conditions (depends on T009)
- [x] T031 [US4] `NavigationHelper#render_navigation`/`#render_navigation_items`/`#render_navigation_item`/`#render_nav_item_with_children`/`#render_nav_section_header` (expanded submenu + collapsed dropdown variants) (depends on T027, T029, T030) in `spree/admin/app/helpers/spree/admin/navigation_helper.rb`
- [x] T032 [US4] `NavigationHelper#render_tab_navigation` for tab-style contexts (`:tax_tabs`, etc.) (depends on T031)

**Checkpoint**: All four user stories independently functional — this matches the framework as shipped.

---

## Phase N: Polish & Cross-Cutting Concerns

- [x] TXXX Misc admin UI helpers shipped alongside navigation (`per_page_dropdown`, `link_to_with_icon`, `active_badge`, `page_header_back_button`, `external_link_to`, `help_bubble`, `link_to_export_modal`) in `spree/admin/app/helpers/spree/admin/navigation_helper.rb`
- [x] TXXX Full backend suite passes: `cd spree/admin && bundle exec rspec`
- [ ] TXXX **Gap identified**: no dedicated RSpec coverage found for `query_builder_controller.js` (Stimulus) during this migration pass — flagged in spec.md Edge Cases / plan.md Constitution Check (Principle IV) as a documentation gap, not a blocking issue for this frozen module.
- [ ] TXXX **Gap identified**: `Table::Column#type` is not validated against the `TYPES` constant at the model layer (only `key` presence is validated) — an unrecognized type silently falls back to `render_string_column` at render time rather than failing fast at registration time. Documented as a known quirk, not remediated (module is frozen).

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: registries must exist before any story's classes can be registered.
- **User Story 1 (Phase 3)** and **User Story 4 (Phase 6)** have no dependency on each other — table rendering and navigation rendering are independent subsystems sharing only the `Visibility`-style condition pattern (convention, not shared code).
- **User Story 2 (Phase 4)** depends on Foundational's `Table`/`Column` (for `filterable_columns`/`available_fields`) but not on User Story 1's rendering helpers.
- **User Story 3 (Phase 5)** depends on Foundational's `Table` registry (`add_bulk_action` lives on `Table`) but is otherwise independent of Stories 1, 2, 4.

## Notes

- All tasks are marked `[x]` because this is a reverse-engineered spec for already-shipped, frozen code — there is no remaining implementation work, only the two documentation gaps noted in Phase N.
- Any future change to this module should go through an extension or a `packages/dashboard` reimplementation instead, per the Migration Notes in spec.md.
