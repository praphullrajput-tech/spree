---
description: "Task list for the (already-shipped) Dashboard Core Framework, reverse-engineered during brownfield spec-kit migration"
---

# Tasks: Dashboard Core Framework

**Input**: Design documents from `/specs/033-dashboard-core-framework/`

**Prerequisites**: plan.md, spec.md

**Tests**: Vitest unit tests already exist/are supported via each registry's `__reset*Registry()` test-only helper; no new tests were required by this migration.

**Organization**: Tasks are grouped by user story (spec.md) to reflect how the framework's capabilities map to its three usage scenarios. All tasks below are marked complete — this is a retroactive record of already-implemented work, not a forward plan.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Could have run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

## Path Conventions

All paths are under `packages/dashboard-core/src/` (this feature's home) with `packages/dashboard/src/` as the consuming side, per plan.md's Project Structure.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm frontend workspace builds/tests cleanly: `pnpm typecheck && pnpm lint` at workspace root, `pnpm test` for `packages/dashboard-core`
- [x] T002 [P] Establish the `adminClient` singleton in `packages/dashboard-core/src/client.ts` (`createAdminClient` from `@spree/admin-sdk`, `VITE_SPREE_API_URL`-driven base URL supporting dev-proxy / same-origin-prod / cross-origin-prod topologies)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Registry primitives and shared query-key conventions that every user story depends on

- [x] T003 [P] Table registry core in `packages/dashboard-core/src/lib/table-registry.ts` — `ColumnDef` discriminated union (string/boolean/number/date/currency/enum/resource/tags filter types), `defineTable`/`getTable`, `tables` mutation Proxy (`addColumn`/`removeColumn`/`updateColumn`)
- [x] T004 [P] Pending-mutation queue in `table-registry.ts` — mutations against a not-yet-`defineTable`-d table key are queued (`pending` Map) and replayed via `flushPending` when the table registers, with `AggregateError` surfacing all queued-mutation failures at once
- [x] T005 [P] Timestamp-column helper in `packages/dashboard-core/src/lib/timestamp-columns.tsx` (`ensureTimestampColumns`) — auto-appended by `defineTable` so every table gets consistent `created_at`/`updated_at` columns
- [x] T006 [P] Nav registry in `packages/dashboard-core/src/lib/nav-registry.ts` — `add`/`remove`/`update`/`insertBefore`/`insertAfter`, position-sorted `useSyncExternalStore` snapshot (`useNavEntries`), unique-key enforcement
- [x] T007 [P] Settings-nav registry in `packages/dashboard-core/src/lib/settings-nav-registry.ts` — entries + groups, `label`/`labelKey` validation, grouped snapshot (`useSettingsNav`)
- [x] T008 [P] Slot registry in `packages/dashboard-core/src/lib/slot-registry.ts` — `registerSlot`/`removeSlot`/`updateSlot`, per-slot `useSlotEntries` hook, `SlotAmbientContext` type
- [x] T009 [P] Permission subject/action constants in `packages/dashboard-core/src/lib/permissions.ts` (`Subject`, `Action`) mirroring CanCanCan class names surfaced by the Admin API's `/api/v3/admin/me`
- [x] T010 [P] Query-key conventions in `packages/dashboard-core/src/lib/query-keys.ts` — `resourceKey`/`useResourceKey`/`useResourceKeyBuilder`/`withStoreScope`, canonical `[resource, storeId, ...rest]` shape
- [x] T011 [P] Shared `QueryClient` instance in `packages/dashboard-core/src/lib/query-client.ts`

**Checkpoint**: Registries and query-key conventions in place — user story work can build on top

---

## Phase 3: User Story 1 - Plugin author extends the admin SPA (Priority: P1) 🎯 MVP

**Goal**: A single `defineDashboardPlugin(config)` call registers nav/settings-nav/slot/table extensions from one config object, with per-registry uniqueness enforcement and aggregated error reporting.

**Independent Test**: A plugin entry module calling `defineDashboardPlugin({ nav, slots, tables })` produces a working nav item + slot component + table column with zero `packages/dashboard` route edits.

### Implementation for User Story 1

- [x] T012 [US1] `DashboardPluginConfig` interface + `defineDashboardPlugin` facade in `packages/dashboard-core/src/plugin.ts` — fans `nav`/`settingsNavGroups`/`settingsNav`/slots/`tables` out to the four Phase 2 registries
- [x] T013 [US1] Error-collection semantics in `defineDashboardPlugin` — each registry call wrapped in a `safely()` helper so one duplicate key doesn't prevent the rest of the config from registering; single failure rethrows directly, multiple failures rethrow as `AggregateError`
- [x] T014 [US1] `TableMutations` shape (`add`/`remove`/`update`) in `plugin.ts`, delegating to the `tables` Proxy mutator built in T003/T004 (inherits the pending-queue replay semantics automatically)
- [x] T015 [US1] Module-level usage documentation (JSDoc example) at the top of `plugin.ts` demonstrating the canonical plugin entry-module pattern for downstream plugin authors

**Checkpoint**: `defineDashboardPlugin` is the complete, documented plugin surface — independently usable without any other user story's providers mounted

---

## Phase 4: User Story 2 - Dashboard developer builds a registry-driven table/mutation/permission UI (Priority: P2)

**Goal**: Resource pages get sortable/filterable tables, store-scoped mutation invalidation + toasts, and declarative permission gating without hand-rolled boilerplate per page.

**Independent Test**: `defineTable('widgets', {...})` + `useResourceMutation({...})` + `<Can I a>` behave correctly against a stub table/permission set.

### Implementation for User Story 2

- [x] T016 [P] [US2] `useResourceMutation` in `packages/dashboard-core/src/hooks/use-resource-mutation.ts` — wraps TanStack `useMutation`, auto-injects `storeId` into `invalidate` keys via `withStoreScope`, default success/error toasts (each independently disableable via `false`), suppresses error toast on 422 (`isValidationError`)
- [x] T017 [P] [US2] `mapSpreeErrorsToForm` in `packages/dashboard-core/src/lib/form-errors.ts` — routes `SpreeError.message` to `formState.errors.root`, routes only flat/non-dotted/non-`base` `details` keys to per-field errors, returns `false` for non-`SpreeError` so callers fall back to their own toast/log
- [x] T018 [P] [US2] `<Can I a fallback>` component in `packages/dashboard-core/src/components/can.tsx` — reads `usePermissions()`, renders `children`/`fallback`, documented as UX-only (backend `authorize!` remains the real boundary)
- [x] T019 [P] [US2] `<Slot name context fallback>` component in `packages/dashboard-core/src/components/slot.tsx` — renders `useSlotEntries(name)` sorted by position, filtered by each entry's `if` predicate, merges ambient context placeholder with slot-specific `context`
- [x] T020 [US2] `getDisplayableColumns`/`getDefaultColumnKeys`/`getFilterableColumns`/`getSortableColumns` helpers in `table-registry.ts` consumed by `<ResourceTable>` (in `packages/dashboard-core/src/components/resource-table.tsx`, outside this feature's direct scope but the primary consumer of T003-T005)

**Checkpoint**: Table/mutation/permission/slot primitives are independently testable and already power every `packages/dashboard` resource route

---

## Phase 5: User Story 3 - App-root auth/store/permission context (Priority: P3)

**Goal**: Session lifecycle, current-store context, and permission-rule evaluation are available to every route via three composed providers.

**Independent Test**: Mount `AuthProvider` → `StoreProvider` → `PermissionProvider`, log in, and confirm `useAuth()`/`useStore()`/`usePermissions()` reflect the expected state.

### Implementation for User Story 3

- [x] T021 [US3] `AuthProvider`/`useAuth` in `packages/dashboard-core/src/providers/auth-provider.tsx` — `login`/`logout`/`acceptInvitation`/`updateUser`, session application via `adminClient.setToken`, locale reconciliation against the account's `selected_locale`
- [x] T022 [US3] Silent background refresh in `auth-provider.tsx` — timer scheduled ~30s before the 5-minute JWT TTL (`REFRESH_INTERVAL_MS`), serialized via `refreshPromiseRef` so concurrent refresh triggers (StrictMode/HMR/401-retry) don't double-rotate the token
- [x] T023 [US3] `adminClient.onUnauthorized` wiring in `auth-provider.tsx` — a 401 mid-session triggers an on-demand refresh attempt before the session is cleared
- [x] T024 [US3] `StoreProvider`/`useStore` in `packages/dashboard-core/src/providers/store-provider.tsx` — exposes `currencies`/`locales`/`availableLocales`/`defaultCurrency`/`defaultLocale`/`timezone`; drops stale fetch responses when `storeId` changed mid-flight (`latestStoreIdRef`); one-shot store-default locale fallback re-armed per store (`localeFallbackDoneRef`)
- [x] T025 [US3] `PermissionProvider`/`usePermissions` in `packages/dashboard-core/src/providers/permission-provider.tsx` — fetches `PermissionRule[]` from `adminClient.me.get()`, `buildPermissions` mirrors CanCanCan semantics (`manage`/`all` wildcards, last-matching-rule-wins, `isConditional` flag for per-record conditions), deny-all `EMPTY_PERMISSIONS` before rules load

**Checkpoint**: All three providers are independently mountable and power every authenticated route in `packages/dashboard`

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T026 [P] Test-only reset helpers (`__resetTableRegistry`, `__resetNavRegistry`, `__resetSettingsNavRegistry`, `__resetSlotRegistry`) added to each registry, intentionally not exported from the package's public index, to support isolated Vitest runs
- [x] T027 Verify `packages/dashboard-core/src/locales/en.json` carries the toast copy keys consumed by `use-resource-mutation.ts` (`admin.messages.saved`, `admin.errors.generic`) across all locale files
- [x] T028 Reverse-engineered spec-kit artifacts written to `specs/033-dashboard-core-framework/{spec,plan,tasks}.md` documenting the shipped framework (this migration)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — registries/query-keys BLOCK all three user stories
- **User Stories (Phase 3-5)**: All depend on Foundational; as shipped, US1 (plugin facade) sits directly on top of the Phase 2 registries, US2 (table/mutation/permission/slot UI primitives) and US3 (providers) are independent of each other and of US1
- **Polish (Phase 6)**: Depends on all user stories

### Notes

- This tasks.md is a retroactive record for an already-implemented, in-production feature (brownfield migration) — no task here represents pending work.
- Future forward-looking work (e.g., wiring real ambient values into `<Slot>`'s `SlotAmbientContext`, per the "ambient context — wired up properly once SlotProvider lands" comment in `components/slot.tsx`) is a known gap noted in spec.md's Migration Notes, not tracked as a task here since it wasn't part of what was reverse-engineered as shipped.
