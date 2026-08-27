# Implementation Plan: Custom Fields / Metafields

**Branch**: `014-custom-fields-metafields` | **Date**: 2026-08-25 | **Spec**: `specs/014-custom-fields-metafields/spec.md`

**Input**: Feature specification from `specs/014-custom-fields-metafields/spec.md`

**Note**: This document reverse-engineers the plan for an already-implemented feature (brownfield migration), not a forward design. It records the actual architecture found in the codebase.

## Summary

Custom Fields (internally still named "Metafields") let store admins define typed, schema-enforced, per-resource-type fields (`Spree::MetafieldDefinition`) and set per-record values (`Spree::Metafield`, STI-typed) on any of 29 `Spree::Metafields`-including models. The Admin API exposes full CRUD for both; the Store API exposes read-only storefront-visible values via `?expand=custom_fields`. The API-facing naming ("Custom Fields") is bridged onto the internal "Metafields" naming via serializer renames, `alias_attribute`s, and constant aliases (`Spree::CustomField = Spree::Metafield`) — the full model/table rename is deferred to 6.0 per `docs/plans/5.5-6.0-custom-fields-rename.md`.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines: `spree/core`, `spree/api`, `spree/admin`) and TypeScript (React SPA: `packages/dashboard`, `packages/dashboard-core`, `packages/admin-sdk`, `packages/sdk`)

**Primary Dependencies**: Backend — CanCanCan (authorization), Ransack (`whitelisted_ransackable_attributes`/`_scopes` on `MetafieldDefinition`), Alba serializers, `Spree::PrefixedId` (Sqids-based `cf_`/`cfdef_` ids), STI (`type` column on `spree_metafields`). Frontend — TanStack Query (`useCustomFields`/`useCustomFieldDefinitions` hooks), React Hook Form + Zod (`schemas/custom-field-definition.ts`), `@spree/admin-sdk` generic + first-class resource bindings.

**Storage**: PostgreSQL/SQLite3 via ActiveRecord — `spree_metafields` (STI, polymorphic `resource`), `spree_metafield_definitions`, no foreign key constraints, no column defaults except at the app layer.

**Testing**: RSpec (`spree/api/spec/controllers/.../custom_field*_spec.rb`, `spree/api/spec/integration/.../custom_field*_spec.rb`, `spree/api/spec/serializers/.../custom_field_serializer_spec.rb`), Vitest/MSW (`packages/admin-sdk/tests/custom-fields.test.ts`), Playwright (`packages/dashboard/e2e/custom-field-definitions.spec.ts`, `packages/dashboard/e2e/products-custom-fields.spec.ts`).

**Target Platform**: Rails engine gems consumed by a Spree host app; React SPA served standalone, proxying to Rails Admin/Store API v3.

**Project Type**: Monorepo — touches `spree/core`, `spree/api`, `spree/admin` (legacy, unchanged), `packages/dashboard`, `packages/dashboard-core`, `packages/admin-sdk`, `packages/sdk` (generated).

**Performance Goals**: N/A — not a performance-sensitive feature; standard CRUD + N+1-safe `includes(:metafield_definition)` on the `metafields`/`public_metafields`/`private_metafields` associations.

**Constraints**: Uniqueness on `(namespace, key, resource_type)` for definitions and `(metafield_definition_id, resource_type, resource_id)` for values — both DB- and model-enforced. No free-form values without a definition (no schemaless mode).

**Scale/Scope**: 29 `Spree::Metafields`-including models; 6 first-class SDK/SPA parents (products, variants, orders, customers, categories, option_types); remaining 23 use the generic Admin API/SDK escape hatch.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (models/concern), `spree/api` (controllers/serializers/routes), `spree/admin` (legacy, unchanged), `packages/dashboard`, `packages/dashboard-core`, `packages/admin-sdk`, `packages/sdk` (generated). Cross-module coupling goes through the documented path: SPA → `@spree/admin-sdk` → Admin API v3 → `spree/core` models. No direct SPA-to-Rails-model reach-through found. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: Confirmed — `use-custom-fields.ts` hooks call `adminClient.customFields(...)`/`adminClient.customFieldDefinitions` exclusively; no server-rendered HTML or direct model access from the SPA. **Pass.**
- **III. Read/Write Field Symmetry**: Admin `CustomFieldsController#permitted_params` permits `:custom_field_definition_id, :value` — exactly what the serializer's `custom_field_definition_id` alias exposes. `CustomFieldDefinitionsController` (5.5) permits `label`/`field_type`/etc. matching serializer output. The one asymmetry — `display_on` on the wire vs. the eventual `storefront_visible` boolean — is explicitly flagged as a documented, in-flight 6.0 change in the rename plan, not an undocumented mismatch. **Pass, with the 6.0 rename tracked.**
- **IV. Test-Backed**: RSpec controller + integration + serializer specs (backend), Vitest/MSW SDK tests, Playwright e2e for both the Settings definitions page and the inline product custom-fields editor. **Pass.**
- **V. Translations and Prefixed IDs**: SPA strings load through i18next (`admin.custom_field_definitions.*` keys referenced in `use-custom-fields.ts` toasts). All ids are prefixed (`cf_`, `cfdef_`), with legacy `mf_`/`mfdef_` still decodable. **Pass.**
- **VI. `docs/plans/` for Architectural Changes**: This feature is fully governed by `docs/plans/5.5-6.0-custom-fields-rename.md` (rename plan) and adjacent to `docs/plans/5.4-metafield-translations.md` (pending). Both already exist; no new plan entry required by this migration. **Pass.**

No violations — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/014-custom-fields-metafields/
├── plan.md              # This file
├── spec.md              # Reverse-engineered spec
└── tasks.md             # Reverse-engineered task list (all marked done)
```

### Source Code (repository root)

```text
# spree/core — models, concern
spree/core/
├── app/models/spree/metafield.rb                       # Spree::Metafield (STI base), TYPE_TOKENS vocabulary
├── app/models/spree/metafields/                         # STI subclasses: short_text, long_text, rich_text, number, boolean, json.rb
├── app/models/spree/metafield_definition.rb              # Spree::MetafieldDefinition, field_type/label aliases
├── app/models/spree/custom_field.rb                      # Constant alias: Spree::CustomField = Metafield
├── app/models/spree/custom_field_definition.rb           # Constant alias: Spree::CustomFieldDefinition = MetafieldDefinition
├── app/models/concerns/spree/metafields.rb               # Spree::Metafields concern — included by 29 models
└── db/migrate/20250728095629_create_spree_metafields.rb

# spree/api — Admin & Store API v3
spree/api/
├── app/controllers/spree/api/v3/admin/custom_fields_controller.rb
├── app/controllers/spree/api/v3/admin/custom_field_definitions_controller.rb
├── app/serializers/spree/api/v3/custom_field_serializer.rb              # Store
├── app/serializers/spree/api/v3/admin/custom_field_serializer.rb        # Admin (extends Store)
├── app/serializers/spree/api/v3/admin/custom_field_definition_serializer.rb
├── config/routes.rb                                                     # custom_fieldable concern, custom_field_definitions
└── spec/{controllers,integration,serializers}/spree/api/v3/**/custom_field*_spec.rb

# spree/admin — legacy Rails admin (unchanged, not the target for new work)
spree/admin/
├── app/controllers/spree/admin/metafield_definitions_controller.rb
└── app/helpers/spree/admin/metafields_helper.rb

# packages/dashboard — admin SPA
packages/dashboard/src/
├── routes/_authenticated/$storeId/settings/custom-field-definitions.tsx
├── tables/custom-field-definitions.tsx
├── components/spree/custom-fields/custom-fields-inline.tsx
├── schemas/custom-field-definition.ts
└── e2e/{custom-field-definitions,products-custom-fields}.spec.ts

# packages/dashboard-core — hooks
packages/dashboard-core/src/hooks/use-custom-fields.ts

# packages/admin-sdk — Admin API client
packages/admin-sdk/
├── resources/ (custom-fields.ts, custom-field-definitions.ts — generic + first-class bindings on products/variants/orders/customers/categories/option_types)
├── examples/custom-field-definitions/
├── examples/product-custom-fields/
└── tests/custom-fields.test.ts

# packages/sdk — Store API client (generated)
packages/sdk/src/types/generated/   # StoreCustomField type
```

**Structure Decision**: Full-stack feature already implemented across all listed modules. Backend owns the model/validation/authorization layer (`spree/core` + `spree/api`); the SPA (`packages/dashboard` + `packages/dashboard-core` + `packages/admin-sdk`) is a pure consumer of the Admin API per Constitution Principle II. `packages/sdk` only carries generated read types for the Store API expand surface. `spree/admin` (legacy) still runs the old UI in parallel and is intentionally excluded from further investment.

## Complexity Tracking

*No violations — table intentionally omitted.*
