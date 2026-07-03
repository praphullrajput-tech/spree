---

description: "Task list for Translations Admin — fully shipped; centralized page + bulk CSV + staleness pending"
---

# Tasks: Translations Admin

**Status**: Fully shipped (June 2026); Phase 2 (centralized page, CSV, staleness) PENDING

---

## Path Reference

| Code type | Path |
|-----------|------|
| Registry | `spree/core/lib/spree/translations.rb` |
| Concern | `spree/core/app/models/concerns/spree/translatable_resource.rb` |
| Batch domain | `spree/core/app/models/spree/translations/batch.rb` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Dashboard components | `packages/dashboard/src/components/spree/translations/` |
| Dashboard hooks | `packages/dashboard/src/hooks/use-translations.ts` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Registry + API ✅

- [x] T001 `spree/core/lib/spree/translations.rb` — stateless registry; `register(resource_type, fields:, children:)`; field discovery helpers; rich-text flag detection via `Spree::RichTextSanitizer`
- [x] T002 `spree/core/app/models/concerns/spree/translatable_resource.rb` — `upsert_translations({ locale → { field → value } })`; locale validation against store's available locales; field aliasing (`label` → `presentation`); `TRANSLATABLE_FIELDS`
- [x] T003 `spree/core/app/models/concerns/spree/presentation_translatable.rb` — shared `label`/`label=` alias for `OptionType` and `OptionValue`
- [x] T004 `spree/core/app/models/spree/translations/batch.rb` — resolves resource types; validates locales; upserts all records in one transaction; rolls back on any failure
- [x] T005 Register 7 resource types in `Spree::Translations`: Product, Taxon/Category, Taxonomy, Store, Policy, OptionType (with OptionValue children), OptionValue
- [x] T006 `spree/api/app/controllers/spree/api/v3/admin/translatable_resources_controller.rb` — `GET /api/v3/admin/translatable_resources`; returns registry metadata
- [x] T007 `spree/api/app/controllers/spree/api/v3/admin/translations_controller.rb` — `GET /api/v3/admin/:resource/:id/translations`; locale matrix + field metadata + nested children
- [x] T008 `spree/api/app/controllers/spree/api/v3/admin/translations/batches_controller.rb` — `POST /api/v3/admin/translations/batch`; delegates to `Spree::Translations::Batch`
- [x] T009 `spree/api/app/serializers/spree/api/v3/admin/resource_translations_serializer.rb` — matrix + field metadata + nested children + locale envelope
- [x] T010 `spree/api/app/serializers/concerns/spree/api/v3/admin/translatable.rb` — `?expand=translations` mixin for admin resource serializers
- [x] T011 Mount `:translatable` routes concern on products, categories, option_types in `spree/api/config/routes.rb`
- [x] T012 Register `translations_batch_service` dependency in `Spree::Dependencies`

**Checkpoint**: discovery + read + batch write API ✅

---

## Phase 2: SPA Editor ✅

- [x] T013 `packages/dashboard/src/hooks/use-translations.ts` — `useLocales()` + `useResourceTranslations(resourceType, id)` TanStack Query hooks
- [x] T014 `packages/dashboard/src/components/spree/translations/resource-translations-card.tsx` — coverage card ("X of Y locales translated"); opens dialog on click
- [x] T015 `packages/dashboard/src/components/spree/translations/resource-translations-dialog.tsx` — spreadsheet editor: locale dropdown; Original column (read-only); editable cells per locale; field-type-aware rendering (plain-text vs. rich-text); nested children rows with indentation; Save calls batch endpoint
- [x] T016 Embed `ResourceTranslationsCard` in `product-form.tsx`
- [x] T017 Embed `ResourceTranslationsCard` in `category-form.tsx`
- [x] T018 Wire translations via OptionType options route (`routes/_authenticated/$storeId/products/options.tsx`)
- [x] T019 Add i18n keys under `admin.translations.*` in all 6 locale files (ar, de, en, fr, pl, zh-CN)

**Checkpoint**: per-resource translations editor embedded on product/category/option-type pages ✅

---

## Phase 3: Tests ✅

- [x] T020 `spree/api/spec/controllers/.../translations_controller_spec.rb` — matrix read; nested children; category/taxon aliasing
- [x] T021 `spree/api/spec/controllers/.../translatable_resources_controller_spec.rb` — discovery endpoint
- [x] T022 `spree/api/spec/controllers/.../translations/batches_controller_spec.rb` — batch write; scopes; validation; rollback
- [x] T023 `spree/api/spec/integration/.../products/translations_spec.rb` — swagger-documented happy path
- [x] T024 `spree/api/spec/integration/.../translatable_resources_spec.rb`
- [x] T025 `spree/api/spec/integration/.../locales_spec.rb`
- [x] T026 `packages/dashboard/e2e/products-translations.spec.ts` — product name translation; rich-text focus handling (2 tests)
- [x] T027 `packages/dashboard/e2e/option-type-translations.spec.ts` — batch save of option type + nested option values (1 test)

**Checkpoint**: backend controller specs, integration specs, E2E tests ✅

---

## Phase 4: Centralized Translations Page (PENDING)

- [ ] T028 `packages/dashboard/src/routes/_authenticated/$storeId/translations/index.tsx` — overview grid of all resources × locales with coverage percentages
- [ ] T029 Navigation entry for centralized translations page
- [ ] T030 Coverage/staleness tracking column in the grid (requires staleness API from 6.0 plan)

## Phase 5: Bulk CSV (PENDING — 6.0)

- [ ] T031 `POST /api/v3/admin/exports` with `type: Spree::Exports::Translations` — generate CSV of all translations
- [ ] T032 `POST /api/v3/admin/imports/translations` — bulk CSV import
- [ ] T033 SPA upload UI for translation CSV import

## Phase 6: Staleness Tracking (PENDING — 6.0)

- [ ] T034 `translation_updated_at` timestamp per locale per resource — detect when source content was updated after translation
- [ ] T035 Serializer: `stale_locales` field listing locales whose translation predates last source content update
- [ ] T036 SPA: stale badge on coverage card and editor rows

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| Centralized translations page not built | Medium | T028–T030; plan drafted in `5.4-centralized-translations-admin.md` but not implemented |
| No bulk CSV import/export | Medium | T031–T033; deferred to 6.0 per `5.5-6.0-resource-translations-api.md` |
| No staleness tracking | Low | T034–T036; 6.0 scope |
| Only 7 resource types registered | Low | Shipping methods, promotions, blog posts etc. not translatable; add via registry |
