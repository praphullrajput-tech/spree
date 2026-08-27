# Implementation Plan: Translations / i18n (Backend Resource Translations)

**Branch**: `023-translations-i18n` | **Date**: 2026-08-25 | **Spec**: `specs/023-translations-i18n/spec.md`

**Input**: Feature specification from `specs/023-translations-i18n/spec.md`

**Note**: This document reverse-engineers the plan for an already-shipped feature (brownfield migration), not a prospective design.

## Summary

Spree stores per-field, per-locale translations for a fixed registry of models (`Product`, `Taxon`, `Taxonomy`, `OptionType`, `OptionValue`, `Store`, `Policy`) via the Mobility gem's table backend, with reads transparently resolved to `Mobility.locale`/`I18n.locale` (set from the `x-spree-locale` header) and falling back through a store-configurable locale chain. The `Spree::TranslatableResource` concern is the single contract every registered model includes, exposing class-level discovery (`translatable_fields`, aliasing for legacy column names) and an instance-level atomic upsert (`upsert_translations`) with omit-to-leave-alone semantics. The Admin API v3 exposes this as a registry-driven read endpoint, a single atomic batch write endpoint spanning heterogeneous resource types, and discovery/locale endpoints — no per-model controllers. `packages/dashboard` consumes it via a generic launcher card + spreadsheet-style editor dialog usable for any registered resource. Bulk translation today is CSV-only and product-scoped (`Spree::Exports::ProductTranslations`).

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines, backend: `spree/core`, `spree/api`) and TypeScript (React SPA, `packages/dashboard`, `packages/admin-sdk`)

**Primary Dependencies**: Backend: `mobility` gem (table backend, `store_based_fallbacks` plugin patch), CanCanCan, Alba serializers, `state_machines-activerecord` (unrelated to this feature but shared base). Frontend: TanStack Query (`useResourceTranslations`), React Hook Form (not used here — the editor is a custom spreadsheet grid, not a standard RHF form), shadcn/ui + Base UI dialog primitives.

**Storage**: PostgreSQL/SQLite3 via ActiveRecord — one `*_translations` table per translatable model (Mobility's table backend convention, e.g. `spree_product_translations`), keyed `(record_id, locale)`, no foreign key constraints per repo convention.

**Testing**: RSpec + Factory Bot for the concern/model/service layer and Admin API controller specs (`spree/api/spec/controllers/spree/api/v3/admin/translations/batches_controller_spec.rb`, `locales_controller_spec.rb`); Playwright e2e for the dashboard editor (`packages/dashboard/e2e/option-type-translations.spec.ts`, `products-translations.spec.ts`).

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`) consumed by a Spree host app; React SPA (`packages/dashboard`) proxying to the Admin API v3.

**Project Type**: Monorepo — `spree/core`, `spree/api`, `packages/dashboard`, `packages/admin-sdk`, `packages/sdk` (generated locale type only).

**Performance Goals**: N/A — not a documented perf target in the source plan; the matrix read is intentionally opt-in (`?expand=translations`) specifically to avoid default-path cost on list/detail views.

**Constraints**: Batch write must be all-or-nothing (single DB transaction) even across heterogeneous resource types; locale writes must be validated against the owning store's `supported_locales_list`, never silently accepted outside it.

**Scale/Scope**: 7 registered resource types today (`Product`, `Taxon`, `Taxonomy`, `OptionType`, `OptionValue`, `Store`, `Policy`); registry-driven so adding an 8th requires no new endpoint.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (concerns, `Spree::Translations`, export), `spree/api` (controllers, serializers, routes), `packages/dashboard` (card/dialog/hook), `packages/admin-sdk` (client accessors). Cross-module coupling goes through the Admin API (dashboard never reaches into Rails models) and through the `Spree.translatable_resources` registry (no gem reaches across another's model boundary directly). **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: `useResourceTranslations`/`ResourceTranslationsDialog` call `adminClient.<resource>.translations` exclusively; no server-rendered HTML or direct model access from the SPA. **Pass.**
- **III. Read/Write Field Symmetry**: The matrix read (`{ locale => { field: value } }`) uses `public_translatable_fields` — the exact key set the batch endpoint's `values.<locale>.<field>` accepts (`OptionType#label`/`label=` is the textbook alias case cited in `CLAUDE.md`). **Pass.**
- **IV. Test-Backed**: RSpec model specs for `TranslatableResource`/`Spree::Translations::Batch` (unsupported-locale rejection, omit-to-leave-alone semantics), controller specs for `BatchesController`/`LocalesController`, Playwright e2e for the dialog. **Pass** (already in place — this migration adds no new test debt).
- **V. Translations and Prefixed IDs**: This *is* the backend translation system, not a UI-string consumer — N/A for i18next keys on the backend side. The dashboard card/dialog's own UI copy (button labels, dialog title) does go through i18next per repo convention (`admin.translations.title`, etc.) — confirmed present, not newly introduced by this doc. Resource ids in batch entries and matrix responses are prefixed ids (`prod_...`, `opttype_...`). **Pass.**
- **VI. `docs/plans/` for Architectural Changes**: `docs/plans/5.5-6.0-resource-translations-api.md` is the authoritative plan and already exists, governing this area (Phase 1 shipped, Phase 2/3 pending — see spec.md → Migration Notes). **Pass** — no new plan needed since one already governs.

Any violation must appear in Complexity Tracking below with justification.

*No violations identified — this is a reverse-engineered spec for shipped Phase 1 work that already conforms to the constitution's gates.*

## Project Structure

### Documentation (this feature)

```text
specs/023-translations-i18n/
├── plan.md              # This file
├── spec.md              # Feature specification (already written)
└── tasks.md             # Task breakdown (already written, all marked done — migrated feature)
```

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/
├── app/models/concerns/spree/translatable_resource.rb        # core contract: discovery + upsert_translations + destroy_locale_translation
├── app/models/concerns/spree/translatable_resource_scopes.rb # join_translation_table Arel helper
├── app/models/concerns/spree/translatable_resource_slug.rb   # localized_slugs_for_store
├── app/models/spree/exports/product_translations.rb          # CSV export (product-only, current bulk mechanism)
├── app/models/spree/{product,taxon,taxonomy,option_type,option_value,store,policy}.rb  # TRANSLATABLE_FIELDS / RICH_TEXT_TRANSLATABLE_FIELDS declarations
├── lib/mobility/plugins/store_based_fallbacks.rb              # dynamic per-store fallback chain patch over Mobility
├── lib/spree/translations.rb                                  # Spree::Translations (matrix_for/fields_for/registry) + Spree::Translations::Batch
├── lib/spree/core/engine.rb                                   # translatable_resources registry (config.spree.translatable_resources)
└── spec/models/spree/translatable_resource_spec.rb, spec/lib/spree/translations_spec.rb (and similar)

# spree/api — Store & Admin REST API v3
spree/api/
├── app/controllers/spree/api/v3/admin/translations_controller.rb           # GET nested read (matrix + discovery + children)
├── app/controllers/spree/api/v3/admin/translations/batches_controller.rb   # POST atomic multi-record write
├── app/controllers/spree/api/v3/admin/locales_controller.rb                # GET admin locales
├── app/controllers/spree/api/v3/store/locales_controller.rb                # GET store locales
├── app/controllers/spree/api/v3/admin/translatable_resources_controller.rb # GET registry discovery
├── app/serializers/concerns/spree/api/v3/admin/translatable.rb             # ?expand=translations serializer concern
├── config/routes.rb                                                        # :translatable route concern, translations/batch, translatable_resources
└── spec/controllers/spree/api/v3/admin/{translations,locales_controller}_spec.rb, spec/controllers/.../translations/batches_controller_spec.rb

# packages/dashboard — admin SPA routes/forms
packages/dashboard/src/
├── components/spree/translations/resource-translations-card.tsx    # launcher card (resource-agnostic)
├── components/spree/translations/resource-translations-dialog.tsx  # spreadsheet-style editor
├── hooks/use-translations.ts                                       # useResourceTranslations + SDK accessor map
└── e2e/{option-type-translations,products-translations}.spec.ts

# packages/admin-sdk — hand-written admin client
packages/admin-sdk/src/store-client.ts   # .translations accessor on products/categories/optionTypes resources
```

**Structure Decision**: Backend contract lives in `spree/core` (the concern + shared `Spree::Translations` builder, reused by every consumer); the Admin API v3 in `spree/api` exposes it generically (one controller per HTTP verb-shape, not per model); `packages/dashboard` + `packages/admin-sdk` consume it via a resource-agnostic card/dialog and per-resource `.translations` SDK accessors. No `packages/dashboard-ui`/`dashboard-core` changes — the editor is app-specific enough (product/option-type-aware launcher placement) to live directly in `packages/dashboard`.

## Complexity Tracking

*No constitution violations identified — this table is intentionally empty.*
