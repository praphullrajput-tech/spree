---

description: "Task list for the Translations / i18n (backend resource translations) feature — reverse-engineered from shipped code, all tasks completed"

---

# Tasks: Translations / i18n (Backend Resource Translations)

**Input**: Design documents from `specs/023-translations-i18n/` (spec.md, plan.md)

**Prerequisites**: plan.md, spec.md (both present)

**Tests**: Included — the shipped feature has RSpec + controller specs + Playwright e2e already in place.

**Organization**: Tasks are grouped by user story per spec.md. This is a **brownfield migration** — every task below reflects work already merged; all are marked complete.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core` and `spree/api` gem test suites pass with the `mobility` gem dependency present (`Gemfile`/gemspec)
- [x] T002 [P] Baseline backend: `cd spree/core && bundle exec rspec` passes including translation-concern specs
- [x] T003 [P] Baseline frontend: `pnpm typecheck && pnpm lint` passes at workspace root including `packages/dashboard` translations components

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core Mobility integration and registry that every user story depends on

- [x] T004 [spree/core] `Spree::TranslatableResource` concern (`spree/core/app/models/concerns/spree/translatable_resource.rb`) — `translatable_fields`, `translatable_field_aliases`, `public_translatable_fields`, `translatable_rich_text_fields`, `translation_table_alias`/`arel_table_alias`, `get_field_with_locale`, `upsert_translations`, `translatable_store`, `validate_translation_locales!`
- [x] T005 [spree/core] `Spree::TranslatableResourceScopes` concern (`translatable_resource_scopes.rb`) — `join_translation_table` Arel outer-join helper
- [x] T006 [spree/core] `Spree::TranslatableResourceSlug` concern (`translatable_resource_slug.rb`) — `localized_slugs_for_store`
- [x] T007 [spree/core] `Mobility::Plugins::StoreBasedFallbacks` (`lib/mobility/plugins/store_based_fallbacks.rb`) — `Concurrent::ThreadLocalVar`-backed dynamic fallback chain, registered as `:store_based_fallbacks` Mobility plugin
- [x] T008 [spree/core] Registry: `Rails.application.config.spree.translatable_resources` in `lib/spree/core/engine.rb` — `Product`, `OptionType`, `OptionValue`, `Taxon`, `Taxonomy`, `Store`, `Policy`
- [x] T009 [spree/core] Per-model `TRANSLATABLE_FIELDS`/`RICH_TEXT_TRANSLATABLE_FIELDS` + `translates(...)` declarations on `Product`, `Taxon`, `Taxonomy`, `OptionType`/`OptionValue` (via `Spree::PresentationTranslatable`), `Store`, `Policy`
- [x] T010 [spree/api] `Spree::Api::V3::LocaleAndCurrency` concern — resolves `x-spree-locale` → `Mobility.locale`/`I18n.locale`, validates against `supported_locale?` (pre-existing infra this feature builds on, unchanged here)

**Checkpoint**: Foundation ready — read resolution + write contract exist independent of any API surface

---

## Phase 3: User Story 1 - Storefront and admin reads resolve to the request locale (Priority: P1) 🎯 MVP

**Goal**: Reads transparently resolve to the active locale with store-configured fallback

**Independent Test**: Set `x-spree-locale`, confirm plain attribute reads return localized values with fallback when a translation is missing

### Tests for User Story 1

- [x] T011 [P] [US1] RSpec spec for `Mobility::Plugins::StoreBasedFallbacks` fallback-chain resolution
- [x] T012 [P] [US1] RSpec spec for `Spree::Api::V3::LocaleAndCurrency` locale resolution/validation (pre-existing)

### Implementation for User Story 1

- [x] T013 [US1] Wire `translates(*TRANSLATABLE_FIELDS, column_fallback: !Spree.always_use_translations?)` on every registered model (T009)
- [x] T014 [US1] Default scope `i18n` applied via `included do; extend Mobility; default_scope { i18n }; end` in `TranslatableResource`

**Checkpoint**: Locale-aware reads with fallback work independently of any write/admin surface

---

## Phase 4: User Story 2 - Admin edits translations for one resource across all locales (Priority: P1)

**Goal**: Atomic, registry-driven write path for one or many records at once

**Independent Test**: `GET .../translations` then `POST /api/v3/admin/translations/batch`, confirm round-trip and rollback-on-failure semantics

### Tests for User Story 2

- [x] T015 [P] [US2] Controller spec `spree/api/spec/controllers/spree/api/v3/admin/translations/batches_controller_spec.rb` — happy path, omit-to-leave-alone, unsupported-locale 422, scope enforcement, all-or-nothing rollback
- [x] T016 [P] [US2] Playwright e2e `packages/dashboard/e2e/option-type-translations.spec.ts` — multi-record (option type + values) save via the dialog
- [x] T017 [P] [US2] Playwright e2e `packages/dashboard/e2e/products-translations.spec.ts` — single-resource save via the dialog

### Implementation for User Story 2

- [x] T018 [P] [US2] `upsert_translations`/`destroy_locale_translation` on `TranslatableResource` (T004) — omit-to-leave-alone, `""` clears, `nil` deletes
- [x] T019 [US2] `Spree::Translations::Batch` (`spree/core/lib/spree/translations.rb`) — multi-entry orchestration, `EntryError` with per-entry index (depends on T018)
- [x] T020 [US2] `Spree::Api::V3::Admin::Translations::BatchesController` (`spree/api/app/controllers/spree/api/v3/admin/translations/batches_controller.rb`) — params parsing, per-resource-type scope enforcement (`require_batch_scopes!`), per-record `authorize!(:update, record)`, error rendering
- [x] T021 [US2] Route `post 'translations/batch', to: 'translations/batches#create'` in `spree/api/config/routes.rb`
- [x] T022 [US2] `ResourceTranslationsDialog` (`packages/dashboard/src/components/spree/translations/resource-translations-dialog.tsx`) — spreadsheet grid, locale switcher, cross-locale edit accumulation, submit via batch endpoint
- [x] T023 [US2] `useResourceTranslations` hook (`packages/dashboard/src/hooks/use-translations.ts`) with resource-token → SDK-accessor map

**Checkpoint**: User Story 2 fully functional — an admin can edit and atomically save translations independently of discovery UI

---

## Phase 5: User Story 3 - Admin discovers translatable fields/locales without per-model code (Priority: P2)

**Goal**: Registry-driven discovery so new translatable models need no new controller/route/serializer

**Independent Test**: `GET /api/v3/admin/translatable_resources` and `GET /api/v3/admin/locales` return complete, correctly-typed data

### Tests for User Story 3

- [x] T024 [P] [US3] Controller spec `spree/api/spec/controllers/spree/api/v3/admin/locales_controller_spec.rb`
- [x] T025 [P] [US3] RSpec spec for `Spree::Translations.registry`/`.fields_for` field-type inference (`html`/`slug`/`string`)

### Implementation for User Story 3

- [x] T026 [P] [US3] `Spree::Translations` module (`spree/core/lib/spree/translations.rb`) — `matrix_for`, `fields_for`, `registry`, field-type inference from `RICH_TEXT_TRANSLATABLE_FIELDS` / slug-like field names
- [x] T027 [US3] `Spree::Api::V3::Admin::TranslationsController` (nested read, `spree/api/app/controllers/spree/api/v3/admin/translations_controller.rb`) — `set_parent`/`ensure_translatable!`/`parent_lookup` registry-driven resolution, ancestor-name-based subclass matching (`Category < Taxon`)
- [x] T028 [US3] `:translatable` route concern + mount on `products`, `categories`, `option_types` in `spree/api/config/routes.rb`
- [x] T029 [US3] `Spree::Api::V3::Admin::Translatable` serializer concern (`spree/api/app/serializers/concerns/spree/api/v3/admin/translatable.rb`) — `?expand=translations` attribute, admin-only
- [x] T030 [US3] `Admin::TranslatableResourcesController` (registry discovery endpoint) + `Admin::LocalesController`/`Store::LocalesController` (locale discovery)
- [x] T031 [US3] `ResourceTranslationsCard` launcher (`packages/dashboard/src/components/spree/translations/resource-translations-card.tsx`) — translated-count summary, opens dialog

**Checkpoint**: Discovery endpoints let any client (dashboard or third-party) render generic translation UI

---

## Phase 6: User Story 4 - Admin bulk-translates products via CSV (Priority: P3)

**Goal**: Product-scoped bulk translation export (import path already covered by existing `Spree::Imports::RowProcessors::ProductTranslation`)

**Independent Test**: Run the export for a store with 2+ supported locales, confirm one CSV row per `(product, locale)`

### Tests for User Story 4

- [x] T032 [P] [US4] Spec coverage for `Spree::Exports::ProductTranslations` (`scope` excludes archived by default, `multi_line_csv?`, header set)

### Implementation for User Story 4

- [x] T033 [US4] `Spree::Exports::ProductTranslations` (`spree/core/app/models/spree/exports/product_translations.rb`) — locale-aware CSV generation via `product.to_translation_csv(store, locales)`
- [x] T034 [US4] `Spree::CSV::ProductTranslationPresenter` — `CSV_HEADERS`, `TRANSLATABLE_FIELDS`
- [x] T035 [US4] `Spree::Imports::RowProcessors::ProductTranslation` — the corresponding import-side row processor (pre-existing counterpart)

**Checkpoint**: Bulk product translation via CSV works independently of the per-resource API (product-only, as documented in spec.md Assumptions)

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T036 [P] `docs/plans/5.5-6.0-resource-translations-api.md` exists and documents Phase 1 (shipped) vs. Phase 2/3 (pending) — cross-referenced in `specs/023-translations-i18n/spec.md` → Migration Notes
- [x] T037 Full backend suite: `cd spree/core && bundle exec rspec` and `cd spree/api && bundle exec rspec` pass
- [x] T038 Full frontend suite: `pnpm typecheck && pnpm lint && pnpm test` at workspace root
- [x] T039 [P] `packages/dashboard && pnpm test:e2e` covers `option-type-translations.spec.ts` and `products-translations.spec.ts`
- [x] T040 Verify dashboard translation-editor UI copy (dialog title, button labels) exists under `packages/dashboard/src/locales/en.json` (`admin.translations.*`) across all locale files

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: the Mobility integration and registry (T004–T010) block every user story.
- **User Story 1 (Phase 3)**: depends only on Foundational — reads work with zero API/dashboard surface.
- **User Story 2 (Phase 4)**: depends on Foundational (`upsert_translations`); independent of US3's discovery endpoints (the dialog already knows its resource type from its launch context) but in practice shipped alongside US3's discovery for the generic field-type rendering.
- **User Story 3 (Phase 5)**: depends on Foundational (`Spree::Translations` reads the same registry as T008); the nested read controller (T027) and batch write controller (T020) are independent siblings — either could ship first.
- **User Story 4 (Phase 6)**: depends only on Foundational (registry + per-model `TRANSLATABLE_FIELDS`); independent of US2/US3's API surface — CSV export reads the model directly.
- **Polish (Phase 7)**: depends on all prior phases.

## Notes

- This tasks.md documents **already-shipped** work as part of the spec-kit brownfield migration (`/speckit.brownfield.migrate`) — no new implementation is expected from this file. Future incremental work on this feature (Phase 2/3 of the underlying plan) should be tracked as new tasks appended via `/speckit.converge`, not by un-checking these.
- Pending Phase 2/3 items (staleness, coverage grid, generalized CSV, centralized SPA page, metafield fold-in) are intentionally **not** listed as tasks here — they are unbuilt and belong to `docs/plans/5.5-6.0-resource-translations-api.md`'s own migration path, referenced from `spec.md` → Migration Notes.
