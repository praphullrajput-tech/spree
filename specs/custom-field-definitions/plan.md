# Implementation Plan: Custom Field Definitions

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: 5.4 API bridge ✅; 5.5 aliases + Admin CRUD ✅; 6.0 rename pending

---

## Summary

Three-phase rename of "Metafields" to "Custom Fields": the 5.4 phase changed the Store API naming (expand param, response key, prefix IDs, serializer class names) as a clean break. The 5.5 phase introduced `Spree::CustomField` / `Spree::CustomFieldDefinition` as constant aliases of the existing model classes so controllers and serializers reference the 6.0-bound names today without schema changes. It also added a token vocabulary for `field_type` (replacing raw Ruby class strings) and shipped the Admin CRUD API for managing definitions and per-resource values. The 6.0 phase will rename the tables, columns, and STI namespaces and replace the three-way `display_on` enum with a `storefront_visible` boolean.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Serialization** | Alba → Typelizer |
| **STI** | `Spree::Metafields::*` subtypes on `spree_metafields.type` column |
| **Bridge approach** | Constant alias (not subclass) — confirmed correct for STI compat |
| **Scope** | Full-stack (5.4 + 5.5 complete); 6.0 model rename pending |

---

## Key Decisions

1. **Constant alias, not subclass.** `Spree::CustomField = Spree::Metafield` means same class, two names. Subclassing would break STI (`Spree::Metafields::ShortText` would not be `< Spree::CustomField`).
2. **Token vocabulary for `field_type`.** Exposing Ruby class strings (`Spree::Metafields::ShortText`) across the API coupled every SDK consumer to internal naming. Tokens (`short_text`) are stable identifiers that survive the 6.0 class rename without a client migration.
3. **No deprecation warnings on `Spree::Metafield` references in 5.5.** 5.5 is a soft introduction — teams adopt the new name at their own pace. Warnings land in 6.0.
4. **`storefront_visible` is a boolean accessor in 5.5, a real column in 6.0.** The accessor bridges `display_on` via `ActiveModel::Type::Boolean.new.cast(value)`. The column rename and data migration ship in 6.0.
5. **Nested routing for values, flat routing for definitions.** Values are per-instance (this product's `material`); definitions are per-type (all products share the same definitions). Two separate routing concerns.
6. **Hooks centralized in `@spree/dashboard-core`.** Custom fields appear on every resource detail page; centralizing the hooks avoids duplication across 6+ SPA sections.
7. **`field_type` write accepts both token and class string.** Legacy class strings still work in 5.5 for external integrations that wrote the old form. Clean removal in 6.0.

---

## Constitution Check

- [x] **API-First**: Admin CRUD API shipped before SPA consumed it
- [x] **Read/Write Symmetry**: `label` serialized and accepted; `storefront_visible` serialized and accepted; model bridges to `name` / `display_on` columns
- [x] **Prefixed IDs**: `cfdef_…` for definitions; `cf_…` for values; old `mf_`/`mfdef_` prefixes still resolve (sqids ignores prefix on decode)
- [x] **Serializer Hierarchy**: `Admin::CustomFieldSerializer` extends `V3::CustomFieldSerializer`
- [x] **Type Pipeline**: Typelizer + Zod regen after serializer changes; `StoreCustomField`, `AdminCustomFieldDefinition` types generated
- [x] **Security**: CanCanCan via parent resource authorization; `custom_field_definition_id` validated — no free-form mode
- [x] **Namespace**: `Spree::CustomField` / `Spree::CustomFieldDefinition` — constant aliases of `Spree.base_class` subclasses
- [x] **Plan Conflicts**: Reviewed `6.0-product-types.md` (ProductType gains `has_many :custom_field_definitions`); `5.4-search-provider.md` (`CustomFieldDefinition.filterable`); no conflicts

---

## Project Structure

```text
# Backend — models (aliases)
spree/core/app/models/spree/custom_field.rb               ← constant alias to Spree::Metafield
spree/core/app/models/spree/custom_field_definition.rb    ← constant alias to Spree::MetafieldDefinition

# Backend — underlying models
spree/core/app/models/spree/metafield.rb                  ← STI base + TYPE_TOKENS + field_type accessor
spree/core/app/models/spree/metafield_definition.rb       ← alias_attributes: label, field_type, storefront_visible

# Backend — serializers
spree/api/app/serializers/spree/api/v3/custom_field_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/custom_field_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/custom_field_definition_serializer.rb

# Backend — controllers
spree/api/app/controllers/spree/api/v3/admin/custom_field_definitions_controller.rb
spree/api/app/controllers/spree/api/v3/admin/custom_fields_controller.rb         ← nested per parent

# Backend — specs
spree/core/spec/models/spree/custom_field_definition_spec.rb
spree/api/spec/integration/spree/api/v3/admin/custom_field_definitions_spec.rb

# Frontend
packages/dashboard/src/routes/_authenticated/$storeId/settings/custom-field-definitions.tsx
packages/dashboard/src/schemas/custom-field-definition.ts
packages/dashboard/src/components/spree/custom-fields/definition-form.tsx
packages/dashboard/src/components/spree/custom-fields/custom-fields-inline.tsx
packages/dashboard/e2e/custom-field-definitions.spec.ts
```

---

## Phase 1: 5.4 API Bridge (✅ Complete)

- Serializer rename: `MetafieldSerializer` → `CustomFieldSerializer`
- Expand param: `?expand=metafields` → `?expand=custom_fields`
- Response key: `"metafields"` → `"custom_fields"`
- Prefix IDs: `mf_` → `cf_`, `mfdef_` → `cfdef_`
- Admin endpoint rename: `/metafield_definitions` → `/custom_field_definitions`
- `public_metadata` deprecation warning added
- Type pipeline run; SDK types updated

---

## Phase 2: 5.5 Constant Aliases + Admin CRUD (✅ Complete)

- `Spree::CustomField = Spree::Metafield` constant alias
- `Spree::CustomFieldDefinition = Spree::MetafieldDefinition` constant alias
- `alias_attribute :label, :name` on `MetafieldDefinition`
- `alias_attribute :field_type, :metafield_type` on `MetafieldDefinition`
- `alias_attribute :custom_field_definition_id, :metafield_definition_id` on `Metafield`
- `storefront_visible` boolean accessor on `MetafieldDefinition`
- `TYPE_TOKENS` hash + `field_type` token accessor on `Metafield`
- `Admin::CustomFieldDefinitionsController` (flat, `resource_type` filter)
- `Admin::CustomFieldsController` (nested under parent via route concern)
- Routes: `concern :custom_fieldable` applied to products, variants, orders, customers, categories, option_types
- Admin SDK first-class bindings on 6 parents + generic escape hatch
- Settings → Custom Field Definitions SPA page

---

## Phase 3: 6.0 — Full Rename (PENDING)

- Rename tables: `spree_metafields` → `spree_custom_fields`, `spree_metafield_definitions` → `spree_custom_field_definitions`
- Rename columns: `metafield_definition_id` → `custom_field_definition_id`, `metafield_type` → `field_type`
- Replace `display_on` string enum with `storefront_visible` boolean column
- Rename STI type values: `Spree::Metafields::ShortText` → `Spree::CustomFields::ShortText`, etc.
- Drop `public_metadata` columns; rename `private_metadata` → `metadata`
- Drop constant alias files; replace all `Spree::Metafield` references with `Spree::CustomField`
- Drop `alias_attribute` shims; rename the underlying columns instead
- Remove legacy `type` field from `CustomFieldSerializer` (replaced by `field_type` token)
- CSV export headers: `metafield.custom.*` → `custom_field.custom.*`
