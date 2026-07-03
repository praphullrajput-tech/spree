---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `specs/[###-feature-name]/`

**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/`

**Tests**: Test tasks are included by default for Spree features — both backend (RSpec) and frontend (Vitest/Playwright) coverage is expected unless explicitly noted as out-of-scope.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3…)
- Include exact file paths in descriptions

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Core services | `spree/core/app/services/spree/` |
| Core subscribers | `spree/core/app/subscribers/spree/` |
| Migrations | `spree/[engine]/db/migrate/` |
| Store serializers | `spree/api/app/serializers/spree/api/v3/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Store controllers | `spree/api/app/controllers/spree/api/v3/store/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend locale | `spree/[engine]/config/locales/en.yml` |
| Backend specs | `spree/[engine]/spec/` |
| TS generated types | `packages/sdk/src/types/generated/` (do not edit) |
| TS Zod schemas | `packages/sdk/src/zod/generated/` (do not edit) |
| Admin SDK types | `packages/admin-sdk/src/types/generated/` (do not edit) |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard schemas | `packages/dashboard/src/schemas/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| Dashboard UI components | `packages/dashboard-ui/src/spree/` or `packages/dashboard-ui/src/ui/` |
| E2E specs | `packages/dashboard/e2e/` |

## Test Commands

```bash
# Backend (run from engine directory, e.g. spree/core or spree/api)
bundle exec rake test_app          # one-time: create dummy app
bundle exec rspec                  # full suite
bundle exec rspec spec/models/spree/[resource]_spec.rb   # single file
bundle exec rspec spec/models/spree/[resource]_spec.rb:7 # single test

# i18n check (run from spree/)
bundle exec i18n-tasks normalize

# OpenAPI regen (run from spree/api)
bundle exec rake rswag:specs:swaggerize

# Typelizer (run from spree/api)
bundle exec rake typelizer:generate

# Frontend (run from repo root or package directory)
pnpm test                          # all packages
cd packages/sdk && pnpm generate:zod
pnpm typecheck
pnpm lint

# E2E (run from packages/dashboard)
pnpm test:e2e
pnpm test:e2e:ui                   # Playwright UI mode for debugging
```

<!--
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.

  The /speckit-tasks command MUST replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3…)
  - Data model from data-model.md
  - API contracts from contracts/
  - Plan structure from plan.md

  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as an MVP increment

  DO NOT keep these sample tasks in the generated tasks.md file.
  ============================================================================
-->

---

## Phase 1: Backend Foundation (Blocking Prerequisite)

**Purpose**: Schema, model, authorization — must complete before any user story or API work.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [ ] T001 Create migration `spree/[engine]/db/migrate/[timestamp]_create_spree_[resources].rb` — add table with `null: false` required columns, no FK constraints, no default values; guard JSON columns with `respond_to?(:jsonb)`
- [ ] T002 [P] Create model `spree/core/app/models/spree/[resource].rb` — inherit `Spree.base_class`, include `Spree::Metafields` + `Spree::Metadata` if needed, declare associations with `class_name:` and `dependent:`, add state machine if applicable, add `whitelisted_ransackable_attributes`
- [ ] T003 [P] Create factory `spree/core/lib/spree/testing_support/factories/[resource]_factory.rb`
- [ ] T004 Add CanCanCan abilities to `spree/core/app/models/spree/ability.rb` — `can :manage, Spree::[Resource]` for admin; `can :read` for store
- [ ] T005 Write model spec `spree/[engine]/spec/models/spree/[resource]_spec.rb` — custom validations only; use `build` over `create`

**Checkpoint**: `bundle exec rspec spec/models/spree/[resource]_spec.rb` passes — foundation ready

---

## Phase 2: Backend API — User Story 1 (Priority: P1) 🎯 MVP

**Goal**: [What this user story delivers via the API]

**Independent Test**: `GET /api/v3/admin/[resources]` returns records with prefixed IDs

- [ ] T006 [P] [US1] Create Store serializer `spree/api/app/serializers/spree/api/v3/[resource]_serializer.rb` — customer-visible fields only, no timestamps, use `prefixed_id` for association IDs
- [ ] T007 [P] [US1] Create Admin serializer `spree/api/app/serializers/spree/api/v3/admin/[resource]_serializer.rb` — extend Store serializer, add `created_at`, `updated_at`, `deleted_at`, admin-only fields
- [ ] T008 [US1] Create Store controller `spree/api/app/controllers/spree/api/v3/store/[resources]_controller.rb` — override `model_class`, `serializer_class`, `scope`, `collection_includes`; opt into write actions only if needed
- [ ] T009 [US1] Create Admin controller `spree/api/app/controllers/spree/api/v3/admin/[resources]_controller.rb` — override `model_class`, `serializer_class`, `permitted_params`; verify field names match serializer
- [ ] T010 [US1] Add routes to `spree/api/config/routes.rb` under Store and Admin namespaces
- [ ] T011 [US1] Add i18n keys to `spree/[engine]/config/locales/en.yml`
- [ ] T012 [US1] Write integration spec `spree/api/spec/integration/spree/api/v3/admin/[resources]_spec.rb` — happy path + simple 422; used to generate OpenAPI examples

**Checkpoint**: `bundle exec rspec spec/integration/api/v3/admin/[resources]_spec.rb` passes

---

## Phase 3: Type Generation Pipeline

**Purpose**: Propagate serializer changes to TypeScript.

**⚠️ CRITICAL**: Complete before any frontend work begins.

- [ ] T013 Run `cd spree/api && bundle exec rake typelizer:generate` — verify `packages/sdk/src/types/generated/` and `packages/admin-sdk/src/types/generated/` updated
- [ ] T014 Run `cd packages/sdk && pnpm generate:zod` — verify `packages/sdk/src/zod/generated/` updated
- [ ] T015 Run `cd spree/api && bundle exec rake rswag:specs:swaggerize` — OpenAPI spec current
- [ ] T016 Run `pnpm typecheck` — zero TypeScript errors after type regen

**Checkpoint**: `pnpm typecheck` passes — types are in sync

---

## Phase 4: Frontend Feature — User Story 1 (Priority: P1)

**Goal**: [What the admin operator can do in the SPA for this story]

**Independent Test**: Admin navigates to the [resource] list, creates a record, and sees it appear

- [ ] T017 [P] [US1] Create resource hook `packages/dashboard/src/hooks/use-[resource]s.ts` — TanStack Query wrappers for list, show, create, update, delete; typed against generated Admin SDK types
- [ ] T018 [P] [US1] Create form schema `packages/dashboard/src/schemas/[resource].ts` — Zod schema, `FormValues` type, defaults, option arrays (canonical values only — no label strings)
- [ ] T019 [US1] Create list route `packages/dashboard/src/routes/_authenticated/$storeId/[resource]/index.tsx` — `<ResourceTable>` with column definitions; all column headers via `t(...)`; empty state copy via `t(...)`
- [ ] T020 [US1] Create detail/edit route `packages/dashboard/src/routes/_authenticated/$storeId/[resource]/$[resourceId].tsx` — form wired with `react-hook-form` + `zodResolver`; `mapSpreeErrorsToForm` in submit handler
- [ ] T021 [US1] Add navigation entry in relevant nav config — label via `t(...)`
- [ ] T022 [US1] Add i18n keys to `packages/dashboard/src/locales/en.json` — titles, column headers, buttons, empty states, form labels/placeholders/help, toast messages, badge/status text
- [ ] T023 [US1] Add same i18n keys to **all other locale files** in `packages/dashboard/src/locales/`

**Checkpoint**: `pnpm typecheck && pnpm lint` pass; manually verify list → create → edit → delete in browser

---

## Phase 5: E2E Coverage

**Purpose**: Playwright smoke coverage for the happy path.

- [ ] T024 Write E2E spec `packages/dashboard/e2e/[resource].spec.ts` — use `Date.now()` suffix on test data names to avoid collisions; drive through visible UI only (no `waitForResponse`); assert on visible DOM elements
- [ ] T025 Run `cd packages/dashboard && pnpm test:e2e` — suite passes

---

## Phase N: User Story 2 — [Title] (Priority: P2)

[Follow the same Backend API → Type Pipeline (if serializer changed) → Frontend Feature pattern]

---

## Phase N+1: Polish & Cross-Cutting Concerns

- [ ] TXXX [P] Run `bundle exec i18n-tasks normalize` — no missing or unused backend keys
- [ ] TXXX [P] Run `pnpm lint` — zero Biome errors across all packages
- [ ] TXXX [P] Run `pnpm test` — all Vitest tests pass
- [ ] TXXX Run full RSpec suite for affected engines — no regressions
- [ ] TXXX Review serializer fields against `permitted_params` — verify read/write symmetry
- [ ] TXXX Verify no raw integer IDs in any API response (grep `"id":` in integration test snapshots)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Backend Foundation)**: No dependencies — start immediately. Blocks everything else.
- **Phase 2 (Backend API, US1)**: Depends on Phase 1.
- **Phase 3 (Type Pipeline)**: Depends on Phase 2 (serializers must exist before Typelizer runs).
- **Phase 4 (Frontend, US1)**: Depends on Phase 3 (generated types must exist).
- **Phase 5 (E2E)**: Depends on Phase 4 (routes must exist before Playwright can visit them).
- **Phase N (Additional user stories)**: Follow the same Backend → Type Pipeline → Frontend chain per story.
- **Final Polish**: Depends on all desired user stories being complete.

### Within Each User Story

- Models before serializers
- Serializers before controllers
- Controllers before integration tests
- Integration tests before `rswag:specs:swaggerize`
- Type pipeline before any frontend work
- Resource hook + schema before route components
- Route components before i18n keys (so you know what strings to extract)
- i18n in all locales before E2E (E2E uses real locale strings)

### Parallel Opportunities

- Model and factory creation [P]
- Store and Admin serializers [P] (once model exists)
- Resource hook and form schema [P] (once types generated)
- List route and detail route [P] (once hook + schema exist)
- E2E for different user stories [P] (once each story's routes exist)

---

## Notes

- `[P]` = different files, no inter-task dependency — safe to run in parallel
- `[USn]` = maps task to user story for traceability
- Commit after each logical group; use `git commit --fixup` for follow-ups
- Never edit files under `*/generated/` — they are overwritten by the type pipeline
- Check `docs/plans/` "Constraints on Current Work" sections before implementing anything
