# Feature Specification: Exports

**Feature Branch**: `022-exports`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — `spree/core/app/models/spree/export.rb`, `spree/core/app/models/spree/exports/*.rb`, `spree/core/app/presenters/spree/csv/*.rb`, `spree/core/app/jobs/spree/exports/generate_job.rb`, `spree/api/app/controllers/spree/api/v3/admin/exports_controller.rb`, `spree/api/app/serializers/spree/api/v3/{,admin/}export_serializer.rb`, `packages/dashboard-core/src/components/export-button.tsx`, `packages/dashboard-core/src/hooks/use-export.ts`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Export the product catalog to CSV (Priority: P1)

A store admin on the products list wants a CSV of the catalog (or a filtered subset) to hand off to a supplier, import into another tool, or audit offline.

**Why this priority**: Products is the most complex export type (multi-line CSV for variants, metafields, translations) and the one referenced by two related export types (`ProductTranslations`).

**Independent Test**: From the products index in the dashboard, click Export, choose "all" or "filtered", and verify the resulting CSV has `Spree::CSV::ProductVariantPresenter::CSV_HEADERS` plus one column per active `Spree::MetafieldDefinition` for `Spree::Product`, with one row per variant.

**Acceptance Scenarios**:

1. **Given** an admin clicks "Export" → "Export all" on the products page, **When** the export is created with no `search_params`, **Then** `Spree::Exports::Products#scope` excludes archived products and `Spree::Exports::GenerateJob` writes a multi-line CSV (one row per variant, including master) via `Spree::Export#generate_csv`.
2. **Given** an admin has an active filter/search on the products table, **When** they choose "Export filtered", **Then** the SPA sends the current filters/search as a Ransack `search_params` hash (`filtersToRansack`) and the export scopes to exactly those records.
3. **Given** the export finishes, **When** the SPA polls `GET /api/v3/admin/exports/:id` and receives `done: true`, **Then** it fetches `download_url` and triggers a browser download of the CSV.
4. **Given** the export takes longer than the client poll timeout (5 minutes), **When** the poll gives up, **Then** the UI falls back to the email notification (`Spree::ExportMailer.export_done`) instead of failing silently.

---

### User Story 2 - Export orders and customers for accounting/CRM (Priority: P2)

An admin needs order line-item detail or the full customer list for external accounting, CRM import, or marketing segmentation.

**Why this priority**: Second and third most common export destinations in the dashboard (orders index, customers index) after products; same mechanism, different presenters.

**Independent Test**: Create a `Spree::Exports::Orders` (or `Spree::Exports::Customers`) export via the Admin API, verify `csv_headers` matches `Spree::CSV::OrderLineItemPresenter::HEADERS` (or `CustomerPresenter::HEADERS`) plus metafield columns, and that `scope_includes` avoids N+1s across the association chain each presenter reads.

**Acceptance Scenarios**:

1. **Given** an `Orders` export with `multi_line_csv? == true`, **When** `generate_csv` runs, **Then** each order contributes one CSV row per line item (via `record.to_csv(store)`), not one row per order.
2. **Given** a `Customers` export, **When** `Spree::CSV::CustomerPresenter#call` builds a row, **Then** it includes computed fields (`amount_spent_in`, `completed_orders.count`) alongside address and metafield data.
3. **Given** either export type, **When** a CSV cell value begins with `=`, `+`, `-`, `@`, tab, CR, or LF, **Then** `Spree::CSV::FormulaSanitizer` prefixes it with an apostrophe so spreadsheet software does not evaluate it as a formula (CSV-injection defense).

---

### User Story 3 - Programmatic / app-driven exports without dashboard UI (Priority: P3)

A third-party app or internal automation using a secret Admin API key needs gift card, newsletter-subscriber, coupon-code, or product-translation CSVs — data sets not surfaced as a dashboard button today.

**Why this priority**: Lower priority because there is no first-party dashboard entry point for these four types; they exist and are reachable only via direct Admin API calls (or a custom integration), gated by scopes.

**Independent Test**: Using a secret API key scoped `read_customers`, `POST /api/v3/admin/exports` with `type: "Spree::Exports::GiftCards"` (or `NewsletterSubscribers`), poll until `done`, and `GET .../download`. Repeat with an unscoped key and confirm the type is excluded from `index` and the create is rejected.

**Acceptance Scenarios**:

1. **Given** a request with no `user` (secret-API-key caller), **When** the export completes, **Then** `send_export_done_email` is skipped (`return if user.blank?`) — apps are expected to poll, not receive email.
2. **Given** an API key without `read_promotions`, **When** it lists exports, **Then** `Spree::Exports::CouponCodes` entries are filtered out of the `index` response (`ExportsController#readable_export_types`), because `CouponCodes.required_scope` is `:promotions`.
3. **Given** a `ProductTranslations` export, **When** the store has more than one supported locale, **Then** `generate_csv` is overridden to call `product.to_translation_csv(store, locales)` per product instead of the base single-locale `to_csv`.

### Edge Cases

- What happens when `record_selection == 'all'`? `clear_search_params` (a `before_create` callback) discards any `search_params` so an "export all" request can't be contaminated by stale filter state.
- What happens when `search_params` contains a prefixed ID (e.g. `promotion_id_eq: 'promo_xxx'`)? `decode_prefixed_id_filters` transparently decodes any string/array value that looks like a prefixed ID back to the raw DB ID before Ransack runs, since Ransack itself has no concept of prefixed IDs.
- What happens if an export's `type` doesn't resolve to a registered class? `ExportsController#build_resource` falls back to the base `Spree::Export` class, which fails presence validation on `type` in practice, and `scoped_resource_name` falls back to `:all`, so only a `read_all`/`write_all`-scoped key can even attempt it.
- What happens to an in-flight export's `attachment` on retry? `GenerateJob` explicitly opts out of retries for most transient errors is wrong — actually it retries a narrow list once, but each retry re-attaches a fresh ActiveStorage blob and re-enqueues the completion email; the job comment documents this is not fully retry-safe.
- What happens when `attachment` is `attached?` but the underlying blob was purged (e.g. by a retention sweep)? Serializer attributes (`filename`, `byte_size`) safe-navigate through `blob&.`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support exactly seven export types, registered via `Spree.export_types`: `Products`, `ProductTranslations`, `Orders`, `Customers`, `GiftCards`, `NewsletterSubscribers`, `CouponCodes`.
- **FR-002**: System MUST generate CSV asynchronously (`Spree::Exports::GenerateJob`, enqueued from `generate_async` in response to the `export.create` lifecycle event), never synchronously in the request cycle.
- **FR-003**: System MUST scope every export to the current store (`for_store`), and additionally to the current vendor when present (`for_vendor`) and to `current_ability` (CanCanCan `accessible_by`), never returning cross-store or cross-tenant data.
- **FR-004**: System MUST support two record-selection modes — `filtered` (apply `search_params` via Ransack) and `all` (no filter, `search_params` cleared before save) — set via the `record_selection` virtual attribute.
- **FR-005**: System MUST append one CSV column per active `Spree::MetafieldDefinition` for the export's model class (except `CouponCodes` and `ProductTranslations`, whose presenters don't mix in `MetafieldsHelper`/don't call `metafields_headers`).
- **FR-006**: System MUST sanitize every CSV cell against formula injection (`Spree::CSV::FormulaSanitizer`) before writing, for both single-line and multi-line (`to_csv`/`to_translation_csv`) record serialization.
- **FR-007**: System MUST attach the generated file via `has_one_attached :attachment` using `Spree.private_storage_service_name` (private storage, not public), and stream downloads through the Admin API controller rather than redirecting to a signed ActiveStorage URL (so the SPA's same-origin JWT auth still applies).
- **FR-008**: System MUST gate each export type's create/view/download/list-visibility by an Admin API key scope derived from `Export.required_scope` (`read_<scope>`, e.g. `Spree::Exports::CouponCodes.required_scope == :promotions`); unmapped types require `read_all`/`write_all`.
- **FR-009**: System MUST skip the completion email when the export has no associated `user` (secret-API-key-created exports), since there is no human inbox to notify.
- **FR-010**: System MUST decode prefixed IDs appearing inside an arbitrary `search_params` Ransack hash back to raw DB IDs before running the query, since Ransack predicates operate on raw column values.

### Key Entities

- **Spree::Export**: Base STI class — store/vendor/user associations, CSV generation orchestration, Ransack-based filtered scope, ActiveStorage attachment, lifecycle events (`export.create`, prefix `EF` numbers, prefixed ID `exp_`).
- **Spree::Exports::{Products,ProductTranslations,Orders,Customers,GiftCards,NewsletterSubscribers,CouponCodes}**: STI subclasses — each defines `csv_headers`, `scope_includes` (N+1 avoidance), and optionally overrides `scope`/`multi_line_csv?`/`generate_csv`/`required_scope`.
- **Spree::CSV::{CustomerPresenter,GiftCardPresenter,CouponCodePresenter,NewsletterSubscriberPresenter,OrderLineItemPresenter,ProductVariantPresenter,ProductTranslationPresenter}**: One presenter per export type, each producing a flat array (or array of arrays, for multi-line) matching its `HEADERS`/`CSV_HEADERS` constant.
- **Spree::CSV::FormulaSanitizer**: Stateless module neutralizing CSV-injection payloads on every exported cell.
- **Spree::CSV::MetafieldsHelper**: Mixin providing `metafields_for_csv`/`metafield_definitions_for_csv`, included by presenters whose model supports `Spree::Metafields`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Export` + 7 STI subclasses, `Exports::GenerateJob`, `Spree::CSV::*` presenters + `FormulaSanitizer` + `MetafieldsHelper`, `Spree::ExportMailer`, `Spree::ExportSubscriber` |
| `spree/api` (Store/Admin API v3) | Yes | `Spree::Api::V3::Admin::ExportsController` (`index`/`show`/`create`/`destroy`/`download`), `Spree::Api::V3::ExportSerializer` + `Admin::ExportSerializer` (adds `done`, `filename`, `byte_size`, `download_url`) |
| `packages/dashboard` (admin SPA) | Yes | `ExportButton` wired into 3 of 7 types' index routes: products, orders, customers |
| `packages/dashboard-ui` / `dashboard-core` | Yes | `dashboard-core`: `components/export-button.tsx` (dialog: filtered vs. all), `hooks/use-export.ts` (create → poll → blob-download, with email-fallback on timeout) |
| `packages/sdk` / `packages/admin-sdk` | Yes | `admin-sdk` `ExportType`/`Export`/`ExportCreateParams` generated types + `adminClient.exports.{create,get}` |
| `docs/plans/` | Yes | `docs/plans/5.5-admin-spa-csv-export.md` already documents this (shipped plan) — referenced directly in code comments |

### API Contract

- **Endpoints**: `GET /api/v3/admin/exports`, `GET /api/v3/admin/exports/:id`, `POST /api/v3/admin/exports`, `DELETE /api/v3/admin/exports/:id`, `GET /api/v3/admin/exports/:id/download`.
- **Serializer fields (read)**: `number`, `type`, `format`, `user_id`, `created_at`, `updated_at` (base `ExportSerializer`); Admin adds `done`, `filename`, `byte_size`, `download_url`.
- **Write params**: `type`, `record_selection`, `search_params` (arbitrary Ransack hash, extracted via `to_unsafe_h`, not enumerated — a documented, deliberate exception to the flat-`params.permit` convention since the shape is inherently dynamic). `format` is accepted but always dropped/ignored — CSV is the only supported format.
- **Auth**: Admin API secret key with scope `read_<Export.required_scope>` (e.g. `read_products`, `read_customers`, `read_promotions`) or `read_all`, **or** Admin JWT + CanCanCan (used by the dashboard). Exports never mutate commerce data, so every action — including `create` — maps to the `read` action-kind for scope purposes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can go from clicking "Export" to a downloaded CSV file on disk without a full-page reload or leaving the current index route.
- **SC-002**: A CSV opened in Excel/Google Sheets/LibreOffice/Numbers never executes a formula, regardless of the underlying data (e.g. a customer's `Company` field beginning with `=`).
- **SC-003**: An export scoped to another store's or vendor's data is never returned, even when requested with a valid API key for a different store.
- **SC-004**: An export created without a human user (app/secret-key caller) never triggers an email send.

## Assumptions

- "Feature" here means the existing export subsystem as built today — a reverse-engineered specification for spec-kit tracking, not a proposed redesign.
- `Spree.private_storage_service_name` is configured to a genuinely private storage backend in production (not verified in this pass — infra-level assumption).
- The 5-minute client-side poll timeout (`POLL_TIMEOUT_MS`) and 2-second interval (`POLL_INTERVAL_MS`) in `use-export.ts` are assumed tuned for typical store catalog/order sizes; not independently benchmarked here.

## Migration Notes

- **CSV-injection defense confirmed**: `spree/core/app/presenters/spree/csv/formula_sanitizer.rb` is applied to every cell in both `generate_csv`'s single-line and multi-line paths (`Spree::Export#generate_csv`) before being written — this is a real, load-bearing security control (OWASP CSV Injection / CWE-1236), not incidental. Any new export type or presenter added later MUST continue routing rows through `Spree::CSV::FormulaSanitizer.row`, since `CSV.open` itself has no such protection.
- **Gap — incomplete dashboard UI coverage**: Of the 7 registered export types, only 3 (`Products`, `Orders`, `Customers`) have a first-party `<ExportButton>` in `packages/dashboard` (confirmed via `grep -rl "ExportButton" packages/dashboard/src`). `GiftCards`, `NewsletterSubscribers`, `CouponCodes`, and `ProductTranslations` are fully implemented server-side (model, presenter, scope gating) but have no dashboard entry point — reachable only via direct Admin API calls today. This may be intentional (narrower audiences) or a pending SPA task; not disambiguated in this pass.
- **Gap — no automated frontend test coverage found**: No Vitest test for `export-button.tsx`/`use-export.ts` and no Playwright e2e spec under `packages/dashboard/e2e/` reference exports. Backend has RSpec coverage (`spree/core/spec/models/spree/export_spec.rb` + `spec/models/spree/exports/`, `spree/api/spec/integration/spree/api/v3/admin/exports_spec.rb`, controller spec, serializer spec).
- **Not migrated**: no code changes were made. This is a reverse-engineered spec for existing, already-shipped behavior.
</content>
