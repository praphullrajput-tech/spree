---

description: "Task list for Custom Field Definitions — 5.4+5.5 complete, 6.0 rename pending"
---

# Tasks: Custom Field Definitions

**Status**: 5.4 API bridge complete; 5.5 aliases + Admin CRUD complete; 6.0 rename pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Store serializers | `spree/api/app/serializers/spree/api/v3/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/settings/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: 5.4 — API Bridge ✅

- [x] T001 Rename serializer file/class: `MetafieldSerializer` → `CustomFieldSerializer`; `Admin::MetafieldSerializer` → `Admin::CustomFieldSerializer`; `Admin::MetafieldDefinitionSerializer` → `Admin::CustomFieldDefinitionSerializer`
- [x] T002 Update product/variant/category serializers — change expand param from `metafields` to `custom_fields`; change response key from `"metafields"` to `"custom_fields"`
- [x] T003 Update prefix IDs: `mf_` → `cf_` on `Spree::Metafield`; `mfdef_` → `cfdef_` on `Spree::MetafieldDefinition`
- [x] T004 Rename admin controller file: `metafield_definitions_controller.rb` → `custom_field_definitions_controller.rb`; update routes
- [x] T005 Update `Spree.api.dependencies` keys: `custom_field_serializer`, `admin_custom_field_serializer`, `custom_field_definition_serializer`
- [x] T006 Add `public_metadata=` deprecation warning to `Spree::Metadata` concern
- [x] T007 Run type pipeline: `typelizer:generate` → `generate:zod` → `rswag:specs:swaggerize`
- [x] T008 Update SDK examples and docs to use `expand: ['custom_fields']`

**Checkpoint**: Store API returns `"custom_fields"` key ✅; `expand=metafields` no longer works ✅

---

## Phase 2: 5.5 — Constant Aliases + Type Tokens + Admin CRUD ✅

### Model Aliases

- [x] T009 Create `spree/core/app/models/spree/custom_field.rb` — `module Spree; CustomField = Metafield; end`
- [x] T010 Create `spree/core/app/models/spree/custom_field_definition.rb` — `module Spree; CustomFieldDefinition = MetafieldDefinition; end`

### alias_attributes

- [x] T011 Add to `Spree::Metafield`: `alias_attribute :custom_field_definition_id, :metafield_definition_id`; `TYPE_TOKENS` hash; `field_type` reader (token) + `field_type=` writer (accepts token or class string)
- [x] T012 Add to `Spree::MetafieldDefinition`: `alias_attribute :label, :name`; `alias_attribute :field_type, :metafield_type`; `storefront_visible` boolean accessor bridging `display_on`

### Serializers

- [x] T013 [P] [US1/US3] Update `CustomFieldSerializer` — add `field_type` token attribute (alongside legacy `type` for back-compat)
- [x] T014 [P] [US1] Update `Admin::CustomFieldSerializer` — keep `display_on` (5.5); prepares for `storefront_visible: boolean` in 6.0
- [x] T015 [P] [US1] Update `Admin::CustomFieldDefinitionSerializer` — change `field_type` value from class string → token; add `storefront_visible` boolean attribute

### Controllers + Routes

- [x] T016 [US1] Update `Admin::CustomFieldDefinitionsController` — model references use `Spree::CustomFieldDefinition`; filter by `resource_type` param; `permitted_params`: `label`, `field_type`, `namespace`, `key`, `resource_type`, `storefront_visible`
- [x] T017 [US2] Create `Admin::CustomFieldsController` — nested under parent via `concern :custom_fieldable`; `scope` = `parent.metafields`; `permitted_params`: `custom_field_definition_id`, `value`; `load_parent_from_route` helper
- [x] T018 [US2] Update routes — add `concern :custom_fieldable { resources :custom_fields }`; apply to: products, variants, orders, customers, categories, option_types

### Model Spec

- [x] T019 Write/update `spree/core/spec/models/spree/custom_field_definition_spec.rb` — `storefront_visible` accessor behavior; `field_type` token read/write; `label` alias; `Spree::CustomFieldDefinition.equal?(Spree::MetafieldDefinition)` assertion

### Integration Spec

- [x] T020 Write integration spec `spree/api/spec/integration/spree/api/v3/admin/custom_field_definitions_spec.rb` — CRUD + `resource_type` filter; `field_type` token in responses
- [x] T021 Run `bundle exec rake rswag:specs:swaggerize`

### Type Pipeline

- [x] T022 Run `typelizer:generate` → `generate:zod` — `AdminCustomFieldDefinition` type includes `field_type` as union token; `storefront_visible` as boolean

### Frontend

- [x] T023 [US1] Create/update settings route `settings/custom-field-definitions.tsx` — `<ResourceTable>`; create/edit `<Sheet>`; `field_type` select with token labels; `storefront_visible` toggle
- [x] T024 [US1] Create `packages/dashboard/src/schemas/custom-field-definition.ts` — Zod schema; `FormValues` type; `FIELD_TYPE_OPTIONS` from token list
- [x] T025 [US1] Create `components/spree/custom-fields/definition-form.tsx` — form component
- [x] T026 [US2] Create `components/spree/custom-fields/custom-fields-inline.tsx` — inline value editor for resource detail pages; reads definitions by `resource_type`; type-aware input per `field_type`
- [x] T027 [US1] Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.customFieldDefinitions.*`
- [x] T028 [US1] Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [x] T029 Write `packages/dashboard/e2e/custom-field-definitions.spec.ts` — create definition → verify token field_type → set storefront_visible false → delete
- [x] T030 Run `pnpm test:e2e` ✅

### Admin SDK

- [x] T031 Add first-class SDK bindings: `adminClient.products.customFields`, `adminClient.orders.customFields`, `adminClient.customers.customFields`, `adminClient.categories.customFields`, `adminClient.optionTypes.customFields`, `adminClient.customFieldDefinitions`
- [x] T032 Add generic escape hatch: `adminClient.customFields(ownerType, ownerId).list()`

**Checkpoint**: all 5.5 integration tests pass ✅; `pnpm typecheck && pnpm lint` pass ✅

---

## Phase 3: 6.0 — Full Rename (PENDING)

**⚠️ Not yet implemented.**

- [ ] T033 Migration: rename `spree_metafields` → `spree_custom_fields`; rename `spree_metafield_definitions` → `spree_custom_field_definitions`
- [ ] T034 Migration: rename columns `metafield_definition_id` → `custom_field_definition_id`; `metafield_type` → `field_type`
- [ ] T035 Migration: add `storefront_visible boolean not null default true` to `spree_custom_field_definitions`; data migration `back_end → false`; drop `display_on` column
- [ ] T036 Migration: update STI `type` values in `spree_custom_fields`: `Spree::Metafields::ShortText` → `Spree::CustomFields::ShortText`, etc.
- [ ] T037 Migration: drop `public_metadata` columns from all tables; rename `private_metadata` → `metadata` where applicable
- [ ] T038 Delete alias files `custom_field.rb` and `custom_field_definition.rb`; replace with real class definitions using new table names
- [ ] T039 Rename `Spree::Metafields::*` STI subclasses to `Spree::CustomFields::*`
- [ ] T040 Drop `alias_attribute` shims from `Spree::Metafield` / `Spree::MetafieldDefinition`
- [ ] T041 Rename concern: `Spree::Metafields` → `Spree::HasCustomFields`; update all 29 model includes
- [ ] T042 Remove legacy `type` field from `CustomFieldSerializer` (both Store and Admin)
- [ ] T043 Update CSV export headers: `metafield.custom.*` → `custom_field.custom.*`
- [ ] T044 Update all `has_many :metafields` / `has_many :public_metafields` association names to `has_many :custom_fields` / `has_many :storefront_custom_fields`

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No local `use-custom-field-definitions.ts` hook — hooks in `@spree/dashboard-core` | Low | Intentional architectural choice; hooks centralized for cross-resource reuse. Document as architectural decision in plan. |
| 6.0 model/table rename not yet implemented | High | T033–T044 above are the full implementation checklist |
| Legacy `type` (class string) field still in `CustomFieldSerializer` alongside `field_type` token | Low | Remove in 6.0 per plan — dual fields are a 5.5 transition only |
| `Spree::Metafields::*` STI namespace used internally until 6.0 | Low | By design — 5.5 exposed only via tokens; internal class names are hidden from API consumers |
