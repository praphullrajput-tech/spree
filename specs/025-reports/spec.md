# Feature Specification: Reports

**Feature Branch**: `025-reports`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — `spree/core/app/models/spree/report.rb`, `spree/core/app/models/spree/reports/{sales_total,products_performance}.rb`, `spree/admin/app/controllers/spree/admin/reports_controller.rb`, `spree/admin/app/controllers/concerns/spree/admin/analytics_concern.rb`, `docs/developer/how-to/custom-report.mdx`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a built-in report as CSV (Priority: P1)

A store admin wants a Sales Total or Products Performance report for a date range, downloadable as CSV, without writing any code.

**Why this priority**: The only end-user-facing value of the feature — everything else is extension-point plumbing in service of this.

**Independent Test**: Create a `Spree::Reports::SalesTotal` with `date_from`/`date_to`/`currency`, call `generate`, and verify a CSV attachment exists with `line_item_class.csv_headers` as the header row and one data row per matching order.

**Acceptance Scenarios**:

1. **Given** a new report record with `store` set but no explicit dates/currency, **When** it is initialized, **Then** `set_default_values` fills `currency` from the store's default, `date_from` to one month ago (start of day, store timezone), and `date_to` to now (end of day, store timezone).
2. **Given** `report.create` fires (model creation), **When** `Spree::ReportSubscriber` handles the `report.create` event, **Then** `generate_async` enqueues `Spree::Reports::GenerateJob` — generation is not synchronous with record creation.
3. **Given** the job runs, **When** `generate` is called, **Then** it streams `line_items_scope` in batches (`find_in_batches`) through the paired `ReportLineItems::*` formatter class into a temp CSV file, attaches it (private storage), deletes the temp file, and emails the requesting admin (`ReportMailer.report_done`) if one is set.
4. **Given** a report subclass doesn't override `line_items_scope`, **When** `line_items` is called, **Then** `NotImplementedError` is raised — this is an abstract-method contract, not a silently-empty report.

---

### User Story 2 - Extend the reporting system with a custom report (Priority: P2)

A merchant/developer wants a report type Spree doesn't ship (e.g. customer order history) without forking core.

**Why this priority**: The system is explicitly designed as an extension point (per `docs/developer/how-to/custom-report.mdx`) — this is the intended primary usage pattern for anything beyond the two built-ins.

**Independent Test**: Define `Spree::Reports::CustomerOrders < Spree::Report` (overriding `line_items_scope`) and a paired `Spree::ReportLineItems::CustomerOrders < Spree::ReportLineItem` (defining `attribute`s + `csv_headers`/`to_csv`), register it in `Spree.reports`, and verify it appears selectable in the admin reports UI and generates correctly.

**Acceptance Scenarios**:

1. **Given** a report class name `Spree::Reports::Foo`, **When** `line_item_class` is resolved, **Then** it looks up `Spree::ReportLineItems::Foo` by convention (same demodulized name) — the pairing is name-convention-based, not explicitly configured per report.
2. **Given** the report has `vendor` support (multi-vendor extension installed), **When** `line_items_scope` is implemented, **Then** it has access to a `vendor` helper alongside `store`/`date_from`/`date_to`/`currency` (per the how-to guide's helper table) — `Spree::VendorConcern` is conditionally included only `if defined?`.

---

### User Story 3 - Admin views report data in the dashboard before/without downloading (Priority: P3)

An admin wants to see report totals directly in the legacy admin UI (a rendered table), not only via CSV download.

**Why this priority**: Convenience view on top of the same data — the CSV generation path (US1) is the durable/exportable artifact; this is an on-screen preview.

**Independent Test**: Visit the legacy admin reports controller's show/index action for a report type and verify `to_partial_path`/`no_report_data_partial_path` render a populated or empty-state partial appropriately.

**Acceptance Scenarios**:

1. **Given** `line_items_scope` returns no records for the selected date range, **When** the admin view renders, **Then** the `no_report_data_partial_path` ('spree/admin/reports/no_report_data') is used instead of the populated report partial.

### Edge Cases

- What happens if `user` is blank when `generate` completes? `send_report_done_email` no-ops (`return unless user.present?`) — reports can be generated without a requesting admin (e.g. scheduled/system-triggered), silently skipping the notification.
- What happens to the temp CSV file if attaching fails partway? Not verified in this pass — `handle_attachment` deletes the tmp file unconditionally after opening it for attachment, but exception handling around `attachment.attach` itself wasn't traced.
- What happens for very large reports? `find_in_batches` streams rather than loading the full scope into memory — but no explicit size cap or background-job timeout handling was verified.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an abstract `Spree::Report` base class requiring subclasses to implement `line_items_scope`; calling it unimplemented MUST raise `NotImplementedError`.
- **FR-002**: System MUST ship at least two built-in reports: `Spree::Reports::SalesTotal` and `Spree::Reports::ProductsPerformance`.
- **FR-003**: System MUST default `currency`/`date_from`/`date_to` from the report's store when not explicitly provided, using the store's timezone for date boundaries.
- **FR-004**: System MUST generate reports asynchronously — record creation triggers `report.create`, handled by `Spree::ReportSubscriber` to enqueue `Spree::Reports::GenerateJob`, not a synchronous callback.
- **FR-005**: System MUST stream report data via `find_in_batches` rather than loading the full result set into memory when writing the CSV.
- **FR-006**: System MUST store generated CSVs via private attachment storage (`Spree.private_storage_service_name`), consistent with other potentially-sensitive generated files (imports, exports).
- **FR-007**: System MUST email the requesting admin when their report finishes generating, if a `user` is associated with the report.
- **FR-008**: The report/report-line-item pairing MUST be resolvable by naming convention alone (`Spree::Reports::Foo` ↔ `Spree::ReportLineItems::Foo`), enabling third-party reports to register without modifying core dispatch logic.
- **FR-009**: Reports MUST be store-scoped (`Spree::SingleStoreResource`) and optionally vendor-scoped when a multi-vendor extension defines `Spree::VendorConcern`.

### Key Entities

- **Spree::Report**: Abstract STI base — store/date-range/currency parameters, async generation lifecycle, CSV writing, attachment handling, completion email.
- **Spree::Reports::{SalesTotal, ProductsPerformance}**: The two shipped concrete report types.
- **Spree::ReportLineItem** (+ per-report subclasses, e.g. `ReportLineItems::SalesTotal`): Row formatter — defines typed `attribute`s, `csv_headers`, and `to_csv` for one report's output shape.
- **Spree.reports**: Registry array (mirrors `Spree.import_types`/`Spree.export_types` pattern) that makes a report type selectable in the admin UI.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Report` base + 2 concrete reports, `ReportLineItem` + subclasses, `Reports::GenerateJob`, `ReportSubscriber`, `ReportMailer` |
| `spree/api` (Store/Admin API v3) | Partial | Only `Spree::Api::V3::ReportSerializer` exists (event-payload shaping for `report.create`/completion) — **no `spree/api/v3/admin/reports_controller.rb` found** |
| `packages/dashboard` (admin SPA) | No | No route/hook found — confirmed absent by directory search |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | No | No report-related client methods found |
| `docs/plans/` | No | No dedicated plan doc found; `docs/developer/how-to/custom-report.mdx` documents the extension contract but is a how-to guide, not an architecture plan |

### API Contract

Not applicable in the REST/CRUD sense — reports are generated and viewed entirely through the legacy `spree/admin` Rails engine. `ReportSerializer` exists only to shape event payloads, mirroring the same pattern found in `020-webhooks` and `021-imports`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can generate a Sales Total or Products Performance report for an arbitrary date range and download a CSV without any code changes.
- **SC-002**: A third-party report class following the `Report`/`ReportLineItem` naming convention appears in the admin UI and generates correctly once registered in `Spree.reports` — no core dispatch code changes required.
- **SC-003**: Report generation does not block the request that creates the report record (async via `GenerateJob`).

## Assumptions

- "Feature" here means the existing reporting subsystem as built today — this document reverse-engineers current behavior for spec-kit tracking, not a proposed redesign.
- `Spree.reports` registry array (mirroring `import_types`/`export_types`) is assumed to exist in `spree/core/lib/spree/core/engine.rb` alongside the two built-ins, consistent with the sibling registries found in `021-imports`/`022-exports` — not independently re-verified line-by-line in this pass.
- Multi-vendor `vendor` scoping is an optional, conditionally-loaded capability (`if defined?(Spree::VendorConcern)`), not present in a standard installation.

## Migration Notes

- **Gap — no Admin API v3 endpoint, no dashboard SPA presence**: Like Imports (`021`), Reports has zero `packages/dashboard` footprint and no Admin API v3 controller — confirmed absent by directory search. This is the same "legacy-admin-only, no REST surface" pattern seen across several back-office extension points in this monorepo; any future SPA migration of this feature must design an Admin API contract first, per Constitution Principle II.
- **Gap — only 2 built-in report types ship in core**: `SalesTotal` and `ProductsPerformance` are the entire out-of-the-box catalog; anything else (customer-order history, inventory-turnover, etc., as used in the how-to guide's own examples) requires a third-party extension or in-house `Spree::Reports::*` subclass.
- **Gap — error handling around attachment/generation failure not traced**: This pass did not verify what happens if CSV generation or attachment raises partway through `generate` (e.g. does the report end up in a visibly-failed state, or silently incomplete?). Flagged for follow-up.
- **Not migrated**: no code changes were made. This is a reverse-engineered spec for existing, already-shipped behavior.
</content>
