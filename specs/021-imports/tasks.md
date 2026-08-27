---

description: "Task list for feature migration (retrospective — feature already shipped)"
---

# Tasks: Imports

**Input**: Design documents from `/specs/021-imports/`

**Prerequisites**: plan.md, spec.md

**Status**: migrated — all tasks below reflect code that already exists in the repository. This is a retrospective record, not pending work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent files, no dependency ordering required
- **[Story]**: US1 = product import, US2 = customer import, US3 = product translation import

## Phase 1: Core Import Model & State Machine (shared by all stories)

- [x] T001 `spree/core/app/models/spree/import.rb` — STI base: state machine (`pending→mapping→completed_mapping→processing→completed`/`failed`), CSV header parsing, mapping/row/processor orchestration, private-storage attachment
- [x] T002 [P] `spree/core/app/models/spree/import_mapping.rb`, `import_row.rb` — per-field mapping and per-CSV-line row records
- [x] T003 [P] `spree/core/app/jobs/spree/imports/base_job.rb`, `create_rows_job.rb`, `process_rows_job.rb`, `process_group_job.rb`, `assign_tags_job.rb`, `create_categories_job.rb`
- [x] T004 `spree/core/app/services/spree/imports/row_processors/base.rb` — shared row-processor contract

## Phase 2: Product Import [US1]

- [x] T005 `spree/core/app/models/spree/imports/products.rb`, `spree/core/app/models/spree/import_schemas/products.rb`
- [x] T006 `spree/core/app/services/spree/imports/row_processors/product_variant.rb` (310 lines) — multi-variant row handling, find-or-create Product/Variant
- [x] T007 [P] `spree/admin/app/views/spree/admin/products/_import_button.html.erb` — entry point on the products index
- [x] T008 Metafield schema extension — `Import#schema_fields` appends `Spree::MetafieldDefinition.for_resource_type` columns when `model_class` includes `Spree::Metafields`

## Phase 3: Customer Import [US2]

- [x] T009 `spree/core/app/models/spree/imports/customers.rb`, `spree/core/app/models/spree/import_schemas/customers.rb`
- [x] T010 `spree/core/app/services/spree/imports/row_processors/customer.rb` — special-cased `model_class` resolution to `Spree.user_class`

## Phase 4: Product Translation Import [US3]

- [x] T011 `spree/core/app/models/spree/imports/product_translations.rb`, `spree/core/app/models/spree/import_schemas/product_translations.rb`
- [x] T012 `spree/core/app/services/spree/imports/row_processors/product_translation.rb` — Mobility-backed locale column writes on existing products only

## Phase 5: Legacy Admin UI (shared, all stories)

- [x] T013 [P] `spree/admin/app/controllers/spree/admin/imports_controller.rb` — upload + lifecycle transitions
- [x] T014 [P] `spree/admin/app/controllers/spree/admin/import_mappings_controller.rb` — column-mapping step
- [x] T015 [P] `spree/admin/app/controllers/spree/admin/import_rows_controller.rb` — row status/retry
- [x] T016 [P] `spree/admin/app/javascript/spree/admin/controllers/import_form_controller.js` — Stimulus wizard controller
- [x] T017 [P] `spree/admin/app/subscribers/spree/admin/import_subscriber.rb` — `import.completed` → email + UI loader update
- [x] T018 [P] `spree/admin/app/subscribers/spree/admin/import_row_subscriber.rb` — row-level progress broadcast (exact division of labor vs. T017 not independently re-verified, per spec.md Migration Notes)

## Phase 6: Event Payload Serialization (shared, all stories)

- [x] T019 [P] `spree/api/app/serializers/spree/api/v3/import_serializer.rb`, `import_row_serializer.rb` — shape the `import.completed` event payload only, no backing controller

## Notes

- Every phase above is already implemented; nothing here is scheduled work.
- Per spec.md's Migration Notes, **no Admin API v3 controller and no `packages/dashboard` route/hook/component exist for this feature** — confirmed by directory search, not just undocumented. This is the single largest gap for any future 6.0 SPA migration of this feature.
- Per-row failure handling and the `ImportSubscriber`/`ImportRowSubscriber` responsibility split were not independently re-verified in this pass — flagged, not remediated.
</content>
