---
status: migrated
---

# Spec: Translations Admin

**Feature**: Per-resource translation management for all translatable resources via a registry-driven Admin API and SPA spreadsheet editor

---

## Overview

Spree supports translating content fields (name, description, slug, etc.) across multiple locales using the Mobility gem. The Translations Admin feature exposes this via a discovery API, per-resource read endpoint, and atomic batch write endpoint. The Admin SPA provides a spreadsheet-style editor embedded in each resource's detail page, plus a coverage card launcher.

---

## User Scenarios

### US1 — Admin translates a product's name into French
Given a product detail page with a "Translations" card showing "1 of 3 locales translated",
When the admin clicks the card and opens the editor,
Then a spreadsheet shows all translatable fields as rows and locales as columns; the admin edits the `name` cell under `fr`, clicks Save; `POST /api/v3/admin/translations/batch` is called atomically.

### US2 — Admin translates option type and its values together
Given an OptionType edit sheet with nested OptionValues,
When the admin opens the translations dialog,
Then parent fields and indented child rows (each OptionValue's label) are shown in the same spreadsheet; saving persists all in one batch request.

### US3 — Admin checks which resources support translations
Given an integration that needs to enumerate translatable resource types,
When `GET /api/v3/admin/translatable_resources` is called,
Then the response lists all registered resource types with their translatable field names.

### US4 — Admin edits a rich-text description translation
Given a product with a rich-text `description` field,
When the admin edits the description cell in the translations editor,
Then a rich-text editor is rendered (not a plain-text input); the saved value is HTML.

### US5 — Admin reads translations for a product
Given a product with existing French and German translations,
When `GET /api/v3/admin/products/:id/translations` is called,
Then the response returns a locale-keyed matrix: `{ fr: { name: "...", description: "..." }, de: { name: "..." } }` with field metadata (translatable fields list, types).

---

## Functional Requirements

### FR-001 — TranslatableResource concern
`Spree::TranslatableResource` concern included in translatable models. Provides `upsert_translations({ locale => { field => value } })` — validates locales against store's available locales, resolves field aliases, and persists via Mobility. Exposes `TRANSLATABLE_FIELDS` constant. Rich-text fields detected via `Spree::RichTextSanitizer`.

### FR-002 — Translation registry
`Spree::Translations` module (stateless): `register(resource_type, fields:, children:)`, `registry` hash, field discovery. Resources registered: `Spree::Product` (name, description, slug, meta_description, meta_title; rich-text: description), `Spree::Taxon`/`Category` (name, pretty_name, description, permalink; rich-text: description), `Spree::Taxonomy` (name), `Spree::Store` (name, meta_description, meta_keywords, seo_title, customer_support_email, address, contact_phone), `Spree::Policy` (name, body; rich-text: body), `Spree::OptionType` (label/presentation; children: OptionValue), `Spree::OptionValue` (label/presentation).

### FR-003 — Discovery endpoint
`GET /api/v3/admin/translatable_resources` → lists all registered resource types with translatable field names. No auth scope required beyond being an admin.

### FR-004 — Per-resource translation read
`GET /api/v3/admin/:resource/:id/translations` — returns translation matrix `{ locale → { field → value } }` plus field metadata (field list, types, rich-text flags). Supports nested children (e.g., OptionValues nested under OptionType). Serialized by `ResourceTranslationsSerializer`. Mounted via `:translatable` routes concern on products, categories, option_types.

### FR-005 — Batch write endpoint
`POST /api/v3/admin/translations/batch` — atomic batch upsert across multiple resource types and locales in a single transaction (`Spree::Translations::Batch`). Rolls back entirely on any failure. Body: `{ resources: [{ type, id, translations: { locale → { field → value } } }] }`. Auth: JWT admin or secret key with matching `write_*` scope.

### FR-006 — `?expand=translations` opt-in
Admin resource serializers include a `Spree::Api::V3::Admin::Translatable` mixin. Passing `?expand=translations` on any resource GET appends the full translation matrix inline. Used by the SPA to load resource + translations in one request.

### FR-007 — Admin SPA editor
`ResourceTranslationsDialog` (413-line component): locale dropdown selector, Original column (read-only), editable cells per locale, field-type-aware rendering (plain-text vs. rich-text), nested children rows with indentation (e.g., OptionValues under OptionType). Save calls batch endpoint. `ResourceTranslationsCard` (67-line launcher): shows coverage "X of Y locales translated", opens dialog on click. Both embedded in product-form, category-form, and options route.

### FR-008 — Dashboard hooks
`useLocales()` — fetches store's available locales. `useResourceTranslations(resourceType, id)` — dispatches through `adminClient.products.translations`, `.categories.translations`, `.optionTypes.translations`.

### FR-009 — i18n
All UI strings under `admin.translations.*` keys in all 6 locale files (ar, de, en, fr, pl, zh-CN).

---

## Success Criteria

- [ ] `GET /api/v3/admin/translatable_resources` returns all 7 registered resource types
- [ ] `GET /api/v3/admin/products/:id/translations` returns locale-keyed matrix with field metadata
- [ ] `POST /api/v3/admin/translations/batch` persists translations atomically; rollback on any failure
- [ ] SPA translations dialog shows all fields as rows and locales as columns
- [ ] Nested children (OptionValues) appear indented under parent (OptionType) in the editor
- [ ] Rich-text fields render a rich-text editor; plain-text fields render a text input
- [ ] Coverage card shows "X of Y locales translated"
- [ ] E2E: product name translatable; option type + values batch-saveable

---

## Out of Scope

- Centralized translations admin page (drafted in `5.4-centralized-translations-admin.md`, not implemented)
- Bulk CSV import/export for translations (deferred to 6.0)
- Staleness/completeness tracking per locale (deferred to 6.0)
- Translation workflow / draft-publish approval flow
- Third-party translation service integrations (Phrase, Crowdin)
- RTL field rendering hints
- Translating additional resource types beyond the 7 registered (e.g., shipping methods, promotions)
