# Implementation Plan: Admin Resource/Settings Controllers

**Branch**: `031-admin-resource-settings-controllers` | **Date**: 2026-08-25 | **Spec**: `specs/031-admin-resource-settings-controllers/spec.md`

**Input**: Feature specification from `/specs/031-admin-resource-settings-controllers/spec.md`

**Note**: This module is frozen (`spree/admin`, legacy Rails admin) — this plan documents existing structure for migration/reference; it does not propose new work.

## Summary

`Spree::Admin::ResourceController` is the generic CRUD base class every concrete legacy admin controller (`spree/admin/app/controllers/spree/admin/*_controller.rb`) inherits from. It provides `index`/`new`/`edit`/`create`/`update`/`destroy` with pagination (Pagy `:countish`), Ransack search, CanCanCan authorization, prefixed-ID/FriendlyId resolution, store scoping (`for_store`), and optional parent-nesting (`belongs_to`). It's composed with `Spree::Admin::SettingsConcern` (layout selection for the Settings area), `Spree::Admin::Callbacks`/`ActionCallbacks` (before/after/fails hooks per action, no override needed), and `Spree::Admin::FormBuilder` (styled `new`/`edit` form helpers). This plan documents the existing framework as-is; no new code is being added.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/admin` gem) — backend only, server-rendered HTML/Turbo Streams

**Primary Dependencies**: CanCanCan (authorization), Ransack (search), Pagy (pagination, `:countish` mode), `ar_lazy_preload` (`preload_associations_lazily`), Turbo Rails (turbo-stream responses, `turbo_rails/frame` layout), `state_machines-activerecord` (indirectly, via consumer models), Rails `ActionView::Helpers::FormBuilder`

**Storage**: PostgreSQL/SQLite3 via ActiveRecord — this feature has no migrations of its own; it operates on whatever model class a concrete subclass points `model_class` at

**Testing**: RSpec + Factory Bot, controller specs under `spree/admin/spec/controllers/spree/admin/`, `render_views` + `stub_authorization!` per project convention

**Target Platform**: Rails engine gem (`spree/admin`) mounted into a Spree host app's `/admin` namespace

**Project Type**: Monorepo — single Ruby gem, `spree/admin` only. No frontend/API/other-gem work.

**Performance Goals**: N/A — inherited from existing behavior; `:countish` pagination and `ar_lazy_preload` already avoid the two most common admin-list perf pitfalls (COUNT queries, N+1s)

**Constraints**: Frozen module — per constitution Principle I / VI and `CLAUDE.md`, `spree/admin` is "being phased out — do not add new features here." This plan is documentation-only.

**Scale/Scope**: Framework consumed by ~50+ concrete admin controllers across the `spree/admin` engine (tax categories, refund reasons, webhook endpoints, metafield definitions, stores, policies, shipping categories, exports, reimbursement types, and more)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/admin` only, no cross-module reach. This module itself is explicitly named as "phased out" in Principle I — the plan does not add new features, only documents existing ones. PASS.
- **II. Admin API Is the Only Frontend Data Source**: N/A — no `packages/dashboard` work; this is a server-rendered legacy admin surface, not an SPA data source.
- **III. Read/Write Field Symmetry**: N/A — no Alba serializer involved; `permitted_resource_params` is a per-subclass Rails `params.permit` concern, not an API v3 contract.
- **IV. Test-Backed**: RSpec controller specs (`spree/admin/spec/controllers/spree/admin/`) are the existing/expected coverage per `CLAUDE.md` ("Controller specs: always add `render_views`, use `stub_authorization!`"). No new tests added by this migration — existing suite assumed to already exercise this behavior.
- **V. Translations and Prefixed IDs**: Partial — `FormBuilder#get_label` already resolves labels via `I18n.t`/`Spree.t`-style lookups (existing behavior, not new); prefixed-ID resolution (`find_by_prefix_id!`) is already implemented in `find_resource`/`parent`. No new strings or IDs introduced.
- **VI. `docs/plans/` for Architectural Changes**: N/A — no architectural change; this is reverse-engineered documentation of a frozen framework, not new work requiring a `docs/plans/` entry.

No violations — no Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/031-admin-resource-settings-controllers/
├── plan.md              # This file
├── spec.md              # Feature specification (already written)
└── tasks.md             # Task breakdown (already written)
```

### Source Code (repository root)

```text
# spree/admin — legacy Rails admin engine (the only module this feature touches)
spree/admin/
├── app/controllers/spree/admin/resource_controller.rb        # generic CRUD base
├── app/controllers/spree/admin/base_controller.rb             # parent of ResourceController (auth, current_store, current_ability)
├── app/controllers/concerns/spree/admin/settings_concern.rb   # Settings-area layout/flag concern
├── app/models/spree/admin/resource.rb                         # Resource value object (model_name/object_name/controller_path)
├── app/models/spree/admin/form_builder.rb                      # styled ActionView FormBuilder subclass
├── lib/spree/admin/callbacks.rb                                # class-level before/after/fails DSL
├── lib/spree/admin/action_callbacks.rb                         # per-action callback method registry
├── app/controllers/spree/admin/*_controller.rb                 # ~50+ concrete subclasses (consumers, not touched)
└── spec/controllers/spree/admin/*_controller_spec.rb           # existing RSpec coverage (not added/changed by this migration)
```

**Structure Decision**: Backend-only, single gem: `spree/admin`. No `spree/core`, `spree/api`, or `packages/*` changes — this feature is entirely the legacy admin's internal controller framework, and per Module Impact in spec.md, every other module row is "No".

## Complexity Tracking

*No violations — table omitted.*
