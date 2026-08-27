# Feature Specification: Imports

**Feature Branch**: `021-imports`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — `spree/core/app/models/spree/import.rb`, `spree/core/app/models/spree/imports/*.rb`, `spree/core/app/services/spree/imports/row_processors/*.rb`, `spree/core/app/jobs/spree/imports/*.rb`, `spree/admin/app/controllers/spree/admin/import*_controller.rb`, `spree/admin/app/subscribers/spree/admin/import*_subscriber.rb`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bulk-import a product catalog via CSV (Priority: P1)

A store admin has hundreds or thousands of SKUs in a spreadsheet and wants to load them into Spree without hand-entering each product, including multi-variant products.

**Why this priority**: The core value proposition of the feature — the only import type with a dedicated dashboard entry point (`_import_button.html.erb` on the products index) and documented user guide.

**Independent Test**: Create a `Spree::Imports::Products` record with a CSV attachment, drive it through `pending → mapping → completed_mapping → processing → completed`, and verify the resulting `Spree::Product`/`Spree::Variant` rows match the CSV.

**Acceptance Scenarios**:

1. **Given** a CSV file uploaded to a new `Spree::Imports::Products` import, **When** `start_mapping` fires, **Then** `create_mappings` builds one `Spree::ImportMapping` per schema field and auto-assigns a matching CSV column where the header name matches.
2. **Given** all required schema fields are mapped, **When** `complete_mapping` fires, **Then** `create_rows_async` enqueues `Spree::Imports::CreateRowsJob`, which parses the CSV and creates one `Spree::ImportRow` per line.
3. **Given** rows exist and `start_processing` fires, **When** `process_rows_async` runs, **Then** each row is processed by `Spree::ImportRowProcessors::ProductVariant`, which finds-or-creates the `Product`, and its `Variant`(s) for multi-variant rows, from the mapped column values.
4. **Given** the model class supports metafields, **When** `schema_fields` is computed, **Then** each `Spree::MetafieldDefinition` for that model is appended as an additional importable column (`definition.csv_header_name`).
5. **Given** the import has more rows than `Spree::Config[:large_import_threshold]`, **When** processing begins, **Then** it is treated as a `large_import?` — no per-row UI broadcast, bulk processing instead.
6. **Given** processing finishes, **When** the import transitions to `completed`, **Then** `Spree::Admin::ImportSubscriber` (listening to `import.completed`) sends a completion email and updates the admin UI's loader — not the state machine callback itself.

---

### User Story 2 - Bulk-import customers (Priority: P2)

An admin migrating from another platform wants to load a customer list (name, email, addresses) without manual entry.

**Why this priority**: Same mechanism as products, second-most-common import type, but with no dedicated dashboard entry point found — likely reached generically via the imports index.

**Independent Test**: Create a `Spree::Imports::Customers` import, verify `model_class` resolves to `Spree.user_class` (not a literal `Spree::Customer` model), and that `Spree::ImportRowProcessors::Customer` creates users + addresses from mapped rows.

**Acceptance Scenarios**:

1. **Given** `type == 'Spree::Imports::Customers'`, **When** `model_class` is called, **Then** it returns `Spree.user_class` rather than trying to constantize `Spree::Customer` — a special case in `Spree::Import#model_class` and `.model_class` (class method).

---

### User Story 3 - Bulk-import product translations (Priority: P3)

A store operating in multiple locales wants to load translated product name/description text in bulk rather than editing each product's translation tab individually.

**Why this priority**: Narrower, locale-specific use case; also the type used internally by the sample-data loader (`026-sample-data-seeds`) to seed demo translations.

**Independent Test**: Create a `Spree::Imports::ProductTranslations` import and verify `Spree::ImportRowProcessors::ProductTranslation` writes to the correct Mobility-backed locale columns for existing products (does not create new products).

**Acceptance Scenarios**:

1. **Given** a CSV row referencing an existing product's slug/SKU and a target locale, **When** the row is processed, **Then** the product's translated name/description for that locale is updated — the row processor does not create products, only translations.

### Edge Cases

- What happens if the CSV `type` isn't in `Spree.import_types`? `ensure_whitelisted_type` rejects it at the model-validation layer.
- What happens if the attachment isn't a CSV? `ensure_attachment_content_type` requires `text/csv`.
- What happens to unmapped file columns? Exposed via `unmapped_file_columns` for the admin UI to surface, but they don't block processing once all *required* fields are mapped (`mapping_done?`).
- What happens on a per-row processing failure? Not verified in this pass — see Migration Notes.
- What happens to `import_row_subscriber.rb`'s responsibilities vs. the state machine's own callbacks? Not fully disambiguated in this pass — see Migration Notes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support exactly three import types, registered via `Spree.import_types`: `Spree::Imports::Products`, `Spree::Imports::ProductTranslations`, `Spree::Imports::Customers`.
- **FR-002**: Every import MUST go through the state machine `pending → mapping → completed_mapping → processing → completed` (or `failed` from any state), with `Spree::ImportMapping` rows created automatically on entering `mapping`.
- **FR-003**: System MUST auto-assign CSV columns to schema fields where header names match, via `ImportMapping#try_to_auto_assign_file_column`, reducing manual mapping work.
- **FR-004**: System MUST dynamically extend the importable schema with the target model's `Spree::MetafieldDefinition`s when the model includes `Spree::Metafields`.
- **FR-005**: System MUST create `Spree::ImportRow` records asynchronously (`CreateRowsJob`) rather than parsing the whole CSV synchronously in the request/transition.
- **FR-006**: System MUST process rows via a per-type `Spree::ImportRowProcessors::*` class (`Base` + `ProductVariant`/`Customer`/`ProductTranslation` subclasses), resolved dynamically from `Import#row_processor_class`.
- **FR-007**: System MUST switch to bulk processing (no per-row UI broadcast) when `rows_count >= Spree::Config[:large_import_threshold]`.
- **FR-008**: System MUST publish an `import.completed` lifecycle event on completion, consumed by `Spree::Admin::ImportSubscriber` for email notification and admin-UI loader updates (decoupled from the state machine transition itself).
- **FR-009**: Import data (attachment) MUST be stored via `Spree.private_storage_service_name` (private, not public storage) since imports may contain PII (customer imports).

### Key Entities

- **Spree::Import**: Base STI class — state machine, CSV header parsing, mapping/row/processor orchestration, `owner` (Store/Vendor, polymorphic) + `user` (importing admin) associations.
- **Spree::Imports::{Products,ProductTranslations,Customers}**: STI subclasses, each pairing with an `Spree::ImportSchemas::*` (field definitions) and `Spree::ImportRowProcessors::*` (row-to-model logic).
- **Spree::ImportMapping**: One row per schema field, mapping it to a CSV column (`file_column`).
- **Spree::ImportRow**: One row per CSV data line, processed independently (or in batches for large imports).
- **Spree::ImportRowProcessors::Base/ProductVariant/Customer/ProductTranslation**: Row-level logic converting mapped column values into model attributes/records.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Import` + STI subclasses, `ImportSchemas::*`, `ImportRowProcessors::*`, `Imports::{CreateRowsJob,ProcessRowsJob,ProcessGroupJob,AssignTagsJob,CreateCategoriesJob,BaseJob}` |
| `spree/api` (Store/Admin API v3) | Partial | Only `Spree::Api::V3::ImportSerializer`/`ImportRowSerializer` exist (used for the `import.completed` event payload) — **no `spree/api/v3/admin/imports_controller.rb` was found**; imports have no REST-managed API surface today |
| `packages/dashboard` (admin SPA) | No | No import route/hook found in `packages/dashboard` — confirmed by directory search |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | No | No hand-written or generated import-management client methods found |
| `docs/plans/` | No | No dedicated plan doc found for this feature |

### API Contract

Not applicable in the REST sense — imports are managed entirely through the **legacy `spree/admin` Rails engine** (`ImportsController`, `ImportMappingsController`, `ImportRowsController`, Turbo Frames + `import_form_controller.js` Stimulus controller). The `Spree::Api::V3::Import{,Row}Serializer` pair exists only to shape the `import.completed` webhook/event payload, not to back a CRUD endpoint.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A CSV of N product rows, once mapped, results in the corresponding N `Spree::Product`/`Spree::Variant` records (or updates) without manual per-row admin entry.
- **SC-002**: An import above `Spree::Config[:large_import_threshold]` completes without generating N individual per-row broadcast messages (bulk-mode).
- **SC-003**: On completion, the importing admin receives an email notification and the admin UI reflects `completed` status without a page refresh (Turbo Stream update).

## Assumptions

- "Feature" here means the existing import subsystem as built today — a reverse-engineered specification for spec-kit tracking, not a proposed redesign.
- `Spree.user_class`/`Spree.admin_user_class` configured per standard conventions (per `CLAUDE.md`).
- Per-row failure handling, retry semantics, and the exact division of labor between `Spree::Admin::ImportSubscriber` and `Spree::Admin::ImportRowSubscriber` were not independently verified — see Migration Notes.

## Migration Notes

- **Gap — no Admin API v3 endpoint**: Imports are entirely legacy-Rails-admin-only. There is no `spree/api/v3/admin/imports_controller.rb`, and `packages/dashboard` has zero presence for this domain (confirmed via directory search — no `import` route, hook, or component). This is a real gap for the 6.0 SPA migration, not just a documentation gap: the admin API team would need to design an async-upload-and-status-poll (or webhook-driven) contract before this can move to the dashboard, since the current UX depends on Turbo Streams for live row-count/status updates.
- **Gap — per-row failure handling not verified**: Unlike `026-sample-data-seeds`'s `ImportRunner` (which explicitly rescues per-row and counts failures), this pass did not verify whether `Spree::ImportRowProcessors::*` classes rescue and record row-level failures or let exceptions propagate. Flagged for follow-up, not asserted either way.
- **Gap — subscriber responsibility split unclear**: Both `Spree::Admin::ImportSubscriber` and `Spree::Admin::ImportRowSubscriber` exist; this pass did not fully trace which handles which lifecycle event(s) (e.g. row-level progress broadcast vs. import-level completion). Flagged for follow-up.
- **Not migrated**: no code changes were made. This is a reverse-engineered spec for existing, already-shipped behavior.
</content>
