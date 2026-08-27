---

description: "Task list for feature migration (retrospective — feature already shipped)"
---

# Tasks: Reports

**Input**: Design documents from `/specs/025-reports/`

**Prerequisites**: plan.md, spec.md

**Status**: migrated — all tasks below reflect code that already exists in the repository. This is a retrospective record, not pending work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent files, no dependency ordering required
- **[Story]**: US1 = generate a built-in report, US2 = extend with a custom report, US3 = on-screen admin preview

## Phase 1: Abstract Base & Async Pipeline (shared by all stories)

- [x] T001 `spree/core/app/models/spree/report.rb` — abstract base: store/date-range/currency defaults (store-timezone-aware), private-storage attachment, `line_item_class` naming-convention resolution
- [x] T002 `spree/core/app/models/spree/report_line_item.rb` — base row-formatter contract (`attribute`s, `csv_headers`, `to_csv`)
- [x] T003 `spree/core/app/jobs/spree/reports/generate_job.rb` — async generation entry point
- [x] T004 `spree/core/app/subscribers/spree/report_subscriber.rb` — `report.create` event → `generate_async`
- [x] T005 `spree/core/app/mailers/spree/report_mailer.rb` — `report_done` completion email

## Phase 2: Built-In Reports [US1]

- [x] T006 [P] `spree/core/app/models/spree/reports/sales_total.rb` + `spree/core/app/models/spree/report_line_items/sales_total.rb`
- [x] T007 [P] `spree/core/app/models/spree/reports/products_performance.rb` + `spree/core/app/models/spree/report_line_items/products_performance.rb`

## Phase 3: Extension-Point Documentation [US2]

- [x] T008 `docs/developer/how-to/custom-report.mdx` — documents the `Report`/`ReportLineItem` subclass-and-register pattern, including the `vendor` helper for multi-vendor installs
- [x] T009 `Spree.reports` registry (in `spree/core/lib/spree/core/engine.rb`, alongside `Spree.import_types`/`Spree.export_types`) — makes a registered report type selectable in the admin UI without core dispatch changes

## Phase 4: Legacy Admin UI [US1, US3]

- [x] T010 `spree/admin/app/controllers/spree/admin/reports_controller.rb` — report selection, date-range form, CSV download
- [x] T011 `spree/admin/app/controllers/concerns/spree/admin/analytics_concern.rb`
- [x] T012 [P] `spree/admin/app/views/spree/admin/reports/report.html.erb`, `no_report_data.html.erb` — `to_partial_path`/`no_report_data_partial_path` targets

## Phase 5: Event Payload Serialization (shared)

- [x] T013 `spree/api/app/serializers/spree/api/v3/report_serializer.rb` — shapes `report.create`/completion event payloads only, no backing controller
- [x] T014 [P] `spree/api/spec/serializers/spree/api/v3/report_serializer_spec.rb`

## Notes

- Every phase above is already implemented; nothing here is scheduled work.
- Per spec.md's Migration Notes: no Admin API v3 controller and no `packages/dashboard` route/hook/component exist for this feature — same pattern as `021-imports`. Any future SPA migration must design an Admin API contract first.
- Only two built-in report types ship in core; anything beyond `SalesTotal`/`ProductsPerformance` requires an in-house or third-party `Spree::Reports::*` subclass per the documented extension contract.
- Error handling around partial generation/attachment failure was not independently re-verified — flagged, not remediated, as this migration is documentation-only.
</content>
