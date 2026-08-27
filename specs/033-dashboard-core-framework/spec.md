# Feature Specification: Dashboard Core Framework

**Feature Branch**: `033-dashboard-core-framework`

**Created**: 2026-08-24

**Status**: migrated

**Input**: Reverse-engineered from `packages/dashboard-core` as it exists on `main` (registries, providers, hooks, plugin facade) as part of the brownfield spec-kit migration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plugin author extends the admin SPA without forking it (Priority: P1)

A third-party or in-house plugin author wants to add a nav item, a settings page, a sidebar slot component, and a new table column to the Spree admin dashboard — without editing `packages/dashboard` source or maintaining a fork.

**Why this priority**: This is the framework's entire reason to exist — `defineDashboardPlugin` is the single documented entry point plugin authors use (`packages/dashboard-core/src/plugin.ts`).

**Independent Test**: Write a plugin entry module that calls `defineDashboardPlugin({ nav: [...], slots: {...}, tables: {...} })`, import it before the dashboard's first render, and confirm the nav item, slot component, and table column appear without any change to `packages/dashboard` route files.

**Acceptance Scenarios**:

1. **Given** a plugin entry module calling `defineDashboardPlugin({ nav: [{ key: 'wishlists', label: 'Wishlists', path: '/wishlists', position: 50 }] })`, **When** the dashboard boots and imports the plugin entry, **Then** the sidebar renders the new item at the correct position without a `packages/dashboard` code change.
2. **Given** a plugin registers a table column via `tables: { products: { add: [{ key: 'wishlist_count', ... }] } }` before the `products` table has been `defineTable`-d (its route hasn't loaded yet), **When** the `products` table route later calls `defineTable('products', ...)`, **Then** the queued mutation is replayed and the column appears.
3. **Given** two plugins each register a nav entry with the same `key`, **When** both entry modules are imported, **Then** the second registration throws a descriptive error while the first entry stays registered (registries don't roll back on a later duplicate).

---

### User Story 2 - Dashboard developer builds a data table with registry-driven columns, filters, and permissions (Priority: P2)

A developer building a new resource page in `packages/dashboard` needs sortable/filterable columns, store-scoped query keys, mutation toasts + invalidation, and permission-gated UI — all via `dashboard-core`'s shared infrastructure instead of hand-rolling each concern per page.

**Why this priority**: This is the day-to-day contract between `packages/dashboard-core` and `packages/dashboard` — every resource route depends on it (table registry, `useResourceKey`, `useResourceMutation`, `<Can>`).

**Independent Test**: Call `defineTable('widgets', { columns: [...] })`, render it through `<ResourceTable>`, and verify sorting/filtering/timestamp columns and a `<Can I="destroy" a="Spree::Widget">` gate behave correctly against a stub permission set.

**Acceptance Scenarios**:

1. **Given** a table defined via `defineTable('widgets', { columns: [{ key: 'name', label: 'Name', sortable: true }] })`, **When** `defineTable` runs, **Then** `created_at`/`updated_at` timestamp columns are auto-appended (`ensureTimestampColumns`) so every registered table gets consistent timestamp display without each caller declaring it.
2. **Given** a mutation built with `useResourceMutation({ mutationFn, invalidate: [['widgets']] })`, **When** the mutation succeeds, **Then** the given query keys are invalidated with the current `storeId` auto-injected at position 1, and a success toast fires.
3. **Given** a mutation fails with a 422 validation error, **When** `onError` runs, **Then** no error toast fires (the form is expected to render the error inline via `mapSpreeErrorsToForm`), but non-422 errors (network, 5xx) do toast.
4. **Given** a user without the `Spree::Widget` `destroy` permission, **When** `<Can I="destroy" a="Spree::Widget">` renders, **Then** the gated children are replaced by `fallback` (or nothing) — understanding this is UX-only, not a security boundary.

---

### User Story 3 - Dashboard developer wires auth, store, and permission context at the app root (Priority: P3)

A developer bootstrapping the SPA shell (or a standalone app reusing `dashboard-core`) needs JWT session lifecycle (login, refresh, logout), current-store context (currencies, locales, timezone), and CanCanCan-mirrored permission checks available via hooks/context to every route.

**Why this priority**: Foundational plumbing that every other page depends on, but it's set up once at the app shell rather than touched per-feature like US1/US2.

**Independent Test**: Mount `<AuthProvider>` → `<StoreProvider>` → `<PermissionProvider>`, log in with valid credentials, and confirm `useAuth().isAuthenticated` flips true, the access-token refresh timer is scheduled, and `usePermissions().permissions.can(...)` reflects the rules returned by `/api/v3/admin/me`.

**Acceptance Scenarios**:

1. **Given** a successful login, **When** `AuthProvider` applies the session, **Then** a refresh timer is scheduled ~30s before the JWT's 5-minute TTL and the client silently rotates the token in the background.
2. **Given** the admin API returns 401 mid-session, **When** `adminClient`'s `onUnauthorized` hook fires, **Then** `AuthProvider` attempts a token refresh and, on success, the original request can be retried; on failure, the session is cleared.
3. **Given** `PermissionProvider` has not yet loaded `/api/v3/admin/me`, **When** any component calls `usePermissions().permissions.can(...)`, **Then** it returns `false` for everything (deny-by-default `EMPTY_PERMISSIONS`) rather than throwing or hanging.

### Edge Cases

- A plugin calls `tables.products.addColumn(...)` for a table key that is never `defineTable`-d in this app build (feature not installed) — the mutation stays queued forever and never throws; this is intended, not a bug.
- Multiple registration failures in one `defineDashboardPlugin` call (e.g., a duplicate nav key AND a duplicate slot id) are all surfaced together via `AggregateError`, not just the first.
- A slow `StoreProvider` fetch resolves after the route already navigated to a different `storeId` — the stale response is dropped via a ref check, so it can't clobber the new store's state.
- Concurrent 401s during a burst of parallel requests must not double-rotate the refresh token — `AuthProvider` serializes concurrent refresh calls through a shared in-flight promise.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The framework MUST provide a single plugin entry point (`defineDashboardPlugin`) that registers nav entries, settings-nav entries/groups, slot entries, and table column mutations from one config object.
- **FR-002**: Every registry (nav, settings-nav, slot, table) MUST enforce uniqueness on its own key/id and throw a descriptive error on a duplicate registration, without preventing other entries in the same call from registering.
- **FR-003**: Table column mutations (`addColumn`/`removeColumn`/`updateColumn`) targeting a table that hasn't been `defineTable`-d yet MUST be queued and replayed when that table registers; mutations for tables that never register MUST remain harmlessly queued.
- **FR-004**: `defineTable` MUST auto-append `created_at`/`updated_at` timestamp columns to every table's column list so callers don't declare them individually.
- **FR-005**: All registries MUST expose a `useSyncExternalStore`-based subscription hook so components registered/mutated after first render still update consumers reactively.
- **FR-006**: `useResourceMutation` MUST auto-inject the current `storeId` into invalidated query keys at position 1, fire a success/error toast (each independently disableable), and MUST NOT toast on 422 validation errors.
- **FR-007**: `mapSpreeErrorsToForm` MUST route a Spree API validation error's top-level message to `formState.errors.root` and route only flat (non-dotted, non-`base`) `details` keys to their matching form field.
- **FR-008**: `AuthProvider` MUST maintain a JWT session lifecycle: login, invitation acceptance, logout, silent background refresh scheduled ahead of token expiry, and a hook for the admin SDK's `onUnauthorized` callback to trigger an on-demand refresh.
- **FR-009**: `PermissionProvider` MUST fetch CanCanCan-style permission rules from `/api/v3/admin/me` once authenticated, expose `can`/`cannot`/`isConditional` (last-matching-rule-wins, `manage`/`all` wildcards), and default to deny-all before rules load.
- **FR-010**: `StoreProvider` MUST expose the current store's currencies, locales, default locale/currency, and IANA timezone, and MUST discard responses from a stale `storeId` if the route has since navigated away.
- **FR-011**: The `<Can I a>` component MUST be a pure UX gate (not a security boundary) that renders `children` or `fallback` based on `usePermissions()`.
- **FR-012**: The `<Slot name context>` component MUST render all entries registered to `name`, sorted by `position`, filtered by each entry's `if` predicate, with ambient `{ permissions, store, user }` context merged in alongside slot-specific `context`.

### Key Entities

- **NavEntry / SettingsNavEntry**: Sidebar/settings-sidebar item — key, label (or i18n `labelKey`), path, optional icon/position/subject/children/group.
- **SlotEntry**: Named extension point registration — id, component, optional position and `if` visibility predicate.
- **TableDef / ColumnDef**: Registered table shape — key, columns (each with filter type discriminated union: string/boolean/number/date/currency/enum/resource/tags), sort/search config.
- **Permissions**: Derived-from-rules object exposing `can`/`cannot`/`isConditional`, built from the CanCanCan-mirrored `PermissionRule[]` returned by the Admin API.
- **DashboardPluginConfig**: The single object shape accepted by `defineDashboardPlugin` — `nav`, `settingsNavGroups`, `settingsNav`, `slots`, `tables`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | No | — |
| `spree/api` (Store/Admin API v3) | No | Framework consumes the existing `/api/v3/admin/me` permissions endpoint; no API change in this feature |
| `packages/dashboard` (admin SPA) | Yes (consumer) | Routes/app shell mount `AuthProvider`/`StoreProvider`/`PermissionProvider`, import plugin entry modules, and register built-in tables via `defineTable` |
| `packages/dashboard-ui` / `dashboard-core` | Yes (primary) | This feature IS `packages/dashboard-core`: registries (`table-registry.ts`, `nav-registry.ts`, `settings-nav-registry.ts`, `slot-registry.ts`), providers (`auth-provider.tsx`, `store-provider.tsx`, `permission-provider.tsx`), hooks (`use-resource-mutation.ts`), `lib/form-errors.ts`, `lib/query-keys.ts`, `client.ts`, `plugin.ts` |
| `packages/sdk` / `packages/admin-sdk` | No (consumed) | `@spree/admin-sdk` types (`AdminUser`, `PermissionRule`, `Store`, `SpreeError`) are consumed, not generated by this feature |
| `docs/plans/` | Yes (reference) | Governed by `docs/plans/6.0-admin-spa.md` ("Package Split" — the three extension points and `defineDashboardPlugin` contract); no new plan entry needed, this feature implements that plan's framework layer |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints**: None — this feature is pure frontend framework.
- **Serializer fields (read)**: N/A
- **Auth**: Consumes Admin JWT auth (`Authorization: Bearer <token>`) against `/api/v3/admin/me` for permission rules, and `adminClient.auth.{login,refresh,logout,acceptInvitation}` for session lifecycle — per `CLAUDE.md` → "API Authentication".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A plugin author can add a nav item, slot component, and table column to the dashboard using only `defineDashboardPlugin`, with zero edits to `packages/dashboard` route files.
- **SC-002**: Registries reject duplicate keys/ids with a specific, actionable error message identifying the offending key and the correct API to use instead (e.g., `update()` instead of `add()`).
- **SC-003**: A resource page built with `useResourceMutation` + `<ResourceTable>` requires no hand-written toast or query-invalidation boilerplate.
- **SC-004**: Session refresh happens transparently — a user active past the 5-minute JWT TTL never sees an unexpected logout under normal connectivity.
- **SC-005**: Permission checks via `<Can>` never throw when rules haven't loaded yet; they degrade to deny-all.

## Assumptions

- This is a reverse-engineered spec for an already-shipped framework (`packages/dashboard-core` on `main`); "requirements" describe existing, verified behavior rather than upcoming work.
- Per-record CanCanCan conditions are not evaluated client-side (`isConditional` only flags that a 403 is possible) — the backend remains the authorization source of truth per constitution Principle II framing for admin auth.
- The three extension points (table/nav/slot registries) and `defineDashboardPlugin` are considered the framework's stable public contract per `docs/plans/6.0-admin-spa.md`; internal registry implementation details (e.g., the `pending` queue Map) are not part of that contract and may change.
- Consumers are `packages/dashboard` (primary) and any future standalone app composing `dashboard-core` + `dashboard-ui` (e.g., a vendor panel), per `CLAUDE.md`'s package-split rationale.

## Migration Notes

This spec was reverse-engineered from the existing `packages/dashboard-core` implementation as part of the brownfield spec-kit adoption — no new code was written for this migration; the framework was already fully implemented and in production use by `packages/dashboard`.

**The three extension points + `defineDashboardPlugin` are the framework's public contract** (per `docs/plans/6.0-admin-spa.md` → "Package Split" and the module-level doc comment in `packages/dashboard-core/src/plugin.ts`):

1. **Table registry** (`lib/table-registry.ts`) — built-in tables register via `defineTable(key, def)`, called as a side effect when a route module loads (e.g. `import '@/tables/products'`). Plugin authors mutate an existing table via the `tables` proxy (`tables.products.addColumn(...)` / `removeColumn` / `updateColumn`). Because plugin entry modules run at boot — before any route has lazily loaded its table — mutations against a not-yet-registered table key are queued in a `pending` Map and replayed the moment `defineTable` runs for that key. This decouples plugin boot order from route-load order. `defineTable` also auto-appends `created_at`/`updated_at` columns via `ensureTimestampColumns`.

2. **Nav registry** (`lib/nav-registry.ts`) and its settings-sidebar sibling (`lib/settings-nav-registry.ts`) — flat list of `{ key, label, path, icon?, position?, subject?, children? }` entries, sorted by `position` (built-ins use round numbers like 100/200/300 to leave gaps for plugins), read reactively via `useSyncExternalStore`. `insertBefore`/`insertAfter` let a plugin anchor relative to a known built-in key instead of guessing a position number.

3. **Slot registry** (`lib/slot-registry.ts`) — named injection points (e.g. `product.form_sidebar`) that a route renders via `<Slot name="..." context={...} />` (`components/slot.tsx`). Registered components receive the slot's `context` merged with ambient `{ permissions, store, user }`, filtered by an optional `if` visibility predicate, sorted by `position`.

4. **`defineDashboardPlugin(config)`** (`plugin.ts`) — the single facade a plugin's entry module calls once at import time, fanning `nav`/`settingsNavGroups`/`settingsNav`/`slots`/`tables` config out to the four registries above. It collects (not short-circuits on) errors across every registry call and rethrows as one error or `AggregateError`, so a single duplicate key doesn't hide other problems in the same config.

Supporting framework pieces consumed by both plugin authors and `packages/dashboard` itself: `providers/{auth,store,permission}-provider.tsx` (session, current-store, and CanCanCan-mirrored permission context), `hooks/use-resource-mutation.ts` (store-scoped invalidation + toast), `lib/query-keys.ts` (`[resource, storeId, ...rest]` canonical key shape), `lib/form-errors.ts` (`mapSpreeErrorsToForm`), `client.ts` (the `adminClient` singleton), and `components/can.tsx` (declarative, UX-only permission gate).

**Gaps identified during migration**: `SlotAmbientContext` in `slot-registry.ts` is typed but the actual ambient values (`permissions`, `store`, `user`) are not yet wired through in `components/slot.tsx` — a comment there says "wired up properly once SlotProvider lands," meaning a dedicated `SlotProvider` is still pending. This is a known incompleteness in the current implementation, not something introduced by this migration.
