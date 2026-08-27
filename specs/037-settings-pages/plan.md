# Implementation Plan: Settings Pages (dashboard SPA)

**Branch**: `037-settings-pages` | **Date**: 2026-08-24 | **Spec**: `specs/037-settings-pages/spec.md`

**Input**: Feature specification from `/specs/037-settings-pages/spec.md`

**Note**: This is a reverse-engineered plan for an already-shipped feature (brownfield migration), not a forward design document.

## Summary

The dashboard SPA's settings section is a set of 13 independently-routable pages under `/$storeId/settings/*` covering store configuration, staff/roles, payment methods, markets, channels, stock locations, tax categories, custom field definitions, API keys, webhooks, allowed origins (CORS), emails, and the logged-in admin's own profile. Each page follows the same pattern: a TanStack Router file route, a `use-<resource>.ts` hook wrapping `@spree/admin-sdk` calls, a Zod schema (where forms exist) in `src/schemas/`, and shadcn/ui + `@spree/dashboard-ui` primitives for layout/forms/tables. Provider-configurable resources (payment methods) reuse the shared `<PreferencesForm>` from `dashboard-core`.

## Technical Context

**Language/Version**: TypeScript (React SPA, frontend-only — no backend changes in scope)

**Primary Dependencies**: TanStack Router (file-based routes) + TanStack Query (via resource hooks), React Hook Form + Zod (`zodResolver`), `@spree/dashboard-ui` (Card, Field, Sheet, Dialog, Table, Select primitives), `@spree/dashboard-core` (`PageHeader`, `mapSpreeErrorsToForm`, `useAuth`, `useStore`, `useSwitchAdminLocale`, `PreferencesForm`, `MarketCombobox`, `CountryCombobox`, `ResourceTable`, `Can`/`Subject`/`usePermissions`), `@spree/admin-sdk` (typed Admin API client + generated types), `react-i18next`, `sonner` (toasts)

**Storage**: N/A directly — all persistence is via the existing Admin API v3 (backed by PostgreSQL/SQLite through `spree/core`/`spree/api`, unchanged by this feature)

**Testing**: Vitest for hook/schema unit tests (colocated `*.test.ts` under `packages/dashboard/src`), Playwright e2e under `packages/dashboard/e2e` for full user flows (existing pattern: `e2e/option-types.spec.ts` is the closest analogue for a settings-style CRUD sheet flow)

**Target Platform**: React SPA (`packages/dashboard`) served standalone, proxying to the Rails Admin API v3

**Project Type**: Monorepo — TypeScript packages only (`packages/dashboard`, `packages/dashboard-core`); no `spree/*` Ruby gem changes

**Performance Goals**: Standard SPA responsiveness — settings pages are low-traffic, admin-only; no special performance targets beyond typical TanStack Query cache behavior

**Constraints**: Must not call `adminClient` directly from route components (only via hooks); provider preference forms must not autofill masked `password`-type fields; reorderable lists must use drag-and-drop, not numeric position inputs

**Scale/Scope**: 13 settings routes, 10 dedicated resource hooks, 2 shared cross-cutting components (`PreferencesForm`, comboboxes)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches only `packages/dashboard` (routes/hooks/schemas) and `packages/dashboard-core` (shared `PreferencesForm`, comboboxes, registries/providers already in place). No `spree/core`/`spree/api` changes in this reverse-engineered scope — data access goes exclusively through `@spree/admin-sdk`. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: Confirmed — every route's hook (`use-store-settings`, `use-staff`, `use-payment-methods`, `use-markets`, `use-channels`, `use-stock-locations`, `use-tax-categories`, `use-api-keys`, `use-webhook-endpoints`, `use-allowed-origins`, `use-profile`) wraps `@spree/admin-sdk` calls; none reach into Rails views or server HTML. **Pass.**
- **III. Read/Write Field Symmetry**: N/A for this plan — no serializer changes are in scope; the SPA consumes existing Admin API field names as-is (e.g. `PreferenceField.key` round-trips unchanged through `PreferencesForm`). **Pass (N/A).**
- **IV. Test-Backed**: Vitest for schema/hook logic, Playwright for the CRUD flows a user actually drives (staff invite, payment method create, market create) — mirrors existing `e2e/option-types.spec.ts` conventions (UI-only assertions, no `waitForResponse`). **Pass.**
- **V. Translations and Prefixed IDs**: All labels/placeholders/toasts on these pages route through i18next (`packages/dashboard/src/locales/en.json`, cross-cutting keys in `packages/dashboard-core/src/locales/en.json`); Admin API resources (`AdminUser`, `WebhookEndpoint`, etc.) use prefixed IDs end-to-end. **Pass.**
- **VI. `docs/plans/` for Architectural Changes**: This feature doesn't introduce new architecture — it's already covered by existing plans (`5.5-admin-api-key-scopes.md` for API keys, `5.4-6.0-custom-fields-rename.md` for custom field definitions, `6.0-channels-catalogs-b2b.md`/`6.0-order-routing.md` for channels). No new `docs/plans/` entry required. **Pass (N/A — no new architecture).**

No violations; Complexity Tracking table omitted.

## Project Structure

### Documentation (this feature)

```text
specs/037-settings-pages/
├── plan.md              # This file
├── spec.md              # Reverse-engineered spec (already created)
└── tasks.md             # Reverse-engineered task checklist (already created)
```

### Source Code (repository root)

```text
# packages/dashboard — admin SPA routes/hooks/schemas
packages/dashboard/src/
├── routes/_authenticated/$storeId/settings/
│   ├── index.tsx                       # redirects to /settings/store
│   ├── store.tsx                       # Store Details (US1)
│   ├── staff.tsx                       # Staff / Users / Roles / Invitations (US2)
│   ├── payment-methods.tsx             # Payment Methods (US3)
│   ├── markets.tsx                     # Markets (US4)
│   ├── channels.tsx                    # Channels (US5)
│   ├── stock-locations.tsx             # Stock Locations (US6)
│   ├── tax-categories.tsx              # Tax Categories (US7)
│   ├── custom-field-definitions.tsx    # Custom Field Definitions / Metafields (US8)
│   ├── api-keys.tsx                    # API Keys (US9)
│   ├── webhooks/index.tsx              # Webhooks list/create (US10)
│   ├── webhooks/$webhookEndpointId.tsx # Webhook edit (US10)
│   ├── allowed-origins.tsx             # Allowed Origins / CORS (US11)
│   ├── emails.tsx                      # Emails (US12)
│   └── profile.tsx                     # Profile (US13)
├── hooks/
│   ├── use-store-settings.ts
│   ├── use-staff.ts
│   ├── use-payment-methods.ts
│   ├── use-markets.ts
│   ├── use-channels.ts
│   ├── use-stock-locations.ts
│   ├── use-tax-categories.ts
│   ├── use-api-keys.ts
│   ├── use-webhook-endpoints.ts
│   ├── use-allowed-origins.ts
│   └── use-profile.ts
├── schemas/
│   └── store.ts                        # storeSettingsFormSchema, STOREFRONT_ACCESS_LEVELS, UNIT_SYSTEMS, WEIGHT_UNITS
├── locales/en.json                     # settings.* i18n keys (+ all other locale files)
└── e2e/                                 # settings flow coverage (extend as needed)

# packages/dashboard-core — shared cross-cutting components consumed by settings pages
packages/dashboard-core/src/components/
├── preferences-form.tsx    # generic PreferenceField[]-driven form (payment methods, etc.)
├── market-combobox.tsx     # used by markets.tsx
├── country-combobox.tsx    # used by markets.tsx and store.tsx-adjacent address flows
├── resource-combobox.tsx   # generic searchable combobox base
└── tag-combobox.tsx        # generic tag input base

# packages/admin-sdk — consumed types (generated, not hand-written for this feature)
packages/admin-sdk/src/types/generated/   # Store, AdminUser, Invitation, Role, WebhookEndpoint, PreferenceField, etc.
```

**Structure Decision**: Frontend-only, entirely within `packages/dashboard` (routes/hooks/schemas) and `packages/dashboard-core` (shared `PreferencesForm` + comboboxes). No `spree/core` or `spree/api` changes — all 13 pages consume pre-existing Admin API v3 endpoints via `@spree/admin-sdk`.

## Complexity Tracking

*No constitution violations — table omitted.*
