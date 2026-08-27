# Feature Specification: Admin Resource/Settings Controllers

**Feature Branch**: `031-admin-resource-settings-controllers`

**Created**: 2026-08-25

**Status**: migrated

**Note**: This module is frozen — documented for historical/migration reference only. Per the project constitution, no new features should be added here; new admin work belongs in `packages/dashboard`.

**Input**: Reverse-engineered from existing code (brownfield migration) — no original feature request survives; behavior below is inferred from `spree/admin/app/controllers/spree/admin/resource_controller.rb`, `spree/admin/app/controllers/concerns/spree/admin/settings_concern.rb`, `spree/admin/app/models/spree/admin/form_builder.rb`, and `spree/admin/lib/spree/admin/{callbacks,action_callbacks}.rb`.

## User Scenarios & Testing *(mandatory)*

<!--
  Internal framework/extension-point feature, not a user-facing one.
  "User" here means a Spree core/extension developer adding a new legacy
  Rails admin controller (`spree/admin/`), not an end user of the admin UI.
-->

### User Story 1 - Add a new admin resource controller with full CRUD (Priority: P1)

A developer adds a new admin-manageable model to the legacy Rails admin (e.g. `Spree::Admin::RefundReasonsController`). They subclass `Spree::Admin::ResourceController`, and get `index`/`new`/`edit`/`create`/`update`/`destroy` for free — pagination (Pagy), Ransack search, CanCanCan authorization, prefixed-ID (or FriendlyId slug) lookup, per-store scoping (`for_store`), and turbo-stream-or-HTML response handling — without writing action bodies. The only mandatory override is `permitted_resource_params` (`ResourceController` raises `NotImplementedError` otherwise).

**Why this priority**: This is the base every concrete legacy admin controller inherits from — dozens of admin resources (tax categories, refund reasons, webhook endpoints, metafield definitions, stores, policies, etc.) depend on this working correctly.

**Independent Test**: Subclass `Spree::Admin::ResourceController`, override `permitted_resource_params`, wire a standard `resources :foos` route under `/admin`, and confirm all CRUD actions work against a fresh model with no other controller code.

**Acceptance Scenarios**:

1. **Given** a new controller with only `permitted_resource_params` overridden, **When** an authorized admin visits `GET /admin/foos`, **Then** the response returns a paginated (Pagy `:countish`), Ransack-searchable collection, restricted to records `accessible_by(current_ability, :index)` and scoped to the current store via `for_store` when the model supports it.
2. **Given** the same controller, **When** an admin submits `POST /admin/foos` with invalid attributes, **Then** the response re-renders `:new` with `422 Unprocessable Content` and the object's validation errors, without any custom `create` action code.
3. **Given** the same controller, **When** an admin submits `PUT /admin/foos/:id` with valid attributes, **Then** the object updates, `created_by`/`currency`/`cost_currency` are set where applicable, a success flash is set, and the browser redirects (`303 See Other`) to `location_after_save`.
4. **Given** a model exposing `_prefix_id_prefix`, **When** a member action is requested by prefixed ID, **Then** `find_resource` resolves it via `find_by_prefix_id!`; if the model uses FriendlyId instead, resolution falls back to `.friendly.find`.

---

### User Story 2 - Nest a resource controller under a parent (Priority: P2)

A developer declares `belongs_to :product` (class-level DSL) on a `ResourceController` subclass so the resource is always scoped to a parent record (e.g. variants under a product). All URL helpers (`new_object_url`, `edit_object_url`, `object_url`, `collection_url`) and the `collection`/`scope`/`find_resource` methods automatically route through the parent.

**Why this priority**: Nested admin resources (variants, product properties, etc.) are common enough that the parent-scoping DSL needs to be a first-class, low-effort override — but it's a secondary concern to plain top-level CRUD.

**Independent Test**: Declare `belongs_to :product` on a subclass, hit its nested routes, and confirm the collection/member scope is derived from `parent.send(controller_name)` rather than the bare model class.

**Acceptance Scenarios**:

1. **Given** `belongs_to :product` is declared, **When** `GET /admin/products/:product_id/foos` is requested, **Then** the parent is resolved by prefix ID (or `find_by`) and the collection scope is `parent.foos`.
2. **Given** the same declaration, **When** building URL helpers, **Then** they generate nested polymorphic routes (`admin_product_foo_url`, etc.) instead of top-level ones.

---

### User Story 3 - Build a settings-area page (Priority: P2)

A developer includes `Spree::Admin::SettingsConcern` in a controller (typically a `ResourceController` subclass under Settings, e.g. tax categories, refund reasons, stores) to render inside the `spree/admin_settings` layout (or a Turbo frame when requested) and flag the request as a settings area via `@settings_area`.

**Why this priority**: Nearly every "Settings" admin page composes this concern with `ResourceController`; it's a small, targeted extension rather than the primary CRUD mechanism.

**Independent Test**: Include the concern in any admin controller, request a page, and confirm `@settings_area` is `true` and the layout resolves to `spree/admin_settings` (or `turbo_rails/frame` for a Turbo Frame request).

**Acceptance Scenarios**:

1. **Given** a controller including `SettingsConcern`, **When** any action runs, **Then** `@settings_area` is set to `true` via a `before_action`.
2. **Given** a Turbo Frame request, **When** `choose_layout` is invoked, **Then** it returns `'turbo_rails/frame'` instead of `'spree/admin_settings'`.

---

### User Story 4 - Hook custom logic into create/update/destroy/new/edit via callbacks (Priority: P3)

A developer registers `before`/`after`/`fails` callback methods for `:new_action`, `:edit_action`, `:create`, `:update`, `:destroy` at the class level (`Spree::Admin::Callbacks`), without overriding the action method itself.

**Why this priority**: An escape hatch used by a minority of controllers needing side effects (e.g. sending an email after create) without duplicating the full action body.

**Independent Test**: Register a `before`/`after`/`fails` callback for `:create` on a subclass and confirm it fires at the right point in `ResourceController#create`.

**Acceptance Scenarios**:

1. **Given** `self.create.before :some_method`, **When** `create` runs, **Then** `some_method` is invoked before `@object.save`.
2. **Given** `self.create.fails :some_method`, **When** `@object.save` returns false, **Then** `some_method` is invoked instead of the `after` callbacks.

---

### User Story 5 - Render styled form fields via `Spree::Admin::FormBuilder` (Priority: P3)

A developer builds a `new`/`edit` form using `spree_text_field`, `spree_money_field`, `spree_select`, `spree_check_box`, etc. instead of raw Rails form helpers, to get consistent labels, required-field indicators, help text/bubbles, error messages, and locale-aware money formatting for free.

**Why this priority**: Presentation-layer helper consumed by nearly all `ResourceController` views, but it doesn't gate whether CRUD/settings functionality works — it's the last piece needed for a fully "native-feeling" admin form.

**Independent Test**: Render a form partial with `form_for @object, builder: Spree::Admin::FormBuilder do |f| ... f.spree_text_field :name ... end` and confirm labels, error messages, and help text render around the input.

**Acceptance Scenarios**:

1. **Given** a field with validation errors, **When** `spree_text_field` renders, **Then** the error message from `error_message_on` appears alongside the input.
2. **Given** a money field with a currency and locale, **When** `spree_money_field` renders, **Then** the value is formatted with the currency's decimal/thousands separators and the currency symbol appended.

### Edge Cases

- What happens when `permitted_resource_params` is not overridden? `ResourceController#permitted_resource_params` raises `NotImplementedError` — this is intentional; every concrete subclass must supply its own permitted params (no global allowlist fallback in this base class).
- How does the system handle a model with neither `_prefix_id_prefix` nor FriendlyId? `find_resource` falls back to plain `base_scope.find(params[:id])` (raw ID).
- How does the system handle `destroy` failing (e.g. FK/association guard)? `@object.destroy` returns false; `invoke_callbacks(:destroy, :fails)` fires, an error flash is set, and (for HTML) no redirect happens — the current page re-renders with the flash.
- How does the system handle a model that doesn't respond to `accessible_by` (no CanCanCan model adapter)? `scope` falls back to `base_scope.includes(collection_includes)` with no accessibility filtering (relies on the controller-level `authorize!` calls instead).
- How does the system handle a `current_vendor` in scope (multi-vendor marketplace extension) when the model supports `with_vendor`? `scope` chains `.with_vendor(current_vendor)` onto the base scope.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `ResourceController` MUST provide `index`, `new`, `edit`, `create`, `update`, `destroy` actions usable by any subclass with zero action-body overrides, given `model_class` and `permitted_resource_params` are resolvable.
- **FR-002**: `ResourceController` MUST scope both the index collection and individual `find_resource`/`build_resource` lookups to the current store via `model_class.for_store(current_store)` when the model class responds to `for_store`.
- **FR-003**: `ResourceController` MUST resolve member records by prefixed ID (`find_by_prefix_id!`) when the model class defines `_prefix_id_prefix`, by FriendlyId slug (`.friendly.find`) when the model uses FriendlyId, and otherwise by raw primary key (`find`).
- **FR-004**: `ResourceController` MUST support parent-scoped ("nested") resources via the class-level `belongs_to(model_name, find_by:)` DSL, deriving `scope`, `find_resource`, `build_resource`, and all URL helpers from the resolved `parent` when declared.
- **FR-005**: `ResourceController` MUST authorize collection actions via CanCanCan's `accessible_by(current_ability, action)` (when the model class supports it) and MUST call `authorize!` a second time against the loaded instance for member actions.
- **FR-006**: `ResourceController` MUST paginate `index` collections with Pagy's `:countish` paginator (avoiding `COUNT` queries) and apply Ransack search via `search_collection`/`search_params`, including date-range param coercion (`*_gt`/`*_lt` suffixes) into the current timezone's day boundaries.
- **FR-007**: `ResourceController#update`/`#create`/`#destroy` MUST invoke registered `Spree::Admin::Callbacks` (`before`/`after`/`fails`) at the documented points, MUST set flash messages via `flash_message_for`, and MUST respond with Turbo Streams when the corresponding `*_turbo_stream_enabled?` predicate is true, else standard HTML redirects/renders (`303 See Other` on success, `422 Unprocessable Content` on failure).
- **FR-008**: `Spree::Admin::SettingsConcern` MUST set `@settings_area = true` via a `before_action` and MUST select the `spree/admin_settings` layout, falling back to `turbo_rails/frame` for Turbo Frame requests.
- **FR-009**: `Spree::Admin::FormBuilder` MUST provide styled field helpers (`spree_text_field`, `spree_number_field`, `spree_money_field`, `spree_email_field`, `spree_date_field`, `spree_datetime_field`, `spree_text_area`, `spree_rich_text_area`, `spree_select`, `spree_collection_select`, `spree_check_box`, `spree_radio_button`, `spree_file_field`) that each render a label (with required indicator/help bubble), the input, an error message, and help text.
- **FR-010**: `Spree::Admin::FormBuilder#spree_money_field` MUST format displayed values using the given currency's (or the current `I18n.locale`'s) decimal/thousands separators and append the currency symbol.

### Key Entities

- **`Spree::Admin::ResourceController`**: Abstract base controller (inherits `Spree::Admin::BaseController`) providing generic CRUD, pagination, Ransack search, CanCanCan authorization, prefixed-ID/FriendlyId resolution, and parent-nesting for every concrete legacy admin resource controller.
- **`Spree::Admin::Resource`**: Value object (constructed in `ResourceController#resource`) encapsulating `controller_path`, `controller_name`, parent model name, and `object_name` — used for route-helper and instance-variable naming.
- **`Spree::Admin::Callbacks` / `Spree::Admin::ActionCallbacks`**: Class-level DSL + per-action callback registry (`before`/`after`/`fails` method lists) letting subclasses hook into `new_action`/`edit_action`/`create`/`update`/`destroy` without overriding the action.
- **`Spree::Admin::SettingsConcern`**: Controller concern flagging a controller as part of the Settings area and selecting its layout.
- **`Spree::Admin::FormBuilder`**: Custom `ActionView::Helpers::FormBuilder` subclass providing Spree-styled field helpers for `new`/`edit` views.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/admin` (legacy Rails admin) | Yes | This IS the module — `ResourceController`, `SettingsConcern`, `FormBuilder`, `Callbacks`/`ActionCallbacks` are internal framework classes consumed by every concrete `spree/admin/app/controllers/spree/admin/*_controller.rb` (tax categories, refund reasons, webhook endpoints, metafield definitions, stores, policies, shipping categories, exports, reimbursement types, etc.) |
| `spree/core` (models, services) | No | Consumed models (`for_store`, `_prefix_id_prefix`, `accessible_by`) live here but are out of scope for this feature |
| `spree/api` (Store/Admin API v3) | No | — |
| `packages/dashboard` (admin SPA) | No | — |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | No | — |
| `docs/plans/` | No | Frozen legacy framework, not an active architectural direction; no new `docs/plans/` entry needed |

### API Contract

N/A — this is a server-rendered (HTML/Turbo Stream) legacy Rails admin framework, not an API v3 surface. It has no `spree/api` counterpart of its own (see Migration Notes below for the closest analog).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every concrete legacy admin controller under `spree/admin/app/controllers/spree/admin/` that inherits `ResourceController` supports full CRUD by overriding only `permitted_resource_params` (and, optionally, `model_class`/`scope`/`collection_includes`/`collection_default_sort`) — no action-method duplication.
- **SC-002**: 100% of nested (parent-scoped) admin controllers correctly resolve their parent and derive URLs from it, verified by the `belongs_to` DSL producing working nested routes.
- **SC-003**: 100% of Settings-area admin controllers render inside the `spree/admin_settings` layout (or the Turbo Frame layout when applicable) purely by including `SettingsConcern` — no manual `layout` declarations needed.

## Assumptions

- This is an internal framework/extension-point feature: "requirements" describe existing behavior contracts that concrete subclasses rely on, not new user-facing capability.
- Scope is limited to the four base classes named in Key Entities; the ~50+ concrete controllers that subclass `ResourceController` (tax categories, refund reasons, webhook endpoints, etc.) are consumers, not part of this feature's surface.
- No production code changes are anticipated — this document exists purely to give the frozen legacy framework spec-kit coverage for migration/reference purposes.
- Existing RSpec controller specs (`spree/admin/spec/controllers/`) are assumed to already cover this behavior; this migration does not add new tests.

## Migration Notes

- **This module is frozen.** `spree/admin` (the legacy Rails admin engine) is being phased out per the project constitution (Principle I: Module Boundaries) and `CLAUDE.md` — no new features should be added here. Any new admin work belongs in `packages/dashboard` (the React SPA).
- The rough SPA-side equivalent of this generic-CRUD-base pattern is **`027-api-v3-resource-framework`** (`Spree::Api::V3::ResourceController` and its `Store`/`Admin` subclasses), which the dashboard consumes via **`packages/dashboard` resource hooks** (`useResourceMutation`, `use-[resource].ts`) instead of server-rendered forms/views.
- Where `ResourceController` gives a legacy admin controller CRUD via subclassing + Rails views, the modern path is: `spree/api` Admin API v3 controller (CRUD via `027`) → generated SDK types → a dashboard route/hook (React Hook Form + Zod) — there is no direct line-for-line replacement of `FormBuilder`, `SettingsConcern`, or the `Callbacks` DSL; those concerns are handled by React components, TanStack Router layouts, and mutation hook composition respectively.
