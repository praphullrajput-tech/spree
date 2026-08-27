# Implementation Plan: Imports

**Branch**: `021-imports` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-imports/spec.md`

**Note**: This plan is reverse-engineered from an already-shipped feature (brownfield migration), not authored ahead of implementation.

## Summary

A state-machine-driven CSV import pipeline (`Spree::Import` STI base + `Products`/`ProductTranslations`/`Customers` subclasses) that walks a `pending → mapping → completed_mapping → processing → completed` lifecycle: auto-mapping CSV columns to schema fields (including dynamic metafield columns), creating one `Spree::ImportRow` per CSV line asynchronously, then processing each row through a per-type `Spree::ImportRowProcessors::*` class. Entirely managed through the legacy `spree/admin` Rails engine (Turbo Frames + Stimulus) — no Admin API v3 controller or dashboard SPA presence exists for this feature today.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines) — `spree/core` (model/state-machine/row-processor logic) and `spree/admin` (the only management UI).

**Primary Dependencies**: `state_machines-activerecord` (import lifecycle), Active Storage (`has_one_attached :attachment`, private storage service), Sidekiq/ActiveJob (`CreateRowsJob`, `ProcessRowsJob`, `ProcessGroupJob`, `AssignTagsJob`, `CreateCategoriesJob`), Turbo Streams (live row/status updates in the legacy admin UI), `Spree::Metafields` (dynamic schema extension).

**Storage**: PostgreSQL/SQLite3 via ActiveRecord; CSV attachment stored via `Spree.private_storage_service_name` (not public storage, since customer imports may carry PII).

**Testing**: RSpec (`spree/core/spec/models/spree/import*_spec.rb`, `spree/core/spec/services/spree/imports/row_processors/*_spec.rb` if present, `spree/admin/spec/controllers/spree/admin/import*_controller_spec.rb`, `spree/admin/spec/subscribers/spree/admin/import*_subscriber_spec.rb`). No frontend/Vitest/Playwright coverage — no dashboard SPA surface exists.

**Target Platform**: Legacy `spree/admin` Rails engine only (Turbo Frame-based multi-step wizard: upload → map columns → process). No REST API surface, no SPA route.

**Project Type**: Monorepo — `spree/core` (import model/state machine/row processors/jobs) + `spree/admin` (the entire UI: controllers, subscribers, Stimulus controller, views) + `spree/api` (serializers only, for the `import.completed` event payload — not a CRUD endpoint).

**Performance Goals**: Large imports (above `Spree::Config[:large_import_threshold]`) skip per-row UI broadcasts and use bulk processing to avoid overwhelming Turbo Streams/ActionCable with thousands of individual updates.

**Constraints**: CSV attachment content-type restricted to `text/csv`; import `type` restricted to `Spree.import_types` allowlist; attachment storage must be private (PII risk for customer imports).

**Scale/Scope**: 3 import types (Products, ProductTranslations, Customers), 4 row-processor classes (Base + 3 concrete), 6 background job classes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: `spree/core` owns the model/state-machine/processing logic; `spree/admin` owns the only UI. No `packages/dashboard` involvement, so no cross-boundary coupling to worry about there. PASS.
- **II. Admin API Is the Only Frontend Data Source**: **N/A today, but a known constraint for future work** — since no dashboard SPA UI exists yet, this principle doesn't currently apply. If imports are ever brought into `packages/dashboard`, an Admin API v3 endpoint MUST be built first per this principle — see spec.md Migration Notes gap.
- **III. Read/Write Field Symmetry**: N/A — no controller `permitted_params` exists for this feature; the only serializers (`ImportSerializer`/`ImportRowSerializer`) are read-only, used for event payloads.
- **IV. Test-Backed**: RSpec coverage exists for the legacy admin controllers/subscribers; row-processor-level and job-level spec coverage was not independently verified in this pass (see spec.md Migration Notes).
- **V. Translations and Prefixed IDs**: `Spree::Import` uses `has_prefix_id :imp` — prefixed IDs already in place. Admin UI strings go through `Spree.t`/legacy i18n, not i18next (this is a legacy-admin-only feature, no dashboard i18next keys apply).
- **VI. `docs/plans/` for Architectural Changes**: No plan doc exists for this feature currently. If the Admin-API/SPA gap identified above is addressed, a `docs/plans/` entry should be created at that time per this principle.

No violations for the current (legacy-admin-only) state. The Admin API/SPA gap is flagged as future work, not a violation of existing code.

## Project Structure

### Documentation (this feature)

```text
specs/021-imports/
├── plan.md              # This file
├── spec.md              # Reverse-engineered specification
└── tasks.md             # Reverse-engineered task list (all complete)
```

### Source Code (repository root)

```text
# spree/core — import model, state machine, row processors, jobs
spree/core/
├── app/models/spree/import.rb                              # STI base, state machine
├── app/models/spree/imports/{products,product_translations,customers}.rb
├── app/models/spree/import_schemas/{products,product_translations,customers}.rb
├── app/models/spree/import_mapping.rb, import_row.rb        # (referenced by import.rb associations)
├── app/services/spree/imports/row_processors/
│   ├── base.rb
│   ├── product_variant.rb    # 310 lines — largest, handles multi-variant rows
│   ├── customer.rb
│   └── product_translation.rb
└── app/jobs/spree/imports/
    ├── base_job.rb, create_rows_job.rb, process_rows_job.rb
    ├── process_group_job.rb, assign_tags_job.rb, create_categories_job.rb

# spree/admin — the only management UI (legacy, Turbo/Stimulus)
spree/admin/
├── app/controllers/spree/admin/{imports,import_mappings,import_rows}_controller.rb
├── app/subscribers/spree/admin/{import,import_row}_subscriber.rb
├── app/javascript/spree/admin/controllers/import_form_controller.js
├── app/views/spree/admin/{imports,import_mappings,import_rows}/
├── app/views/spree/admin/products/_import_button.html.erb   # entry point, products index only
└── spec/controllers/spree/admin/import{,_rows}_controller_spec.rb
    spec/subscribers/spree/admin/import{,_row}_subscriber_spec.rb

# spree/api — event-payload serialization only, no CRUD controller
spree/api/app/serializers/spree/api/v3/{import,import_row}_serializer.rb
spree/api/spec/serializers/spree/api/v3/{import,import_row}_serializer_spec.rb

# [NOT PRESENT] packages/dashboard — no import route/hook/component exists
# [NOT PRESENT] packages/sdk / packages/admin-sdk — no import client methods exist
```

**Structure Decision**: Backend (`spree/core`) + legacy admin (`spree/admin`) only. No `packages/dashboard`, `dashboard-ui`, `dashboard-core`, `sdk`, or `admin-sdk` involvement exists today — confirmed absent by directory search, not merely out of scope.

## Complexity Tracking

*No Constitution Check violations for existing code — table intentionally empty. The Admin-API/SPA gap is tracked as a Migration Note, not a violation.*
</content>
