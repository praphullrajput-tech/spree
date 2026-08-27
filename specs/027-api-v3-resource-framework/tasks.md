---

description: "Task list template for feature implementation"
---

# Tasks: API v3 Resource Framework

**Input**: Design documents from `/specs/027-api-v3-resource-framework/`

**Prerequisites**: plan.md, spec.md

**Tests**: Already present and passing as part of the existing `spree/api` suite — this is a reverse-engineered spec for shipped code, not new work.

**Organization**: Tasks are grouped by user story, mirroring spec.md. All tasks below are marked complete because the framework already exists in the codebase; this file records what was built for traceability, not a forward implementation plan.

## Path Conventions

- **API framework**: `spree/api/app/controllers/spree/api/v3/`, concerns in `spree/api/app/controllers/concerns/spree/api/v3/`, specs in `spree/api/spec/controllers/spree/api/v3/`
- No `spree/core` or `packages/*` paths apply to this feature.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the touched module builds/tests cleanly.

- [x] T001 Backend stack builds: `spree/api` gem loads within a Spree host app (`pnpm server:dev` boots successfully with these controllers mounted)
- [x] T002 [P] Baseline backend: `cd spree/api && bundle exec rspec` passes

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The base controller hierarchy that every resource controller depends on.

- [x] T003 [spree/api] `Spree::Api::V3::BaseController` (`spree/api/app/controllers/spree/api/v3/base_controller.rb`) — rate limiting, JWT/API-key auth hooks, locale/currency/market resolution, security headers, Pagy
- [x] T004 [spree/api] `Spree::Api::V3::ResourceController` (`spree/api/app/controllers/spree/api/v3/resource_controller.rb`) — `index`/`show`/`create`/`update`/`destroy`, `scope`, `collection`, `ransack_params` with prefixed-ID decoding, `permitted_params` default inference
- [x] T005 [spree/api] `Spree::Api::V3::ParamsNormalizer` concern (`concerns/spree/api/v3/params_normalizer.rb`) — prefixed-ID resolution + nested-attributes normalization on write, `prepend`-safe across the hierarchy
- [x] T006 [spree/api] `Spree::Api::V3::Store::BaseController` + `Store::ResourceController` (`spree/api/app/controllers/spree/api/v3/store/`) — publishable-key auth, channel resolution, storefront gating
- [x] T007 [spree/api] `Spree::Api::V3::Admin::BaseController` + `Admin::ResourceController` (`spree/api/app/controllers/spree/api/v3/admin/`) — JWT/secret-key auth, scoped authorization, `render_result_error`/`decode_ids` helpers

**Checkpoint**: Foundation in place — concrete resource controllers can be built on top.

---

## Phase 3: User Story 1 - Add a new Admin API resource with full CRUD (Priority: P1) 🎯 MVP

**Goal**: A subclass with only `model_class`/`serializer_class` gets full CRUD.

### Tests for User Story 1

- [x] T008 [P] [US1] `spree/api/spec/controllers/spree/api/v3/resource_controller_spec.rb` — base CRUD, scoping, pagination behavior
- [x] T009 [P] [US1] `spree/api/spec/controllers/spree/api/v3/admin/base_controller_spec.rb` — admin auth wiring via a test controller

### Implementation for User Story 1

- [x] T010 [US1] `authorize_resource!` + `ability_action_for_request` mapping (GET→show, POST→create, PATCH/PUT→update, DELETE→destroy) in `resource_controller.rb`
- [x] T011 [US1] `destroy` action defers to model `can_be_deleted?` (422) ahead of CanCanCan (403) — `resource_controller.rb`
- [x] T012 [US1] `Spree::Api::V3::ScopedAuthorization` concern for secret-API-key scope enforcement (`concerns/spree/api/v3/scoped_authorization.rb`)
- [x] T013 [US1] ~300 concrete Admin API controllers built on this contract (`spree/api/app/controllers/spree/api/v3/admin/*_controller.rb`)

**Checkpoint**: User Story 1 functional and independently verified via existing controller specs.

---

## Phase 4: User Story 2 - Add a new Store API resource, read-only by default (Priority: P1)

**Goal**: New Store resources default to read-only via routing; writes are opt-in.

### Tests for User Story 2

- [x] T014 [P] [US2] Existing Store API integration specs cover read-only defaults and opt-in write endpoints (e.g. carts, customers, addresses)

### Implementation for User Story 2

- [x] T015 [US2] `Spree::Api::V3::StorefrontGating` concern (`concerns/spree/api/v3/storefront_gating.rb`) — `login_required`/`prices_hidden` posture, `allow_guest_storefront_access!` opt-out
- [x] T016 [US2] `Spree::Api::V3::ChannelResolution` concern (`concerns/spree/api/v3/channel_resolution.rb`) — `X-Spree-Channel` header resolution into `Spree::Current.channel`
- [x] T017 [US2] Concrete Store API controllers (`spree/api/app/controllers/spree/api/v3/store/*_controller.rb`) — most read-only via routing, carts/customers/wishlists opt into writes

**Checkpoint**: User Story 2 functional — verified via existing Store API integration specs.

---

## Phase 5: User Story 3 - Resource with legacy-name write bridge (Priority: P2)

**Goal**: Read/write field symmetry via model-level aliasing, not controller/SDK mappers.

### Implementation for User Story 3

- [x] T018 [US3] `permitted_params` default inference from `Spree::PermittedAttributes` (`resource_controller.rb`) as the shared allowlist mechanism
- [x] T019 [US3] Model-level legacy-column aliases (e.g. `Spree::OptionType#label`/`label=`) living outside this framework but relying on it never introducing its own translation layer

**Checkpoint**: User Story 3 functional — verified by example resources following the pattern.

---

## Phase 6: User Story 4 - Nested resource under a parent (Priority: P3)

**Goal**: `set_parent`/`@parent`/`parent_association` support nested collections.

### Implementation for User Story 4

- [x] T020 [US4] `set_parent` hook + `@parent`-aware `scope`/`build_resource` in `resource_controller.rb`
- [x] T021 [US4] `parent_association`, `parent_ability_action`, `authorize_parent!` in `resource_controller.rb`
- [x] T022 [US4] `Spree::Api::V3::Admin::SubclassedResource` concern (`concerns/spree/api/v3/admin/subclassed_resource.rb`) for nested STI create/update (PromotionAction/PromotionRule under Promotion)
- [x] T023 [US4] `Spree::Api::V3::BulkOperations` concern (`concerns/spree/api/v3/bulk_operations.rb`) as an opt-in mixin for bulk tag actions

**Checkpoint**: All user stories functional and independently verified.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T024 [P] Rate limiting (`RATE_LIMIT_RESPONSE`, `rate_limit` in `base_controller.rb`) + `RateLimitHeaders` concern
- [x] T025 [P] `SecurityHeaders` concern applied uniformly across Store + Admin controllers
- [x] T026 [P] `LocaleAndCurrency` concern — market/locale/currency resolution shared across both APIs
- [x] T027 Full backend suite: `cd spree/api && bundle exec rspec` passes
- [x] T028 Reference: `docs/plans/6.0-admin-api.md` documents the ~300-endpoint Admin REST API surface this framework serves

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** blocks all user stories.
- **User Stories (Phase 3-6)**: US1 and US2 (both P1) are the dominant paths; US3 (P2) and US4 (P3) are layered extensions already in place.
- **Polish (Phase 7)**: cross-cutting concerns shared by all stories.

## Notes

- This tasks.md is retrospective: all items reflect already-shipped code identified during brownfield migration, not planned work.
- No `[NEEDS CLARIFICATION]` items — the framework's contract was fully recoverable from source and existing specs.
