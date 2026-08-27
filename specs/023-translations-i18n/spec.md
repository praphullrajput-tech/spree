# Feature Specification: Translations / i18n (Backend Resource Translations)

**Feature Branch**: `023-translations-i18n`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (`Spree::TranslatableResource`/`TranslatableResourceScopes`/`TranslatableResourceSlug` concerns, Mobility gem + `Mobility::Plugins::StoreBasedFallbacks`, `Spree::Translations` module, Admin API v3 `translations`/`translations/batch`/`translatable_resources`/`locales` endpoints, `Spree::Exports::ProductTranslations` CSV export, `@spree/dashboard` resource translations card/dialog) as part of the spec-kit brownfield migration. Scope is **backend resource-content translation** (Mobility-backed field translation for Product/Taxon/OptionType/OptionValue/Taxonomy/Store/Policy) — **not** the frontend i18next UI-string system (`packages/dashboard/src/locales/*.json`), which is a separate concern documented elsewhere in `CLAUDE.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Storefront and admin reads resolve to the request locale (Priority: P1)

A customer browsing the storefront in French, or an admin viewing the dashboard with `x-spree-locale: de`, sees translated field values (product name, description, slug, category name, etc.) transparently — the same serializer attribute (`name`, `description`) returns the localized value with no separate `name_fr` field.

**Why this priority**: This is the foundation every other translation workflow depends on — reads must resolve per-locale before any write path is useful.

**Independent Test**: Set `Mobility.locale = :de` (or send `x-spree-locale: de`), request a product with a `de` translation for `name`, confirm the plain `name` attribute returns the German value; request with a locale that has no translation and confirm it falls back through `Mobility::Plugins::StoreBasedFallbacks` to the default locale value.

**Acceptance Scenarios**:

1. **Given** a `Spree::Product` with an `en` (default) and a `de` translation for `name`, **When** `Mobility.locale` is `:de`, **Then** `product.name` returns the German value.
2. **Given** a `de` translation exists only for `name` but not `description`, **When** reading `description` under `:de`, **Then** the store-configured fallback chain (`Mobility.store_based_fallbacks`) returns the fallback locale's value instead of `nil`.
3. **Given** the request locale is unsupported by the current store, **When** `Spree::Api::V3::LocaleAndCurrency` resolves it, **Then** it rejects the locale rather than silently reading an arbitrary locale's data.

---

### User Story 2 - Admin edits translations for one resource across all locales (Priority: P1)

A store admin opens a product's (or option type's, or category's) "Translations" card in `packages/dashboard`, picks a target locale, edits fields in a spreadsheet-style dialog, and saves — writing all edited locales/fields for that resource (and, for option types, its nested option values) in one atomic request.

**Why this priority**: The write path is the actual value-add of this feature; storefront reads (US1) are inert without a way to populate translations.

**Independent Test**: `GET /api/v3/admin/products/:id/translations` to fetch the matrix + discovery fields, edit a `fr` value in `ResourceTranslationsDialog`, submit, and confirm `POST /api/v3/admin/translations/batch` echoes the updated matrix and a subsequent `GET` reflects the change.

**Acceptance Scenarios**:

1. **Given** a product with no `fr` translations, **When** an admin submits `{ resource_type: "product", resource_id: "prod_...", values: { fr: { name: "Machine à espresso" } } }` via the batch endpoint, **Then** `Spree::Product#upsert_translations` is invoked, only `name` is written under `fr`, and other fields/locales are untouched (omit-to-leave-alone).
2. **Given** a batch entry sets a field to `""`, **When** saved, **Then** an empty string is persisted (read falls back to source via `column_fallback`); **given** a field is set to `nil`, **Then** that translation cell is deleted.
3. **Given** a batch contains multiple entries of different resource types (e.g. an `option_type` and one of its `option_value`s), **When** any entry fails validation, **Then** the whole transaction rolls back and the response details the failing entry's index (`Spree::Translations::Batch::EntryError`).
4. **Given** a batch entry targets a locale not in the store's `supported_locales_list`, **When** submitted, **Then** the write raises `ActiveRecord::RecordInvalid` (`:unsupported_locale`) and surfaces as a 422, never silently accepted.
5. **Given** an API-key (secret key) caller, **When** the batch spans resource types the key lacks `write_<resource>` scope for, **Then** the request is rejected 403 before any record is touched (`require_batch_scopes!`); a JWT caller instead relies on per-record `authorize!(:update, record)`.

---

### User Story 3 - Admin discovers which fields/locales are translatable, without per-model code (Priority: P2)

An admin-facing client (the dashboard, or a third-party integration) needs to know, for any registered resource, which fields are translatable, their type (`string`/`html`/`slug`), and which locales the store supports — without hardcoding per-model knowledge.

**Why this priority**: Discovery is what makes the editor and the registry generic — without it, every new translatable model would need bespoke frontend code.

**Independent Test**: `GET /api/v3/admin/translatable_resources` returns `product`, `category`, `option_type`, `option_value`, `taxonomy`, `store`, `policy` each with their `fields[]` (key + type); `GET /api/v3/admin/locales` returns the current store's `supported_locales_list` with the default flagged.

**Acceptance Scenarios**:

1. **Given** the registry (`Rails.application.config.spree.translatable_resources`), **When** `Spree::Translations.registry` is called, **Then** it returns one entry per registered class with `resource_type` (public token) and `fields` (public field name + inferred `type`).
2. **Given** `Spree::Product` declares `RICH_TEXT_TRANSLATABLE_FIELDS = %i[description]`, **When** discovery runs, **Then** `description` is typed `html` (drives rich-text editor) while `name`/`meta_title` are typed `string` and `slug` is typed `slug`.
3. **Given** `Spree::OptionType` stores its translatable column as `presentation` but exposes it publicly as `label`, **When** discovery and the matrix are read, **Then** both surfaces use the public name `label` (`translatable_field_aliases`), and `label=` is what the batch write accepts.

---

### User Story 4 - Admin bulk-translates products via CSV (Priority: P3)

A store admin exports all products' translatable fields (name, description, slug, meta_title, meta_description) across every non-default supported locale to CSV, edits offline, and — separately — has an import path for the same shape (product translation import is documented in the async import machinery this feature builds on).

**Why this priority**: Bulk workflows matter operationally (hundreds of products) but are additive to the per-resource API (US2) and scoped to products only today.

**Independent Test**: Trigger `Spree::Exports::ProductTranslations` for a store with `de`/`fr` supported locales; confirm the generated CSV has `Spree::CSV::ProductTranslationPresenter::CSV_HEADERS` and one row per `(product, locale)` pair via `product.to_translation_csv(store, locales)`.

**Acceptance Scenarios**:

1. **Given** a store with only its default locale enabled, **When** the export runs, **Then** it produces the default (non-multi-line) export path since there are no target locales.
2. **Given** `status: 'archived'` products and no explicit search params, **When** the export scope is built, **Then** archived products are excluded by default.

---

### Edge Cases

- What happens when a batch write targets a resource the requesting store doesn't own? → `parent_relation` scopes lookups through `for_store(current_store)` where available; a cross-store id raises `ActiveRecord::RecordNotFound`.
- What happens when the read matrix is requested for a resource class not in the registry? → `ensure_translatable!` checks the class's ancestor names against the registry set and raises `ActiveRecord::RecordNotFound` (also guards subclasses like `Spree::Category < Spree::Taxon`).
- How does the system handle the storefront ever seeing a `translations` matrix? → It never does — `Translatable` concern is only included in **Admin** serializers, gated further by `?expand=translations`; Store serializers have no such attribute.
- What happens to translation rows when a batch write deletes the last remaining translated field for a locale? → `destroy_locale_translation` (model-level) removes the row directly rather than resaving with all-nil fields, avoiding a spurious presence-validation failure on fields like `Product#name`.
- What happens when reading a translated `description`/`body` HTML field? → Sanitization is owned by the model's own writer at persist time, not by the translation write path (`upsert_translations` only routes values to existing setters).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST resolve every translatable field read (`name`, `description`, `slug`, etc.) to the active `Mobility.locale`/`I18n.locale`, set by `x-spree-locale` (Store/Admin API) via `Spree::Api::V3::LocaleAndCurrency`, with no separate per-locale attribute name.
- **FR-002**: System MUST fall back to a configurable locale chain (`Mobility.store_based_fallbacks`, a `Concurrent::ThreadLocalVar`-backed patch over Mobility's static fallbacks plugin) when the active locale has no translation for a field, and ultimately to the record's default-locale (column) value via `column_fallback`.
- **FR-003**: System MUST let any model in `Rails.application.config.spree.translatable_resources` (`Product`, `Taxon`, `Taxonomy`, `OptionType`, `OptionValue`, `Store`, `Policy`) declare a `TRANSLATABLE_FIELDS` constant and optionally `RICH_TEXT_TRANSLATABLE_FIELDS`, gaining Mobility-backed translation storage via `translates(*TRANSLATABLE_FIELDS, column_fallback: ...)`.
- **FR-004**: System MUST provide a public-name/internal-name bridge (`translatable_field_aliases`, `public_translatable_fields`) so a model whose translatable column has a legacy name (`OptionType#presentation`) exposes and accepts a different public API name (`label`) everywhere translations are read or written — read/write symmetry is enforced at this layer.
- **FR-005**: System MUST expose a single instance method, `upsert_translations(values)`, that writes `{ locale => { field => value } }` with omit-to-leave-alone semantics: an absent locale or field is untouched; `""` writes an empty string; `nil` deletes that field's translation cell (via `destroy_locale_translation` when needed) — all within one DB transaction, rolling back entirely on any validation failure.
- **FR-006**: System MUST validate every locale in a write against the resolved store's `supported_locales_list` (`translatable_store` — the record's own `store` association if present, else `Spree::Current.store`) and raise `ActiveRecord::RecordInvalid` on any unsupported locale, never silently accepting it.
- **FR-007**: System MUST expose one generic, registry-driven Admin API read endpoint per translatable resource (`GET /api/v3/admin/{products,categories,option_types}/:parent_id/translations`, mounted via the `:translatable` route concern) returning the full matrix, discovery `fields[]` (key/type/source), and nested translatable children (e.g. an option type's option values) in one request — no per-model translation controllers.
- **FR-008**: System MUST expose one generic, atomic Admin API write endpoint (`POST /api/v3/admin/translations/batch`) accepting a flat array of `{ resource_type, resource_id, values }` entries spanning possibly-different resource types, succeeding or rolling back as a whole (`Spree::Translations::Batch`), with per-entry error indexing on failure.
- **FR-009**: System MUST expose registry/discovery endpoints — `GET /api/v3/admin/translatable_resources` (fields by resource type, no record needed) and `GET /api/v3/admin/locales` / `GET /api/v3/store/locales` (the store's supported locales, default flagged) — so clients discover translatable shape and available locales rather than hardcoding them.
- **FR-010**: System MUST make the `translations` matrix available on Admin serializers only, strictly opt-in via `?expand=translations` (never a default attribute, never present on Store serializers), reusing `Spree::Translations.matrix_for` for both the expand attribute and the dedicated endpoint.
- **FR-011**: System MUST gate the batch endpoint's authorization per entry: API-key (secret key) callers require `write_<resource>` scope for every distinct resource type present in the batch (checked up front, before any writes); JWT callers rely on per-record CanCanCan `authorize!(:update, record)`.
- **FR-012**: System MUST support bulk CSV export of product translations (`Spree::Exports::ProductTranslations`) across all non-default `supported_locales_list` locales, one row per `(product, locale)`, excluding archived products by default when no explicit search params are given.

### Key Entities

- **`Spree::TranslatableResource`** (concern): the core contract — `translatable_fields`/`public_translatable_fields`/`translatable_field_aliases`/`translatable_rich_text_fields` (class-level discovery), `upsert_translations`/`destroy_locale_translation`/`translatable_store` (instance-level write), backed by Mobility's table backend (one `*_translations` row per `(record_id, locale)`).
- **`Spree::TranslatableResourceScopes`** (concern): `join_translation_table` — Arel-level outer join helper for querying against a specific locale's translation row.
- **`Spree::TranslatableResourceSlug`** (concern): `localized_slugs_for_store` — resolves the slug/permalink per supported locale, for sitemap/redirect use.
- **`Spree::Translations`** (stateless module): shared builder for `matrix_for` (the `{locale => {field => value, translated_field_count}}` read shape), `fields_for` (discovery), and `registry` (the public `translatable_resources` listing) — reused by the dedicated endpoint, the `?expand=translations` attribute, the batch write echo, and the discovery endpoint.
- **`Spree::Translations::Batch`**: orchestrates the multi-record atomic upsert behind `POST .../translations/batch`; raises a typed `EntryError` (carrying the failing entry's index) on any per-entry validation failure.
- **Registered translatable models**: `Spree::Product` (`name`, `description` [html], `slug`, `meta_description`, `meta_title`), `Spree::Taxon` (`name`, `pretty_name`, `description` [html], `permalink`), `Spree::Taxonomy` (`name`), `Spree::OptionType`/`Spree::OptionValue` (public `label`, internal `presentation`, via `Spree::PresentationTranslatable::TRANSLATABLE_FIELDS`), `Spree::Store` (`name`, `meta_description`, `meta_keywords`, `seo_title`, `customer_support_email`, …), `Spree::Policy` (`name`, `body` [html]).
- **`Mobility::Plugins::StoreBasedFallbacks`**: a `Mobility::Plugin` patch replacing the gem's boot-time-static fallback chain with a `Concurrent::ThreadLocalVar`-backed, dynamically reconfigurable one (`Mobility.store_based_fallbacks=`), set per-request from the current store's locale configuration.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::TranslatableResource`/`TranslatableResourceScopes`/`TranslatableResourceSlug` concerns (`app/models/concerns/spree/`), `Spree::Translations` + `Spree::Translations::Batch` (`lib/spree/translations.rb`), `Mobility::Plugins::StoreBasedFallbacks` (`lib/mobility/plugins/store_based_fallbacks.rb`), `Spree::Exports::ProductTranslations` (`app/models/spree/exports/product_translations.rb`), `Spree::CSV::ProductTranslationPresenter`, registry in `lib/spree/core/engine.rb` (`Rails.application.config.spree.translatable_resources`), per-model `TRANSLATABLE_FIELDS`/`RICH_TEXT_TRANSLATABLE_FIELDS` declarations on Product/Taxon/Taxonomy/OptionType/OptionValue/Store/Policy |
| `spree/api` (Store/Admin API v3) | Yes | `Spree::Api::V3::Admin::TranslationsController` (nested read), `Admin::Translations::BatchesController` (atomic write), `Admin::TranslatableResourcesController` + `Admin::LocalesController`/`Store::LocalesController` (discovery), `Spree::Api::V3::Admin::Translatable` serializer concern (`?expand=translations`), `:translatable` route concern mirroring `:custom_fieldable`, `Spree::Api::V3::LocaleAndCurrency` (locale resolution — pre-existing, unchanged by this feature) |
| `packages/dashboard` (admin SPA) | Yes | `ResourceTranslationsCard` (launcher) + `ResourceTranslationsDialog` (spreadsheet editor) under `components/spree/translations/`, `useResourceTranslations`/`use-translations.ts` hook, e2e specs (`e2e/option-type-translations.spec.ts`, `e2e/products-translations.spec.ts`) |
| `packages/admin-sdk` | Yes | Resource-scoped `.translations` accessors (`adminClient.products.translations`, `.categories.translations`, `.optionTypes.translations`) plus the batch/discovery/locales endpoints |
| `packages/sdk` | Yes (generated) | `StoreLocale` type + `GET /api/v3/store/locales` — generated from serializer changes, not hand-written |
| `docs/plans/` | Yes | `docs/plans/5.5-6.0-resource-translations-api.md` (this migration's authoritative plan, Phase 1 shipped) and adjacent `5.4-centralized-translations-admin.md` / `5.4-metafield-translations.md` (pending, see Migration Notes) |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints**:
  - `GET /api/v3/admin/{products,categories,option_types}/:parent_id/translations` (read-only matrix + discovery + nested children)
  - `POST /api/v3/admin/translations/batch` (atomic multi-record, multi-resource-type upsert)
  - `GET /api/v3/admin/translatable_resources` (registry discovery)
  - `GET /api/v3/admin/locales`, `GET /api/v3/store/locales` (supported-locale discovery)
- **Serializer fields (read)**: per-locale matrix `{ locale => { <public field>: value, translated_field_count } }` via `Spree::Api::V3::Admin::Translatable`'s `translations` attribute (Admin-only, `?expand=translations`); discovery `fields[]` = `{ key, type, source }` (`Spree::Translations.fields_for`/`.registry`). Field names on read (`label`, `name`, `description`, …) are exactly what the batch endpoint's `values.<locale>.<field>` accepts — no client-side renaming.
- **Auth**: Admin API — secret key + `read_<resource>`/`write_<resource>` scopes (checked per-entry for the batch endpoint) or JWT + CanCanCan (`authorize!(:show/:update, parent_or_record)`). No Store API write surface exists or is planned for this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A storefront/admin request in any store-supported locale returns translated field values with zero client-visible difference in attribute shape from the default locale.
- **SC-002**: An admin can edit and save translations for a product (or an option type plus all its option values) in a single round trip, with all-or-nothing persistence on validation failure.
- **SC-003**: Adding a new translatable model to the registry requires zero new controller/route/serializer code — only a `TRANSLATABLE_FIELDS` constant and a registry entry.
- **SC-004**: No Store API response ever includes a `translations` matrix or an unsupported-locale write succeeds silently.
- **SC-005**: Product translation CSV export produces one row per `(product, non-default-locale)` pair with the documented header set, excluding archived products by default.

## Assumptions

- This spec covers **backend resource-content translation** (Mobility/`TranslatableResource`) only. Frontend i18next UI-string translation (`packages/dashboard/src/locales/*.json`, `packages/dashboard-core/src/locales/*.json`) is a distinct, already-documented system (see `CLAUDE.md` → "Translations") and is out of scope here.
- The feature reflects **Phase 1** of `docs/plans/5.5-6.0-resource-translations-api.md` as shipped: read-all + write (batch) + discovery, no staleness tracking, no generalized cross-registry CSV, no centralized SPA translations page beyond the per-resource card/dialog.
- `Spree::MetafieldDefinition`/`Metafield` translation (folding custom fields into this registry, per `5.4-metafield-translations.md`) is not yet implemented and is not covered by this spec.
- Read routes are mounted on `products`, `categories`, and `option_types` only; `option_value`, `taxonomy`, `store`, and `policy` are writable via the batch endpoint and appear in the discovery registry, but have no dedicated standalone read route yet (option values are read inline as nested children of their option type).

## Migration Notes

This spec documents Phase 1 (5.5) of `docs/plans/5.5-6.0-resource-translations-api.md`, which is **shipped**. Cross-referencing the plan's own phasing:

| Plan item | Status in this codebase |
|---|---|
| `TranslatableResource#upsert_translations`/`#destroy_locale_translation` | Shipped, as documented above |
| `:translatable` route concern + generic `Admin::TranslationsController` (read) | Shipped, mounted on products/categories/option_types |
| `OptionValue` as its own registered translatable resource | Shipped (in `translatable_resources`, has `TRANSLATABLE_FIELDS`) |
| `?expand=translations` admin serializer attribute | Shipped (`Spree::Api::V3::Admin::Translatable` concern) |
| `GET /admin/translatable_resources` + `GET /{,admin/}locales` discovery | Shipped |
| Single atomic batch write endpoint (`POST /admin/translations/batch`) | Shipped (`Spree::Translations::Batch`, `Admin::Translations::BatchesController`) — the plan's Key Decision #1 |
| Dashboard per-resource translation editor (`ResourceTranslationsCard`/`Dialog`) | Shipped, ahead of the plan's Phase 2 scheduling — the plan expected this in Phase 2 but it exists now |
| **Phase 2 — pending**: `source_digest` + advisory `stale` flag, `?include=staleness` | Not implemented. No staleness tracking exists anywhere in the read/write path today. |
| **Phase 2 — pending**: `GET /api/v3/admin/translations` cross-record coverage matrix (`?resource_type=product&...`) | Not implemented — no coverage/grid endpoint exists; only the per-resource matrix and the registry. |
| **Phase 2 — pending**: Generalized CSV import/export across the full registry (`Spree::Imports/Exports::ResourceTranslations`) | Not implemented — only `Spree::Exports::ProductTranslations` (product-only) exists; no taxon/option-type/policy/store translation CSV importer/exporter. |
| **Phase 2 — pending**: Centralized Translations page (Surface 2, coverage grid + bulk import/export UI) under Products nav | Not implemented — only the per-resource card/dialog (Surface 1) exists in `packages/dashboard`. |
| **Phase 3 — pending**: Fold `MetafieldDefinition`/`Metafield` into `Spree.translatable_resources` | Not implemented — `5.4-metafield-translations.md` remains a draft plan with no code. |

**Gap identified during this migration**: the plan's route-concern example (`resources :option_types, concerns: [:custom_fieldable, :translatable]`) matches the shipped routes; no discrepancy found between plan and code for Phase 1 items. The dashboard editor UI, listed in the plan under Phase 2 ("React dashboard: per-resource translation tab (Surface 1)"), has already shipped alongside Phase 1 rather than waiting for Phase 2 — the plan document is stale on this sequencing point.
