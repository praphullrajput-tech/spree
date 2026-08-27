# Feature Specification: Admin Table/Navigation Framework

**Feature Branch**: `030-admin-table-navigation-framework`

**Created**: 2026-08-24

**Status**: migrated

**Note**: This module is frozen — documented for historical/migration reference only. Per the project constitution, no new features should be added here; new admin work belongs in packages/dashboard.

**Input**: Reverse-engineered from existing code in `spree/admin` as part of `/speckit.brownfield.migrate`. No original user-facing feature request exists; this spec documents the internal framework as built.

## User Scenarios & Testing *(mandatory)*

This is an internal developer-facing framework, not an end-user feature. "Users" below are Spree core/extension developers who register tables and navigation items for the legacy Rails admin; the people who ultimately interact with the rendered UI are admin staff.

### User Story 1 - Register a sortable/filterable index table (Priority: P1)

A core or extension developer registers a `Spree::Admin::Table` for a resource (e.g. `:products`), declares columns with types (`string`, `money`, `status`, `date`, `link`, `image`, `association`, `custom`, etc.), and gets a fully working index page: sortable headers, per-column filter definitions surfaced to a visual query builder, a search box, optional date-range filter, and row actions (edit/delete) — with zero controller/view boilerplate beyond `include Spree::Admin::TableConcern` and `render_table`.

**Why this priority**: Every legacy admin index page (products, orders, promotions, etc.) depends on this to render consistently; it's the foundation the other stories build on.

**Independent Test**: Register a table with a handful of columns of different types in an initializer, hit the controller's index action with `render_table(collection, :key)`, and verify sortable headers, column values, and search/filter UI render without additional per-controller code.

**Acceptance Scenarios**:

1. **Given** a table registered via `Spree.admin.tables.register(:products, model_class: Spree::Product)` with columns added via `table.add(:name, sortable: true, filterable: true, default: true)`, **When** the products index renders via `render_table(@products, :products)`, **Then** the `name` column appears by default, is sortable, and is available as a query-builder filter field.
2. **Given** a column configured with `sort_scope_asc`/`sort_scope_desc` (custom sort scope) instead of a plain ransack attribute, **When** the controller calls `apply_table_sort(collection)` after the ransack search, **Then** the collection is reordered using the named model scope instead of a SQL `ORDER BY` on the ransack attribute.
3. **Given** a column with `type: :money`, **When** the value is a `Spree::Money` or numeric amount, **Then** it renders via `display_amount`/`Spree::Money#to_html` in the current store currency.
4. **Given** `row_actions_delete: true` and the current user lacks `destroy` permission (CanCanCan), **When** the row renders, **Then** the delete action is not shown (permission-gated via `link_to_delete`/`can?`).

---

### User Story 2 - Build complex filters with the visual query builder (Priority: P1)

An admin staff user builds a filter query with AND/OR groups and nested conditions (e.g. "status = complete AND (total > 100 OR customer_name contains 'Smith')") through a Stimulus-driven UI, without writing ransack params by hand. The state round-trips through a `query_state` JSON param on navigation/pagination.

**Why this priority**: This is the most complex, most reused piece of the framework — every filterable table with more than trivial search needs it, and it's the main place a bug would silently corrupt search results.

**Independent Test**: Load an index page with the query builder open, add a filter, add an "OR" group with two nested filters, submit, and confirm the resulting `q[...]` ransack params (or `g` groupings) match the expected AND/OR semantics; reload with the same `query_state` param and confirm the UI reconstructs the same filter tree.

**Acceptance Scenarios**:

1. **Given** a root group with two plain filters (`combinator: :and`), **When** `to_ransack_params` is called, **Then** the result is a flat hash like `{ name_cont: 'foo', status_eq: 'active' }`.
2. **Given** a root group with `combinator: :or` containing two filters, **When** `to_ransack_params` is called, **Then** the result uses ransack's `g` (grouping) syntax: `{ g: { '0' => { m: 'or', c: { ... } } } }`.
3. **Given** a serialized `query_state` JSON string from a previous request, **When** `QueryBuilder#load_from_json` parses it, **Then** the resulting `FilterGroup` tree (including nested groups) matches the original structure, and malformed JSON degrades to an empty root group rather than raising.
4. **Given** a filter operator of `null`/`not_null` (`no_value: true`), **When** the filter is submitted without a value, **Then** the generated ransack param is `{ "field_null" => true }` and the UI does not require a value input.
5. **Given** a filter value that is an array of `{id:, ...}` hashes (from an autocomplete/resource picker), **When** converted to a ransack param, **Then** the IDs are extracted; for `eq`/`not_eq` with a single selected value, the array collapses to a scalar.

---

### User Story 3 - Bulk operations on selected rows (Priority: P2)

An admin staff user selects one or more rows in a table and applies a registered bulk action (e.g. bulk delete, bulk status change), which opens a confirmation modal driven by a generic `bulk_operation` route rather than one-off per-resource controllers.

**Why this priority**: Valuable but the table renders and functions without it (bulk actions are opt-in per table); lower priority than the base table/filter mechanics.

**Independent Test**: Register a bulk action with `add_bulk_action`, verify it appears in the bulk-actions panel only when the table has selected rows and the action is visible for the current user, and that invoking it opens the shared bulk-operation modal scoped to the correct `table_key`/action `key`.

**Acceptance Scenarios**:

1. **Given** a table with 3 registered bulk actions, **When** the panel renders, **Then** the first 2 render as primary buttons and the remaining ones collapse into a dropdown.
2. **Given** a bulk action with a `condition`/`if` that evaluates false for the current view context, **When** `visible_bulk_actions(view_context)` is called, **Then** that action is excluded.
3. **Given** a bulk action with `confirm: 'admin.confirm_delete'` (an i18n key), **When** rendered, **Then** the link's `data-confirm` attribute shows the translated string, not the raw key.

---

### User Story 4 - Register and render sidebar/tab navigation (Priority: P2)

A core or extension developer registers navigation items (with optional nesting, sections, badges, icons, conditions) for a given context (`:sidebar`, `:settings`, `:tax_tabs`, etc.), and the framework renders the tree with active-state detection, permission-based visibility, and collapsed/expanded submenu variants — without hand-writing each `<li>` in a shared partial.

**Why this priority**: Structural navigation is needed for every admin section, but is simpler and lower-risk than the table/filter machinery (P1 stories); still core to "does the legacy admin function at all."

**Independent Test**: Register a top-level item with two children in the `:sidebar` context, visit a URL matching one child, and confirm the parent is marked active, the submenu is expanded, and only children whose `condition` passes for the current user render.

**Acceptance Scenarios**:

1. **Given** an item added with `parent: :settings`, **When** `build_tree` runs, **Then** the item appears in `Spree.admin.navigation.get_context(:settings).find(:settings).children`, not as a root item.
2. **Given** an item's `url:` is a Symbol (route helper name), **When** `resolve_url(context)` is called with a view context, **Then** it calls that route helper on the context (falling back to `context.spree.<helper>` or the raw string).
3. **Given** the current request path matches the resolved URL of a child item, **When** `active?` is evaluated on the parent, **Then** the parent is also considered active (so the submenu expands).
4. **Given** an item with `condition: ->{ can?(:manage, Spree::Promotion) }`, **When** `visible?(view_context)` is evaluated via `instance_exec`, **Then** CanCanCan's `can?` helper is available inside the block.
5. **Given** `section(:catalog, label: 'Catalog')`, **When** rendered, **Then** it appears as a non-clickable section header (`section?` true) rather than a link.

---

### Edge Cases

- What happens when a controller calls `apply_table_sort` but no table is registered for that controller (`table` returns `nil`)? → Returns the collection unmodified (`return collection unless table`).
- How does the system handle a `query_state` param that references a `field` not present in `filterable_columns`? → The filter is still converted to a ransack param (`Filter` doesn't validate `field` against the table); an invalid ransack attribute would be rejected by Ransack itself downstream, not by this framework.
- How does the system handle two navigation items registered with the same `key`? → The second `add` overwrites the first in `@items` (Hash keyed by symbol).
- How does the system handle a `Table::Column` whose `type` isn't in `TYPES`? → Falls through to `render_string_column` in `render_column_value`'s `case`/`else` (no hard validation preventing unknown types at the render layer, though `Column` has `validates :key, presence: true` at the model layer — type isn't validated against `TYPES`/`FILTER_TYPES` in the excerpted code).
- What happens when `move`/`insert_before`/`insert_after` targets a key that doesn't exist? → Returns `nil`, no-op.
- How are deeply nested `FilterGroup`s (group inside a group inside a group) serialized to ransack? → Only one level of `g` nesting is built by `build_or_grouping`/`to_and_ransack_params`; nested `:and` groups merge flat into the parent's hash, nested `:or` groups become entries under `g`, but a group-of-groups-of-groups is not explicitly modeled beyond what `FilterGroup#groups` recursion produces — verify against `query_builder_controller.js` for the client-side depth limit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The framework MUST allow registering a per-resource `Table` (columns, bulk actions, search/date-range config) keyed by symbol via `Spree.admin.tables.register`, retrievable via `Spree.admin.tables.get`.
- **FR-002**: Each `Table::Column` MUST support: display type (`string`, `number`, `money`, `date`, `datetime`, `status`, `boolean`, `link`, `image`, `association`, `custom`), independent sortable/filterable/displayable/default flags, position-based ordering, and an optional `condition` gating visibility.
- **FR-003**: The framework MUST support per-column filter metadata (`filter_type`, `operators`, `value_options`, `search_url`, `preload_options`) consumed by a client-side query builder to render the correct input widget per field.
- **FR-004**: The framework MUST convert a tree of `Filter`/`FilterGroup` objects to Ransack-compatible params, correctly distinguishing flat AND semantics from Ransack's `g` grouping syntax for OR semantics.
- **FR-005**: The framework MUST serialize/deserialize the full filter tree to/from a single JSON string (`query_state`) so filter state survives pagination, sorting, and page reloads without needing to re-express every ransack param in the URL.
- **FR-006**: The framework MUST support a custom-sort escape hatch (`sort_scope_asc`/`sort_scope_desc`) for columns whose sort semantics can't be expressed as a plain ransack attribute, applied by the controller via `apply_table_sort`/`apply_custom_sort`.
- **FR-007**: The framework MUST support registering bulk actions per table (label, icon, HTTP method, confirm message, condition, optional inline modal form) rendered via a single generic bulk-operation route rather than per-resource controllers.
- **FR-008**: The framework MUST allow registering a tree of navigation items per named context (`:sidebar`, `:settings`, and other ad-hoc tab contexts), supporting nesting via `parent:`, ordering via `position`/`insert_before`/`insert_after`/`move`, section headers, badges, tooltips, and visibility/active-state conditions evaluated against the current view context (so CanCanCan `can?` and route helpers are available).
- **FR-009**: Navigation item URLs MUST be resolvable from a Symbol (route helper), a Proc (evaluated via `instance_exec` against the view context), or a plain string.
- **FR-010**: The framework MUST let a controller opt into a specific registered table via `use_table` or fall back to the table matching its `controller_name`.

### Key Entities

- **Table**: Per-resource registry of columns and bulk actions plus index-page config (search param/placeholder, row actions, date-range filter, link-to-action). Identified by a symbol key (e.g. `:products`).
- **Table::Column**: A single column definition — display type, sort/filter/visibility flags, position, ransack attribute, filter operators/value options, optional custom partial for `type: :custom`.
- **Table::BulkAction**: A bulk operation definable per table — key, label, icon, HTTP method, confirm text, optional modal form partial, visibility condition.
- **Table::Filter**: A single filter condition (`field`, `operator`, `value`) that converts to one Ransack param.
- **Table::FilterGroup**: A node in the filter tree — a combinator (`:and`/`:or`) plus child filters and nested groups; the root of a `QueryBuilder`.
- **Table::QueryBuilder**: Owns the root `FilterGroup` for a given `Table`; converts to/from Ransack params and JSON state; exposes `available_fields`/`available_operators` for the client-side widget.
- **Navigation**: Per-context (`:sidebar`, `:settings`, etc.) registry of `Navigation::Item`s; builds/maintains the parent-child tree, computes visible/root items.
- **Navigation::Item**: A single nav entry — key, label, url (Symbol/Proc/String), icon, position, parent key, visibility/active conditions, badge, children.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/admin` (legacy Rails admin — frozen) | Yes | Entire framework lives here: `app/models/spree/admin/table.rb` + `table/{column,filter,filter_group,query_builder,bulk_action,builder,visibility}.rb`, `app/models/spree/admin/navigation.rb` + `navigation/{item,builder}.rb`, `app/controllers/concerns/spree/admin/table_concern.rb`, `app/helpers/spree/admin/{table_helper,navigation_helper}.rb`, `app/javascript/spree/admin/controllers/query_builder_controller.js`, `lib/spree/admin/engine.rb` (`TablesEnvironment`/`NavigationEnvironment` registration) |
| `spree/core` (models, services) | No | Consumed only via `Spree.admin.tables`/`Spree.admin.navigation` from within `spree/admin`; no core model changes |
| `spree/api` (Store/Admin API v3) | No | Not an API-facing feature |
| `packages/dashboard` (admin SPA) | No | Not implemented here; see Migration Notes |
| `packages/dashboard-ui` / `dashboard-core` | No | `dashboard-core`'s `src/lib/table-registry.ts` is a separate, forward-looking implementation for the SPA — not touched by this legacy feature |
| `packages/sdk` / `packages/admin-sdk` | No | N/A |
| `docs/plans/` | No | This is a reverse-engineered spec for an already-shipped, frozen module — no new architectural change is proposed |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new admin index page can be stood up (table registration + `render_table` call) without writing bespoke sort/filter/search view logic per resource.
- **SC-002**: Filter state expressed through the visual query builder (including nested AND/OR groups) round-trips through `query_state` without loss across pagination and sort changes.
- **SC-003**: Adding a new bulk action to an existing table requires only an `add_bulk_action` call, no new controller/route.
- **SC-004**: Adding a new sidebar/settings nav entry requires only a `Navigation#add` call, no hand-edited partial.

## Assumptions

- This framework is used exclusively by `spree/admin` (Turbo/Stimulus, server-rendered ERB); it has no client-side JS framework beyond Stimulus controllers and is not consumed by `packages/dashboard`.
- The visual query builder's client-side depth/nesting limits are governed by `query_builder_controller.js` and were not exhaustively re-derived here; treat that file as the source of truth for UI-level constraints not visible from the Ruby models alone.
- Because this module is frozen, no further functional requirements are anticipated; this spec exists purely for historical/migration reference per the brownfield migration process.

## Migration Notes

This is a **frozen legacy module**. Per the project constitution (Module Boundaries Are Load-Bearing) and `CLAUDE.md`, `spree/admin` is "being phased out — do not add new features here." No new tables, bulk actions, filters, or navigation items should be added to this framework going forward; new admin surfaces belong in `packages/dashboard` (the React SPA), consuming data exclusively through the Admin API (Constitution Principle II).

The rough forward-looking equivalent is `packages/dashboard-core/src/lib/table-registry.ts`, which defines an analogous but independent `ColumnDef` concept for the SPA (`key`, `label`, `sortable`, `filterable`, `default`, `ransackAttribute`, `render`, resource-backed filter configs via `ResourceFilterConfig`). It is a separate implementation, not a shared library with `spree/admin` — there is no code reuse between the two; the SPA's table/nav/slot registries (see `docs/plans/6.0-admin-spa.md`) are the intended replacement path as pages migrate off the legacy admin.
