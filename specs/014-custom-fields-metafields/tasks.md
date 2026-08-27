---

description: "Task list for the (already-implemented) Custom Fields / Metafields feature"
---

# Tasks: Custom Fields / Metafields

**Input**: Design documents from `specs/014-custom-fields-metafields/`

**Prerequisites**: plan.md, spec.md

**Tests**: Included — the feature ships with RSpec, Vitest/MSW, and Playwright coverage.

**Note**: This is a reverse-engineered task list for an already-shipped feature (brownfield migration). All tasks are marked complete and reference the real files that implement them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Ran in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US4, see spec.md)

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core` and `spree/api` build/test cleanly: `cd spree/core && bundle exec rspec`, `cd spree/api && bundle exec rspec`
- [x] T002 [P] Confirm frontend baseline: `pnpm typecheck && pnpm lint` at workspace root

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T003 [spree/core] Migration `spree/core/db/migrate/20250728095629_create_spree_metafields.rb` — `spree_metafields` (STI, polymorphic `resource`) and `spree_metafield_definitions` tables, no FKs, explicit `null: false`
- [x] T004 [spree/core] `Spree::MetafieldDefinition` model (`spree/core/app/models/spree/metafield_definition.rb`) — `has_prefix_id :cfdef`, `include Spree::DisplayOn`, namespace/key/resource_type uniqueness, `field_type`/`label` API-naming aliases
- [x] T005 [spree/core] `Spree::Metafield` STI base + subclasses (`spree/core/app/models/spree/metafield.rb`, `spree/core/app/models/spree/metafields/{short_text,long_text,rich_text,number,boolean,json}.rb`) — `has_prefix_id :cf`, `TYPE_TOKENS`/`TYPE_CLASS_TO_TOKEN` vocabulary, per-subclass value validation
- [x] T006 [spree/core] `Spree::Metafields` concern (`spree/core/app/models/concerns/spree/metafields.rb`) — `metafields`/`public_metafields`/`private_metafields` associations, `set_metafield`/`get_metafield`/`has_metafield?`, `custom_fields=` nested-attributes bridge, deferred-assignment-on-create handling
- [x] T007 [spree/core] Constant aliases `spree/core/app/models/spree/custom_field.rb` (`CustomField = Metafield`) and `custom_field_definition.rb` (`CustomFieldDefinition = MetafieldDefinition`)
- [x] T008 [spree/api] Ransack allowlist on `MetafieldDefinition` (`whitelisted_ransackable_attributes`, `whitelisted_ransackable_scopes` for `search`/`multi_search`)
- [x] T009 [packages/dashboard-core] `use-custom-fields.ts` hooks + query-key structure (`customFieldDefinitionsRootKey`, per-resource/per-id keys)
- [x] T010 [packages/dashboard] i18next keys under `admin.custom_field_definitions.*` (messages/errors) in `packages/dashboard/src/locales/en.json`

**Checkpoint**: Foundation complete — model layer, concern, and constant aliases in place before any API/UI work.

## Phase 3: User Story 1 - Define a reusable custom field for a resource type (P1) 🎯 MVP

### Tests for User Story 1

- [x] T011 [P] [US1] RSpec integration spec `spree/api/spec/integration/spree/api/v3/admin/custom_field_definitions_spec.rb`
- [x] T012 [P] [US1] RSpec controller spec `spree/api/spec/controllers/spree/api/v3/admin/custom_field_definitions_controller_spec.rb`
- [x] T013 [P] [US1] Playwright e2e `packages/dashboard/e2e/custom-field-definitions.spec.ts`

### Implementation for User Story 1

- [x] T014 [US1] `Admin::CustomFieldDefinitionsController` (`spree/api/app/controllers/spree/api/v3/admin/custom_field_definitions_controller.rb`) — flat resource, filterable by `resource_type`
- [x] T015 [US1] `Admin::CustomFieldDefinitionSerializer` (`spree/api/app/serializers/spree/api/v3/admin/custom_field_definition_serializer.rb`) — `label`, `field_type` token, `display_on`
- [x] T016 [US1] Route: `resources :custom_field_definitions` in `spree/api/config/routes.rb`
- [x] T017 [US1] SPA Settings route + table (`packages/dashboard/src/routes/.../settings/custom-field-definitions.tsx`, `packages/dashboard/src/tables/custom-field-definitions.tsx`) + Zod schema (`packages/dashboard/src/schemas/custom-field-definition.ts`)
- [x] T018 [US1] `packages/admin-sdk` `customFieldDefinitions` resource + `examples/custom-field-definitions/`

**Checkpoint**: Definitions are fully manageable end-to-end.

## Phase 4: User Story 2 - Set and read a custom field value on a record (P1)

### Tests for User Story 2

- [x] T019 [P] [US2] RSpec integration spec `spree/api/spec/integration/spree/api/v3/admin/products/custom_fields_spec.rb`
- [x] T020 [P] [US2] RSpec controller specs `spree/api/spec/controllers/spree/api/v3/admin/custom_fields_controller_spec.rb` and `custom_fields_polymorphic_parent_spec.rb`
- [x] T021 [P] [US2] Vitest/MSW `packages/admin-sdk/tests/custom-fields.test.ts`

### Implementation for User Story 2

- [x] T022 [US2] `Admin::CustomFieldsController` (`spree/api/app/controllers/spree/api/v3/admin/custom_fields_controller.rb`) — parent inferred from route, scoped through `parent.metafields`, `permitted_params` = `:custom_field_definition_id, :value`
- [x] T023 [US2] `custom_fieldable` route concern nested on products/categories/option_types/customers/variants/orders (`spree/api/config/routes.rb`)
- [x] T024 [US2] `Admin::CustomFieldSerializer` (`spree/api/app/serializers/spree/api/v3/admin/custom_field_serializer.rb`) — extends Store serializer, adds `display_on`
- [x] T025 [US2] Upsert-by-definition + blank-destroys-row semantics in `set_metafield`/`custom_fields=` (`spree/core/app/models/concerns/spree/metafields.rb`)
- [x] T026 [US2] `packages/admin-sdk` generic `customFields(ownerType, ownerId)` + first-class bindings on the six parents, `examples/product-custom-fields/`

**Checkpoint**: Values can be created/read/updated/deleted via the Admin API on all wired parents.

## Phase 5: User Story 3 - Expose custom fields to Store API consumers (P2)

### Tests for User Story 3

- [x] T027 [P] [US3] RSpec serializer spec `spree/api/spec/serializers/spree/api/v3/custom_field_serializer_spec.rb`

### Implementation for User Story 3

- [x] T028 [US3] `Spree::Api::V3::CustomFieldSerializer` (`spree/api/app/serializers/spree/api/v3/custom_field_serializer.rb`) — `label`, `field_type`/`type`, `key`, `value`
- [x] T029 [US3] `?expand=custom_fields` wiring on Product/Variant/Category Store serializers, backed by `public_metafields` (`available_on_front_end` scope, i.e. `display_on: both`)
- [x] T030 [US3] `packages/sdk` generated `StoreCustomField` type + `custom_fields` expand param (type-generation pipeline)

**Checkpoint**: Storefront clients can read customer-facing custom fields, admin-only ones stay hidden.

## Phase 6: User Story 4 - Manage custom fields from the admin dashboard (P2)

### Tests for User Story 4

- [x] T031 [P] [US4] Playwright e2e `packages/dashboard/e2e/products-custom-fields.spec.ts`

### Implementation for User Story 4

- [x] T032 [US4] `<CustomFieldsInline>` component (`packages/dashboard/src/components/spree/custom-fields/custom-fields-inline.tsx`) — type-aware editor per `field_type`
- [x] T033 [US4] `useCustomFields`/`useCreateCustomField`/`useUpdateCustomField`/`useDeleteCustomField` hooks wired to the inline editor (`packages/dashboard-core/src/hooks/use-custom-fields.ts`)
- [x] T034 [US4] `useCustomFieldDefinitions`/`useCustomFieldDefinition` + Settings CRUD hooks (`useCreateCustomFieldDefinitionForSettings`, etc.) wired to the Settings page

**Checkpoint**: Full admin workflow (define → assign → view) works end-to-end in the SPA.

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T035 [P] `docs/plans/5.5-6.0-custom-fields-rename.md` — authoritative plan document, tracks 5.4/5.5 shipped + 6.0 pending phases
- [x] T036 Full backend suite: `cd spree/api && bundle exec rspec spec/controllers/spree/api/v3/admin/custom_field* spec/integration/spree/api/v3/admin/custom_field* spec/integration/spree/api/v3/admin/products/custom_fields_spec.rb spec/serializers/spree/api/v3/custom_field_serializer_spec.rb`
- [x] T037 Full frontend suite: `pnpm typecheck && pnpm lint && pnpm test` at workspace root (covers `packages/admin-sdk/tests/custom-fields.test.ts`)
- [x] T038 [P] `cd packages/dashboard && pnpm test:e2e` — `custom-field-definitions.spec.ts`, `products-custom-fields.spec.ts`
- [x] T039 Locale keys present in both `packages/dashboard/src/locales/en.json` and referenced from `use-custom-fields.ts` toasts

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: model layer + concern + constant aliases must exist before any controller/serializer/hook work.
- **US1 (definitions)** has no dependency on US2 but is a practical prerequisite — a value needs a definition to attach to.
- **US2 (values)** depends on US1's definitions existing at runtime (not at code level — the controller code is independent, but a definition record is required for any value to validate).
- **US3 (Store API read)** depends on US2's values existing to have anything to expose; serializer code itself only depends on Foundational.
- **US4 (SPA)** depends on US1 + US2's Admin API endpoints per Constitution Principle II — the SPA cannot precede its backing API.

## Notes

- This feature currently operates under **dual naming** (see spec.md "Migration Notes") — internal model/table/column names remain `Metafield*`, while the API surface and SPA are fully `custom_field*`. Any new task in this area should default to `custom_field` naming per `docs/plans/5.5-6.0-custom-fields-rename.md` → "Constraints on Current Work".
- No task exists for the 6.0 table/column rename or `storefront_visible` boolean migration — those are tracked as **pending** in the plan, not part of this migrated task list.
