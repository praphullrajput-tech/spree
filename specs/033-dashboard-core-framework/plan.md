# Implementation Plan: Dashboard Core Framework

**Branch**: `033-dashboard-core-framework` | **Date**: 2026-08-24 | **Spec**: `specs/033-dashboard-core-framework/spec.md`

**Input**: Feature specification from `/specs/033-dashboard-core-framework/spec.md`

**Note**: This is a brownfield reverse-engineered plan — `packages/dashboard-core` is already implemented and in production use. This document describes the shipped architecture, not upcoming work.

## Summary

`packages/dashboard-core` is the extension framework underneath the Spree 6.0 admin SPA: four module-singleton registries (table, nav, settings-nav, slot) exposed via `useSyncExternalStore`, three React context providers (auth, store, permission) that supply session/store/CanCanCan-mirrored permission state to every route, a handful of shared hooks/utilities (`useResourceMutation`, `mapSpreeErrorsToForm`, `query-keys.ts`), and a single plugin facade (`defineDashboardPlugin`) that fans a config object out across the four registries. `packages/dashboard` consumes all of it; plugin authors depend only on `@spree/dashboard-core/plugin` and `@spree/dashboard-core` exports.

## Technical Context

**Language/Version**: TypeScript (React SPA, frontend-only feature)

**Primary Dependencies**: React 18 (`useSyncExternalStore`, Context), TanStack Query (`useMutation`, `useQueryClient`), `@spree/admin-sdk` (`createAdminClient`, `SpreeError`, `AdminUser`, `PermissionRule`, `Store` types), `sonner` (toasts), `react-hook-form` (`UseFormSetError` in `form-errors.ts`), `i18next` (`lib/i18n.ts`, referenced by `auth-provider.tsx`/`store-provider.tsx`/`use-resource-mutation.ts`)

**Storage**: N/A — this package holds no persistent storage; it proxies to the Admin API via `@spree/admin-sdk` and caches in-memory via TanStack Query

**Testing**: Vitest (frontend unit, colocated `*.test.ts` — registries have `__reset*Registry` test-only helpers for isolation between test files)

**Target Platform**: Browser — consumed by `packages/dashboard`'s Vite-built React SPA; also intended for reuse by any standalone app composing `dashboard-core` + `dashboard-ui` (e.g. a vendor panel)

**Project Type**: Monorepo TypeScript package — `packages/dashboard-core`, consumed by `packages/dashboard`

**Performance Goals**: Registry reads must not cause unnecessary re-renders — `useSyncExternalStore` + cached snapshots (`snapshotCache`, invalidated only on `notify()`) keep consumers stable across unrelated renders.

**Constraints**: Registries are module-level singletons (not React state) so plugin entry modules can register before any provider mounts; mutations against not-yet-registered tables must queue rather than throw (`table-registry.ts`'s `pending` Map).

**Scale/Scope**: ~10 source files under `packages/dashboard-core/src/{lib,providers,components,hooks}` plus `plugin.ts` and `client.ts`; consumed by every route in `packages/dashboard` (~50+ resource pages) and by any external plugin package.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Pass. This feature IS the `packages/dashboard-core` package from the Module Boundaries list. It exposes its public surface only through documented extension points (registries + `defineDashboardPlugin`); `packages/dashboard` consumes it via imports, never by reaching into internal registry state (`pending`, `registry` Maps are unexported module locals).
- **II. Admin API Is the Only Frontend Data Source**: Pass. `AuthProvider`/`StoreProvider`/`PermissionProvider` all source their data exclusively from `adminClient` (`@spree/admin-sdk`) calls against the Admin API (`/auth/*`, `/api/v3/admin/me`, `/api/v3/admin/store`) — no Rails model or server-rendered HTML access.
- **III. Read/Write Field Symmetry**: N/A — no serializer changes; this feature consumes existing Admin API responses (`AdminUser`, `Store`, `PermissionRule` types come from `@spree/admin-sdk`, generated from Alba serializers elsewhere).
- **IV. Test-Backed**: Vitest unit tests are the applicable framework (frontend-only, no backend or E2E surface introduced by this package itself — E2E coverage lives in `packages/dashboard/e2e` against consuming routes). Registries expose `__reset*Registry()` test-only helpers specifically to support isolated Vitest runs.
- **V. Translations and Prefixed IDs**: Partial/Pass. `auth-provider.tsx` and `use-resource-mutation.ts` route user-visible toast copy through `i18n.t(...)` (`admin.messages.saved`, `admin.errors.generic`). Registry-level labels (`NavEntry.label`, `SettingsNavEntry.label`/`labelKey`) support either a literal string (plugin convenience) or an i18n key (`labelKey`, used by all built-ins) — the framework itself doesn't hardcode English into the built-in nav, but does allow plugin authors to pass literal `label` strings, which is an intentional trade-off for third-party plugin ergonomics vs. internal Principle V strictness. No new resource IDs are exposed by this feature; all IDs it handles (`storeId`, `AdminUser.id`) already flow through prefixed-ID Admin API responses.
- **VI. `docs/plans/` for Architectural Changes**: Pass — governed by the existing `docs/plans/6.0-admin-spa.md` (package split, extension points). This migration references that plan rather than creating a new one, since the architecture was already designed and shipped there.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/033-dashboard-core-framework/
├── plan.md              # This file
├── spec.md              # Feature specification (migrated)
└── tasks.md             # Migrated task checklist (all marked complete)
```

### Source Code (repository root)

```text
# packages/dashboard-core — registries, providers, plugin API (this feature's home)
packages/dashboard-core/src/
├── plugin.ts                          # defineDashboardPlugin facade — the single plugin entry point
├── client.ts                          # adminClient singleton (createAdminClient from @spree/admin-sdk)
├── lib/
│   ├── table-registry.ts              # defineTable/getTable + `tables` mutation proxy + pending-mutation queue
│   ├── nav-registry.ts                # sidebar nav registry (add/remove/update/insertBefore/insertAfter)
│   ├── settings-nav-registry.ts       # settings sub-shell registry (entries + groups)
│   ├── slot-registry.ts               # named extension-point registry (registerSlot/removeSlot/updateSlot)
│   ├── permissions.ts                 # Subject/Action constants mirroring CanCanCan subject/action names
│   ├── query-keys.ts                  # resourceKey/useResourceKey — canonical [resource, storeId, ...rest] shape
│   ├── query-client.ts                # shared TanStack QueryClient instance
│   ├── timestamp-columns.tsx          # ensureTimestampColumns — auto-appends created_at/updated_at columns
│   └── form-errors.ts                 # mapSpreeErrorsToForm — SpreeError -> react-hook-form field/root errors
├── providers/
│   ├── auth-provider.tsx              # AuthProvider/useAuth — JWT session lifecycle + silent refresh
│   ├── store-provider.tsx             # StoreProvider/useStore — current-store context (currencies/locales/tz)
│   └── permission-provider.tsx        # PermissionProvider/usePermissions — CanCanCan-mirrored rule evaluation
├── components/
│   ├── can.tsx                        # <Can I a> declarative permission gate (UX-only)
│   ├── slot.tsx                       # <Slot name context> — renders registered slot entries
│   └── page-tabs.tsx                  # shared tab-navigation UI primitive
└── hooks/
    └── use-resource-mutation.ts       # useResourceMutation — invalidation + success/error toast wrapper

# packages/dashboard — the primary consumer (routes register tables, mount providers, import plugins)
packages/dashboard/src/
├── tables/*.ts                        # per-resource defineTable(...) calls, side-effect imported by routes
└── routes/_authenticated/...          # routes rendering <ResourceTable>, <Slot>, useNavEntries, etc.
```

**Structure Decision**: Frontend-only, entirely within `packages/dashboard-core` (the framework) with `packages/dashboard` as the sole first-party consumer per the Module Impact table. No backend (`spree/core`, `spree/api`) changes — this feature predates and is independent of any specific Admin API endpoint beyond what already exists (`/api/v3/admin/me`, `/auth/*`, `/api/v3/admin/store`).

## Complexity Tracking

*No violations — table intentionally omitted.*
