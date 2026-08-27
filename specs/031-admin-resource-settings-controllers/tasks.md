---
description: "Task list for Admin Resource/Settings Controllers (reverse-engineered, frozen module)"
---

# Tasks: Admin Resource/Settings Controllers

**Input**: Design documents from `/specs/031-admin-resource-settings-controllers/`

**Prerequisites**: plan.md, spec.md

**Note**: This module is frozen (`spree/admin`, legacy Rails admin). All tasks below are marked complete because they document already-shipped, already-tested behavior — this migration adds spec-kit coverage, not new code.

## Path Conventions

Single gem: `spree/admin/app/{controllers,models}/spree/admin/...`, `spree/admin/lib/spree/admin/...`, specs in `spree/admin/spec/controllers/spree/admin/...`.

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/admin` gem builds/tests cleanly on `main`: `cd spree/admin && bundle exec rspec` passes
- [x] T002 [P] Confirm dev stack: legacy admin already served under `/admin` on `pnpm server:dev` (no separate boot needed)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T003 [spree/admin] Base CRUD controller already implemented: `spree/admin/app/controllers/spree/admin/resource_controller.rb` (`index`/`new`/`edit`/`create`/`update`/`destroy`, Pagy `:countish` pagination, Ransack search, CanCanCan authorization)
- [x] T004 [spree/admin] Resource value object already implemented: `spree/admin/app/models/spree/admin/resource.rb` (backs `model_class`/`object_name`/URL-helper naming)
- [x] T005 [spree/admin] Prefixed-ID / FriendlyId resolution already implemented in `ResourceController#find_resource` and `#parent` (falls back to raw `find` when neither applies)
- [x] T006 [spree/admin] Parent-nesting DSL already implemented: class-level `belongs_to(model_name, find_by:)` in `ResourceController` (`@parent_data`, `parent`, nested URL helpers)

**Checkpoint**: Foundation already shipped — user story documentation below has no further code dependency.

---

## Phase 3: User Story 1 - Add a new admin resource controller with full CRUD (Priority: P1) 🎯 MVP

**Goal**: Confirm any subclass overriding only `permitted_resource_params` gets full CRUD for free.

**Independent Test**: Subclass `ResourceController`, override `permitted_resource_params`, wire `resources :foos` under `/admin`, exercise all 6 actions.

### Tests for User Story 1

- [x] T007 [P] [US1] Existing RSpec controller specs across `spree/admin/spec/controllers/spree/admin/*_controller_spec.rb` (e.g. `refund_reasons_controller_spec.rb`, `tax_categories_controller_spec.rb`) already exercise CRUD via concrete `ResourceController` subclasses, with `render_views` + `stub_authorization!` per project convention

### Implementation for User Story 1

- [x] T008 [P] [US1] `index`/pagination/search: `resource_controller.rb#index`, `#collection`, `#search_collection`, `#search_params` (date-range `_gt`/`_lt` coercion into current timezone)
- [x] T009 [US1] `new`/`create`: `resource_controller.rb#new`, `#create`, `#build_resource`, `#set_created_by`, `#set_currency`, callback invocation via `invoke_callbacks(:create, ...)`
- [x] T010 [US1] `edit`/`update`: `resource_controller.rb#edit`, `#update`, `#set_current_store`, `remove_assets`, callback invocation via `invoke_callbacks(:update, ...)`
- [x] T011 [US1] `destroy`: `resource_controller.rb#destroy`, flash messaging via `flash_message_for`, callback invocation via `invoke_callbacks(:destroy, ...)`
- [x] T012 [US1] Store scoping + accessibility: `resource_controller.rb#scope` (`for_store`, `with_vendor`, `accessible_by`) and `#find_resource`/`#load_resource_instance`

**Checkpoint**: User Story 1 fully documented and already functional/tested via existing concrete controllers.

---

## Phase 4: User Story 2 - Nest a resource controller under a parent (Priority: P2)

**Goal**: Confirm `belongs_to` produces correctly parent-scoped CRUD + URLs.

**Independent Test**: Declare `belongs_to :product`, hit nested routes, confirm scope derives from `parent.send(controller_name)`.

### Implementation for User Story 2

- [x] T013 [US2] Class-level DSL: `resource_controller.rb` (`class << self` block: `parent_data`, `belongs_to`)
- [x] T014 [US2] Parent resolution: `resource_controller.rb#parent` (prefix-ID vs. `find_by` vs. FriendlyId-aware lookup)
- [x] T015 [US2] Nested URL helpers: `#new_object_url`, `#edit_object_url`, `#object_url`, `#collection_url` (all branch on `parent_data.present?`)

**Checkpoint**: User Story 2 fully documented and already functional/tested via nested admin controllers (e.g. variants under products).

---

## Phase 5: User Story 3 - Build a settings-area page (Priority: P2)

**Goal**: Confirm `SettingsConcern` flags the request and selects the right layout.

**Independent Test**: Include the concern, request a page, confirm `@settings_area == true` and layout resolution.

### Implementation for User Story 3

- [x] T016 [US3] `spree/admin/app/controllers/concerns/spree/admin/settings_concern.rb` — `set_settings_area_flag` before_action, `choose_layout` (Turbo Frame vs. `spree/admin_settings`)
- [x] T017 [P] [US3] Consumers already wired: `spree/admin/app/controllers/spree/admin/{tax_categories,tax_rates,refund_reasons,stores,policies,shipping_categories,exports,metafield_definitions,webhook_endpoints,reimbursement_types}_controller.rb` all include `SettingsConcern`

**Checkpoint**: User Story 3 fully documented and already functional across every Settings-area controller.

---

## Phase 6: User Story 4 - Hook custom logic into create/update/destroy/new/edit via callbacks (Priority: P3)

**Goal**: Confirm the `before`/`after`/`fails` callback DSL fires at the right points without overriding action methods.

### Implementation for User Story 4

- [x] T018 [US4] `spree/admin/lib/spree/admin/callbacks.rb` — `ClassMethods` (`new_action`/`edit_action`/`create`/`update`/`destroy` class methods returning an `ActionCallbacks`), `invoke_callbacks` instance method
- [x] T019 [US4] `spree/admin/lib/spree/admin/action_callbacks.rb` — `ActionCallbacks` registry (`before`/`after`/`fails` method-name arrays)

**Checkpoint**: User Story 4 fully documented; callback points in `ResourceController#new`/`#edit`/`#create`/`#update`/`#destroy` already call `invoke_callbacks` at the documented points.

---

## Phase 7: User Story 5 - Render styled form fields via `Spree::Admin::FormBuilder` (Priority: P3)

**Goal**: Confirm styled field helpers render label + input + error + help consistently.

### Implementation for User Story 5

- [x] T020 [P] [US5] `spree/admin/app/models/spree/admin/form_builder.rb` — text/number/email/date/datetime/textarea/rich-text/select/collection-select/checkbox/radio/file field helpers, all wrapping label + input + `error_message_on` + help text
- [x] T021 [US5] Money field locale/currency formatting: `form_builder.rb#spree_money_field`, `#format_money_value` (currency decimal/thousands separators, symbol append)

**Checkpoint**: User Story 5 fully documented; consumed by `new`/`edit` view partials across concrete admin controllers.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T022 [P] Migration Notes cross-reference added in spec.md pointing to `027-api-v3-resource-framework` + `packages/dashboard` resource hooks as the SPA-side equivalent
- [x] T023 Full backend suite baseline confirmed: `cd spree/admin && bundle exec rspec` (existing suite, no new failures introduced by this documentation-only migration)
- [x] T024 Frozen-module notice verified present at the top of spec.md per constitution Principle I / `CLAUDE.md`

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → already satisfied (existing gem, existing tests)
- **Foundational (Phase 2)** → already shipped; blocks nothing further since no new code is added
- **User Stories (Phases 3-7)** → independently documented, all already implemented and in production use; no sequencing constraint since this is retroactive documentation, not new build order
- **Polish (Phase 8)** → depends on all user story documentation being captured in spec.md/plan.md

## Notes

- This tasks.md captures a **reverse-engineered, already-built** feature. Every task is `[x]` because the underlying code and tests already exist in `main`; the task list exists to give the constitution's spec-kit process a record of this frozen framework, not to drive new implementation.
- Per the frozen-module notice, no follow-up tasks should be added here for new capability — new admin work goes into `packages/dashboard` under its own spec (see `027-api-v3-resource-framework` for the modern equivalent).
