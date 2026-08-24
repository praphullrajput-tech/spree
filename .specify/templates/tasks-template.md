---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The examples below include test tasks. Tests are OPTIONAL - only include them if explicitly requested in the feature specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Use the real module paths from plan.md's Project Structure — not generic
placeholders:

- **Backend model/service**: `spree/core/app/{models,services,finders}/spree/...`, migration in `spree/core/db/migrate/`, spec in `spree/core/spec/...`
- **API endpoint**: `spree/api/app/controllers/spree/api/v3/{store,admin}/...`, serializer in `spree/api/app/serializers/spree/api/v3/...`, integration spec in `spree/api/spec/integration/`
- **Admin SPA**: `packages/dashboard/src/{routes,hooks,schemas,components}/...`, e2e in `packages/dashboard/e2e/`
- **Shared frontend**: `packages/dashboard-ui/src/components/...` (headless, no hooks), `packages/dashboard-core/src/{registries,providers}/...`
- Delete whichever of the above don't apply to this feature per its Module Impact table

<!--
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.

  The /speckit-tasks command MUST replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3...)
  - Feature requirements from plan.md
  - Entities from data-model.md
  - Endpoints from contracts/

  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as an MVP increment

  DO NOT keep these sample tasks in the generated tasks.md file.
  ============================================================================
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the touched module(s) build/test cleanly before adding code

- [ ] T001 Confirm dev stack is up: `pnpm server:dev` (backend) and/or `cd packages/dashboard && pnpm dev` (frontend) — per Module Impact table
- [ ] T002 [P] Baseline backend: `cd spree/core && bundle exec rspec` (or the touched gem) passes on main
- [ ] T003 [P] Baseline frontend: `pnpm typecheck && pnpm lint` passes at workspace root

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

Examples of foundational tasks (adjust based on plan.md's Module Impact table
— delete rows for modules this feature doesn't touch):

- [ ] T004 [spree/core] Add migration in `spree/core/db/migrate/` (no FKs, no defaults, explicit `null: false` — see constitution Quality Gates)
- [ ] T005 [spree/core] Create base model in `spree/core/app/models/spree/[entity].rb`, inheriting `Spree.base_class`, including `Spree::Metafields`/`Spree::Metadata` if applicable
- [ ] T006 [spree/api] Add Ransack allowlist (`whitelisted_ransackable_attributes`/`_associations`/`_scopes`) on any model the API will filter on
- [ ] T007 [packages/dashboard-core] Register new table/nav/slot entries if this feature adds an admin page
- [ ] T008 [packages/dashboard] Add i18next keys to `packages/dashboard/src/locales/en.json` (and `dashboard-core/src/locales/en.json` for cross-cutting copy) — every locale file, not just `en`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**
> Pragmatic per constitution Principle IV — skip tests for standard Rails
> validations or framework behavior; write them for custom logic.

- [ ] T010 [P] [US1] RSpec model/service spec in `spree/core/spec/{models,services}/spree/[name]_spec.rb`
- [ ] T011 [P] [US1] API integration spec (happy path + simple 422) in `spree/api/spec/integration/[resource]_spec.rb`
- [ ] T012 [P] [US1] Vitest unit test in `packages/dashboard/src/.../[name].test.ts`
- [ ] T013 [P] [US1] Playwright e2e in `packages/dashboard/e2e/[resource].spec.ts` — drive via `getByRole`/`getByLabel`, assert on visible UI, no `waitForResponse`

### Implementation for User Story 1

- [ ] T014 [P] [US1] Model/concern in `spree/core/app/models/spree/[entity].rb`
- [ ] T015 [US1] Service object in `spree/core/app/services/spree/[namespace]/[service].rb` (depends on T014)
- [ ] T016 [US1] Controller + serializer in `spree/api/app/{controllers,serializers}/spree/api/v3/...` — read/write field symmetry per constitution Principle III
- [ ] T017 [US1] Run type-generation pipeline if serializers changed: `bundle exec rake typelizer:generate` → `pnpm generate:zod` → `bundle exec rake rswag:specs:swaggerize` (Lefthook handles steps 1-2 on commit; steps 3+ are manual)
- [ ] T018 [US1] Dashboard route/form in `packages/dashboard/src/routes/...`, hook in `src/hooks/use-[resource].ts` — never call `adminClient` directly from components

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2 (OPTIONAL - only if tests requested) ⚠️

- [ ] T018 [P] [US2] Contract test for [endpoint] in tests/contract/test_[name].py
- [ ] T019 [P] [US2] Integration test for [user journey] in tests/integration/test_[name].py

### Implementation for User Story 2

- [ ] T020 [P] [US2] Create [Entity] model in src/models/[entity].py
- [ ] T021 [US2] Implement [Service] in src/services/[service].py
- [ ] T022 [US2] Implement [endpoint/feature] in src/[location]/[file].py
- [ ] T023 [US2] Integrate with User Story 1 components (if needed)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 3 (OPTIONAL - only if tests requested) ⚠️

- [ ] T024 [P] [US3] Contract test for [endpoint] in tests/contract/test_[name].py
- [ ] T025 [P] [US3] Integration test for [user journey] in tests/integration/test_[name].py

### Implementation for User Story 3

- [ ] T026 [P] [US3] Create [Entity] model in src/models/[entity].py
- [ ] T027 [US3] Implement [Service] in src/services/[service].py
- [ ] T028 [US3] Implement [endpoint/feature] in src/[location]/[file].py

**Checkpoint**: All user stories should now be independently functional

---

[Add more user story phases as needed, following the same pattern]

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] TXXX [P] Update `docs/developer/` and/or add a `docs/plans/` entry if this qualifies as an architectural change (constitution Principle VI)
- [ ] TXXX Full backend suite: `cd spree/core && bundle exec rspec` (and any other touched gem)
- [ ] TXXX Full frontend suite: `pnpm typecheck && pnpm lint && pnpm test` at workspace root
- [ ] TXXX [P] `packages/dashboard && pnpm test:e2e` for touched admin flows
- [ ] TXXX Verify all locale files (not just `en.json`) have matching keys in both `packages/dashboard/src/locales/` and `packages/dashboard-core/src/locales/`
- [ ] TXXX Run quickstart.md validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (if tests requested):
Task: "Contract test for [endpoint] in tests/contract/test_[name].py"
Task: "Integration test for [user journey] in tests/integration/test_[name].py"

# Launch all models for User Story 1 together:
Task: "Create [Entity1] model in src/models/[entity1].py"
Task: "Create [Entity2] model in src/models/[entity2].py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
