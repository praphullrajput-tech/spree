# Tasks: Settings Pages (dashboard SPA)

**Input**: Design documents from `/specs/037-settings-pages/`

**Prerequisites**: plan.md, spec.md

**Tests**: Reverse-engineered feature — tasks below record what already exists in the codebase; all are marked complete.

**Organization**: Tasks are grouped by user story (settings page) to match spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent file, no dependency on other tasks
- **[Story]**: Which settings page this task belongs to

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Dev stack confirmed: `pnpm server:dev` (backend) + `cd packages/dashboard && pnpm dev` (frontend) serve the settings routes
- [x] T002 [P] Baseline frontend: `pnpm typecheck && pnpm lint` passes at workspace root
- [x] T003 [P] `@spree/admin-sdk` generated types available for `Store`, `AdminUser`, `Invitation`, `Role`, `WebhookEndpoint`, `WebhookEndpointCreateParams`, `PreferenceField`

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 [packages/dashboard] `routes/_authenticated/$storeId/settings/index.tsx` redirects to `/settings/store`
- [x] T005 [packages/dashboard-core] `PageHeader`, `mapSpreeErrorsToForm`, `useAuth`, `useStore`, `useSwitchAdminLocale`, `reconcileStoreDefaultLocale` available for settings forms
- [x] T006 [packages/dashboard-core] Shared `PreferencesForm` component (`packages/dashboard-core/src/components/preferences-form.tsx`) built for any `PreferenceField[]`-schema-driven resource, with `defaultPreferences()` helper skipping `password` fields
- [x] T007 [packages/dashboard-core] `MarketCombobox` and `CountryCombobox` (`packages/dashboard-core/src/components/{market,country}-combobox.tsx`) built for market/country selection
- [x] T008 [packages/dashboard] i18next keys present in `packages/dashboard/src/locales/en.json` and `packages/dashboard-core/src/locales/en.json` for all settings pages, mirrored across all locale files

**Checkpoint**: Foundation in place — all settings pages below build on it.

---

## Phase 3: User Story 1 - Store Details (Priority: P1) 🎯

- [x] T009 [US1] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/store.tsx`
- [x] T010 [US1] Hook `packages/dashboard/src/hooks/use-store-settings.ts` (`useStoreSettings`, `useUpdateStoreSettings`)
- [x] T011 [US1] Schema `packages/dashboard/src/schemas/store.ts` (`storeSettingsFormSchema`, `STOREFRONT_ACCESS_LEVELS`, `UNIT_SYSTEMS`, `WEIGHT_UNITS`)
- [x] T012 [US1] Locale reconciliation wired via `useSwitchAdminLocale` / `reconcileStoreDefaultLocale`

**Checkpoint**: Store Details page fully functional.

---

## Phase 4: User Story 2 - Staff (Priority: P1)

- [x] T013 [US2] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/staff.tsx` (list, invite, edit, roles)
- [x] T014 [US2] Hook `packages/dashboard/src/hooks/use-staff.ts`
- [x] T015 [US2] Invitation pending-state UI via `RelativeTime`

**Checkpoint**: Staff page fully functional.

---

## Phase 5: User Story 3 - Payment Methods (Priority: P1)

- [x] T016 [US3] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/payment-methods.tsx`
- [x] T017 [US3] Hook `packages/dashboard/src/hooks/use-payment-methods.ts`
- [x] T018 [US3] Form reuses shared `PreferencesForm` for provider-specific config

**Checkpoint**: Payment Methods page fully functional.

---

## Phase 6: User Story 4 - Markets (Priority: P2)

- [x] T019 [US4] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/markets.tsx`
- [x] T020 [US4] Hook `packages/dashboard/src/hooks/use-markets.ts`
- [x] T021 [US4] Uses `MarketCombobox` / `CountryCombobox`

---

## Phase 7: User Story 5 - Channels (Priority: P2)

- [x] T022 [US5] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/channels.tsx`
- [x] T023 [US5] Hook `packages/dashboard/src/hooks/use-channels.ts`

---

## Phase 8: User Story 6 - Stock Locations (Priority: P2)

- [x] T024 [US6] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/stock-locations.tsx`
- [x] T025 [US6] Hook `packages/dashboard/src/hooks/use-stock-locations.ts`

---

## Phase 9: User Story 7 - Tax Categories (Priority: P2)

- [x] T026 [US7] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/tax-categories.tsx`
- [x] T027 [US7] Hook `packages/dashboard/src/hooks/use-tax-categories.ts`

---

## Phase 10: User Story 8 - Custom Field Definitions (Priority: P3)

- [x] T028 [US8] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/custom-field-definitions.tsx`

---

## Phase 11: User Story 9 - API Keys (Priority: P3)

- [x] T029 [US9] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/api-keys.tsx`
- [x] T030 [US9] Hook `packages/dashboard/src/hooks/use-api-keys.ts`

---

## Phase 12: User Story 10 - Webhooks (Priority: P3)

- [x] T031 [US10] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/webhooks/index.tsx` (list/create)
- [x] T032 [US10] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/webhooks/$webhookEndpointId.tsx` (edit)
- [x] T033 [US10] Hook `packages/dashboard/src/hooks/use-webhook-endpoints.ts`

---

## Phase 13: User Story 11 - Allowed Origins (Priority: P3)

- [x] T034 [US11] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/allowed-origins.tsx`
- [x] T035 [US11] Hook `packages/dashboard/src/hooks/use-allowed-origins.ts`

---

## Phase 14: User Story 12 - Emails (Priority: P3)

- [x] T036 [US12] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/emails.tsx`

---

## Phase 15: User Story 13 - Profile (Priority: P3)

- [x] T037 [US13] Route `packages/dashboard/src/routes/_authenticated/$storeId/settings/profile.tsx`
- [x] T038 [US13] Hook `packages/dashboard/src/hooks/use-profile.ts`

---

## Phase 16: Polish & Cross-Cutting Concerns

- [x] T039 [P] All settings pages use `mapSpreeErrorsToForm` for 422 handling
- [x] T040 [P] All settings pages use i18next keys (no hardcoded strings) across `packages/dashboard/src/locales/` and `packages/dashboard-core/src/locales/`
- [x] T041 Full frontend suite: `pnpm typecheck && pnpm lint && pnpm test` passes
- [x] T042 Migration Notes captured in `spec.md` documenting legacy-admin-only gaps (checkout messaging, shipping methods, zones, policies, returns configuration, marketplace/vendor settings)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → all user story phases (3–15), which were built independently of each other → **Polish (Phase 16)**.
- All phases are already complete (brownfield reverse-engineering); this ordering reflects logical dependency, not remaining work.

## Notes

- This tasks.md reflects a **shipped** feature. No `[ ]` (open) tasks remain.
- Gaps identified during reverse-engineering (legacy-admin-only settings areas with no SPA route) are tracked in spec.md's Migration Notes, not as open tasks here — closing them is future work outside this spec's scope.
