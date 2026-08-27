# Implementation Plan: Reports

**Branch**: `025-reports` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-reports/spec.md`

**Note**: This plan is reverse-engineered from an already-shipped feature (brownfield migration), not authored ahead of implementation.

## Summary

An extension-point reporting system: an abstract `Spree::Report` STI base class (store/date-range/currency parameters, async CSV generation, private attachment storage, completion email) paired by naming convention with a `Spree::ReportLineItem` row formatter. Two built-in reports ship (`SalesTotal`, `ProductsPerformance`); third parties add reports by subclassing both halves and registering in `Spree.reports` — no core dispatch code changes required. Generation is asynchronous (`report.create` event → `ReportSubscriber` → `GenerateJob`). Entirely legacy-Rails-admin-managed; no Admin API v3 controller or dashboard SPA route exists.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine) — `spree/core` (model/services/job) + `spree/admin` (the only UI).

**Primary Dependencies**: `Spree::SingleStoreResource` (store scoping), optional `Spree::VendorConcern` (multi-vendor scoping, conditionally loaded), Active Storage (`has_one_attached :attachment`, private service), ActiveJob (`Reports::GenerateJob`), Rails events (`publish_event`/`ReportSubscriber`), `ActiveModel::Attributes` (typed `ReportLineItem` columns per the how-to guide).

**Storage**: PostgreSQL/SQLite3 via ActiveRecord; generated CSV stored via `Spree.private_storage_service_name`.

**Testing**: RSpec expected under `spree/core/spec/models/spree/report*_spec.rb` and `spree/admin/spec/controllers/spree/admin/reports_controller_spec.rb` (not individually re-verified in this pass); `spree/api/spec/serializers/spree/api/v3/report_serializer_spec.rb` confirmed present.

**Target Platform**: Legacy `spree/admin` Rails engine only — report selection, on-screen preview (`to_partial_path`/`no_report_data_partial_path`), and CSV download.

**Project Type**: Monorepo — `spree/core` (base classes, built-in reports, job, subscriber, mailer) + `spree/admin` (controller, analytics concern, views) + `spree/api` (event-payload serializer only).

**Performance Goals**: Streams report rows via `find_in_batches` rather than loading the full result set — the only performance-relevant design decision confirmed in source.

**Constraints**: Reports are store-scoped; CSV generation happens off the request cycle (async job) so large date ranges don't block the triggering request.

**Scale/Scope**: 1 abstract base + 2 built-in report/line-item pairs; open-ended for third-party extensions via the documented convention.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: `spree/core` owns the extension-point contract and built-ins; `spree/admin` owns the only UI; `spree/api` only shapes event payloads. No `packages/dashboard` crossing exists. PASS.
- **II. Admin API Is the Only Frontend Data Source**: N/A today — no dashboard SPA surface exists (confirmed absent by directory search). Same known gap as `021-imports`; flagged in Migration Notes, not a violation of existing code.
- **III. Read/Write Field Symmetry**: N/A — no write-capable controller/`permitted_params` exists for this feature; `ReportSerializer` is read/event-payload-only.
- **IV. Test-Backed**: `spree/api` serializer spec confirmed; `spree/core`/`spree/admin` spec presence for this specific feature was not individually re-verified in this pass — flagged, not asserted missing.
- **V. Translations and Prefixed IDs**: `has_prefix_id :rep` in place. Report display name uses `Spree.t("report_names.#{type.demodulize.underscore}")` — i18n-backed, extension-friendly (each new report type just needs its own translation key).
- **VI. `docs/plans/` for Architectural Changes**: No plan doc exists; none needed for this migration (documentation-only). `docs/developer/how-to/custom-report.mdx` already documents the extension contract for third-party authors.

No violations. Complexity Tracking table intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/025-reports/
├── plan.md              # This file
├── spec.md              # Reverse-engineered specification
└── tasks.md             # Reverse-engineered task list (all complete)
```

### Source Code (repository root)

```text
# spree/core — abstract base, built-ins, async pipeline
spree/core/
├── app/models/spree/report.rb                          # abstract base: dates/currency defaults, generate/generate_csv/handle_attachment
├── app/models/spree/reports/{sales_total,products_performance}.rb
├── app/models/spree/report_line_item.rb                # (referenced by report.rb — base formatter class)
├── app/models/spree/report_line_items/{sales_total,products_performance}.rb  # (paired by naming convention)
├── app/jobs/spree/reports/generate_job.rb
├── app/subscribers/spree/report_subscriber.rb           # report.create → generate_async
└── app/mailers/spree/report_mailer.rb                   # report_done

# spree/admin — the only management/viewing UI (legacy)
spree/admin/
├── app/controllers/spree/admin/reports_controller.rb
├── app/controllers/concerns/spree/admin/analytics_concern.rb
└── app/views/spree/admin/reports/{report,no_report_data}.html.erb  # to_partial_path targets

# spree/api — event-payload serialization only, no CRUD controller
spree/api/app/serializers/spree/api/v3/report_serializer.rb
spree/api/spec/serializers/spree/api/v3/report_serializer_spec.rb

# [NOT PRESENT] spree/api/v3/admin/reports_controller.rb — no Admin API endpoint
# [NOT PRESENT] packages/dashboard — no route/hook exists
```

**Structure Decision**: Backend (`spree/core`) + legacy admin (`spree/admin`) only, mirroring the same "no REST surface, no SPA presence" shape found in `021-imports`. No `packages/dashboard`, `dashboard-ui`, `dashboard-core`, `sdk`, or `admin-sdk` involvement exists today.

## Complexity Tracking

*No Constitution Check violations for existing code — table intentionally empty. The Admin-API/SPA gap is tracked as a Migration Note, not a violation.*
</content>
