# Implementation Plan: Translations Admin

**Branch**: `main` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped (merged June 26–27, 2026)

---

## Summary

A registry-driven translation system. `Spree::Translations` holds a static map of resource types to their translatable fields. Three Admin API controllers expose discovery, per-resource read, and atomic batch write. The SPA embeds a spreadsheet editor on each resource detail page rather than a centralized page.

---

## Key Decisions

1. **Registry-driven, not convention-driven.** Resource types and their translatable fields are explicitly registered in `Spree::Translations` rather than auto-discovered via `include Mobility`. This makes the public API surface deliberate — adding a model to Mobility doesn't automatically expose it to the translation API without a registry entry.

2. **Atomic batch write, not per-field PATCH.** `POST /api/v3/admin/translations/batch` upserts all fields and locales for all resources in one transaction (`Spree::Translations::Batch`). The SPA saves the entire dialog in one round-trip. Per-field auto-save was rejected to avoid partial-write states when the user edits multiple locales before saving.

3. **`?expand=translations` rather than a separate GET.** Embedding translations inline on the resource request (opt-in via `?expand=translations`) saves a round-trip when the SPA opens the editor. The per-resource `GET /:id/translations` endpoint exists for explicit reads (integrations, CLI).

4. **Nested children in same matrix.** OptionValues are returned as indented rows under their parent OptionType in the same spreadsheet payload rather than requiring a separate request. The `children:` registry key declares this nesting. The batch endpoint accepts mixed parent+children in the same payload.

5. **Field aliasing resolved at concern level.** `OptionType#label` and `OptionValue#label` are aliases for the underlying `presentation` column. The `TranslatableResource` concern resolves aliases before calling Mobility — the API surface uses `label` consistently; the storage detail is hidden.

6. **Rich-text field detection in backend.** `Spree::RichTextSanitizer` is used to detect rich-text fields at registration time so the serializer can include a `rich_text: true` flag in the metadata response. The SPA uses this to decide which editor widget to render — no frontend heuristic needed.

7. **Per-resource editor, not centralized page.** The translations dialog is embedded in product-form, category-form, etc. rather than a dedicated `/translations` route. This matches how merchants actually work (translate a specific product, not a spreadsheet of all products). A centralized page is drafted (`5.4-centralized-translations-admin.md`) but not built.

---

## Constitution Check

- [x] **API-First**: Controllers before SPA
- [x] **Plan Conflicts**: `5.4-store-api-naming-standardization.md` `5.4-metafield-translations.md`, `5.4-centralized-translations-admin.md`, `5.5-6.0-resource-translations-api.md` — consistent with Phase 1 scope
- [x] **Namespace**: `Spree::Translations`, `Spree::TranslatableResource`
- [x] **i18n**: All UI strings in all locale files

---

## Project Structure

```text
spree/core/lib/spree/translations.rb                                              ← registry, field discovery
spree/core/app/models/concerns/spree/translatable_resource.rb                    ← upsert_translations, TRANSLATABLE_FIELDS
spree/core/app/models/concerns/spree/presentation_translatable.rb                ← OptionType/OptionValue label alias
spree/core/app/models/spree/translations/batch.rb                                ← atomic batch domain logic
spree/api/app/controllers/spree/api/v3/admin/translations_controller.rb          ← GET /:resource/:id/translations
spree/api/app/controllers/spree/api/v3/admin/translatable_resources_controller.rb ← GET /translatable_resources
spree/api/app/controllers/spree/api/v3/admin/translations/batches_controller.rb  ← POST /translations/batch
spree/api/app/serializers/spree/api/v3/admin/resource_translations_serializer.rb
spree/api/app/serializers/concerns/spree/api/v3/admin/translatable.rb            ← ?expand=translations mixin
packages/dashboard/src/components/spree/translations/resource-translations-dialog.tsx   ← 413-line spreadsheet editor
packages/dashboard/src/components/spree/translations/resource-translations-card.tsx     ← coverage launcher
packages/dashboard/src/hooks/use-translations.ts                                  ← useLocales, useResourceTranslations
packages/dashboard/e2e/products-translations.spec.ts
packages/dashboard/e2e/option-type-translations.spec.ts
```
