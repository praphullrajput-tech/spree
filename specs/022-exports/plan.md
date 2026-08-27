# Implementation Plan: Exports

**Branch**: `022-exports` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-exports/spec.md`

**Note**: This plan is reverse-engineered from an already-shipped feature (brownfield migration), not authored ahead of implementation.

## Summary

A CSV export pipeline (`Spree::Export` STI base + 7 subclasses: `Products`, `ProductTranslations`, `Orders`, `Customers`, `GiftCards`, `NewsletterSubscribers`, `CouponCodes`) that generates a file asynchronously (`Spree::Exports::GenerateJob`, triggered off the `export.create` lifecycle event), scoped to store/vendor/ability, optionally filtered via an arbitrary Ransack `search_params` hash, and streamed back through an Admin API v3 `download` action. Every exported cell is run through `Spree::CSV::FormulaSanitizer` to neutralize CSV-injection payloads. The dashboard SPA (`packages/dashboard-core`'s `ExportButton` + `useExport`) drives create → poll → browser-download for 3 of the 7 types (Products, Orders, Customers); the remaining 4 are reachable only via direct Admin API calls today.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines) — `spree/core` (model/CSV generation/presenters) and `spree/api` (Admin API v3 controller/serializers). TypeScript (React SPA) — `packages/dashboard-core` (shared `ExportButton`/`useExport`) and `packages/dashboard` (3 route call sites).

**Primary Dependencies**: Active Storage (`has_one_attached :attachment`, private storage service), ActiveJob/Sidekiq (`Spree::Exports::GenerateJob`), Ransack (arbitrary `search_params` filtering + prefixed-ID decoding), CanCanCan (`accessible_by`), Alba serializers, `@spree/admin-sdk` (`adminClient.exports`), TanStack Query (`useMutation` in `useExport`), `sonner` (toast progress UI).

**Storage**: PostgreSQL/SQLite3 via ActiveRecord; CSV attachment stored via `Spree.private_storage_service_name` (private, not public — exports can contain PII such as customer emails/addresses).

**Testing**: RSpec (`spree/core/spec/models/spree/export_spec.rb`, `spree/core/spec/models/spree/exports/`, `spree/core/spec/jobs/spree/exports/`, `spree/core/spec/mailers/spree/export_mailer_spec.rb`, `spree/core/spec/subscribers/spree/export_subscriber_spec.rb`, `spree/api/spec/controllers/spree/api/v3/admin/exports_controller_spec.rb`, `spree/api/spec/integration/spree/api/v3/admin/exports_spec.rb`, `spree/api/spec/serializers/spree/api/v3/export_serializer_spec.rb`). No Vitest or Playwright coverage found for `export-button.tsx`/`use-export.ts`.

**Target Platform**: Admin API v3 (`spree/api`) backing both the dashboard SPA (JWT + CanCanCan) and direct secret-API-key integrations (scope-gated). Dashboard SPA surfaces only 3 of 7 export types.

**Project Type**: Monorepo — `spree/core` (Export STI + presenters + job + mailer + subscriber) + `spree/api` (controller + serializers) + `packages/dashboard-core` (shared `ExportButton`/`useExport`) + `packages/dashboard` (route wiring for products/orders/customers) + `packages/admin-sdk` (generated client types/methods).

**Performance Goals**: CSV generation happens off-request in a background job; `find_in_batches` is used when iterating `records_to_export` to bound memory on large exports.

**Constraints**: Every export type gated by an Admin API key scope (`read_<required_scope>`, derived from the STI subclass name, e.g. `CouponCodes` → `:promotions`); attachment storage must be private; every exported cell must pass through `FormulaSanitizer` before being written; client-side poll timeout is 5 minutes before falling back to the email-notification path.

**Scale/Scope**: 7 export types, 1 background job class, 7 CSV presenter classes + 2 shared mixins (`FormulaSanitizer`, `MetafieldsHelper`), 1 Admin API controller + 2 serializers, 1 shared dashboard component + 1 hook, 3 dashboard route call sites.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: `spree/core` owns model/CSV-generation logic; `spree/api` owns the controller/serializers; `packages/dashboard-core` owns the shared UI component/hook; `packages/dashboard` only wires the component into 3 routes. The SDK (`packages/admin-sdk`) is the sole cross-boundary bridge from dashboard to API — no direct model/HTML access from the frontend. PASS.
- **II. Admin API Is the Only Frontend Data Source**: Confirmed — `useExport` calls `adminClient.exports.{create,get}` exclusively; the file download itself goes through the controller's `download` action (streamed, not a raw ActiveStorage redirect) specifically so the SPA's same-origin JWT/proxy constraints hold. PASS.
- **III. Read/Write Field Symmetry**: `ExportsController#permitted_params` accepts `type`, `record_selection`, `search_params` — all of which the serializer either doesn't need to round-trip (write-only, transient) or already exposes (`type`). `search_params` is a documented, deliberate exception to enumerated `params.permit` (arbitrary nested Ransack hash, extracted via `to_unsafe_h`) — not a naming mismatch. PASS, with the documented exception noted in spec.md's API Contract section.
- **IV. Test-Backed**: RSpec covers model/job/mailer/subscriber/controller/integration/serializer layers (see Testing above). **Gap**: no Vitest test for `use-export.ts`'s poll/download/timeout-fallback logic, and no Playwright e2e for the `ExportButton` flow on any of its 3 wired routes — flagged in spec.md Migration Notes, not remediated here (retrospective plan, no code changes).
- **V. Translations and Prefixed IDs**: `Spree::Export` uses `has_prefix_id :exp`; the serializer exposes `user_id` as a prefixed ID via `user&.prefixed_id`; `download_url` is generated via Rails route helpers keyed on `prefixed_id`. Dashboard strings (`ExportButton` dialog copy, toasts) go through i18next (`admin.components.export_button.*`, `admin.actions.*`) — confirmed in `export-button.tsx`/`use-export.ts`. PASS.
- **VI. `docs/plans/` for Architectural Changes**: `docs/plans/5.5-admin-spa-csv-export.md` already exists and is cited directly in code comments (routes.rb, exports_controller.rb) — this feature is fully covered by an existing plan doc, no new entry needed.

No violations for the current (already-shipped) state. The two Migration Notes gaps (dashboard UI coverage for 4/7 types, missing frontend test coverage) are tracked as follow-up, not treated as violations of what exists.

## Project Structure

### Documentation (this feature)

```text
specs/022-exports/
├── plan.md              # This file
├── spec.md              # Reverse-engineered specification
└── tasks.md             # Reverse-engineered task list (all complete)
```

### Source Code (repository root)

```text
# spree/core — Export STI base + subclasses, CSV presenters, job, mailer, subscriber
spree/core/
├── app/models/spree/export.rb                                   # STI base: scope, generate_csv, event hooks, prefixed-ID decoding
├── app/models/spree/exports/
│   ├── products.rb, product_translations.rb
│   ├── orders.rb, customers.rb, gift_cards.rb
│   ├── newsletter_subscribers.rb, coupon_codes.rb
├── app/presenters/spree/csv/
│   ├── formula_sanitizer.rb          # CSV-injection defense, applied to every cell
│   ├── metafields_helper.rb          # mixin: metafield columns for supporting presenters
│   ├── customer_presenter.rb, gift_card_presenter.rb, coupon_code_presenter.rb
│   ├── newsletter_subscriber_presenter.rb, order_line_item_presenter.rb
│   ├── product_variant_presenter.rb, product_translation_presenter.rb
├── app/jobs/spree/exports/generate_job.rb                        # async CSV generation, narrow non-retry-safe retry policy
├── app/mailers/spree/export_mailer.rb                            # completion email (skipped for app-created exports)
├── app/subscribers/spree/export_subscriber.rb                    # 'export.create' → generate_async
└── spec/{models/spree/export_spec.rb, models/spree/exports/, jobs/spree/exports/,
         mailers/spree/export_mailer_spec.rb, subscribers/spree/export_subscriber_spec.rb}

# spree/api — Admin API v3 controller + serializers
spree/api/
├── app/controllers/spree/api/v3/admin/exports_controller.rb      # index/show/create/destroy/download, scope-gated
├── app/serializers/spree/api/v3/export_serializer.rb             # base: number, type, format, user_id, timestamps
├── app/serializers/spree/api/v3/admin/export_serializer.rb       # + done, filename, byte_size, download_url
└── spec/{controllers/spree/api/v3/admin/exports_controller_spec.rb,
         integration/spree/api/v3/admin/exports_spec.rb,
         serializers/spree/api/v3/export_serializer_spec.rb}

# packages/dashboard-core — shared export UI (headless-adjacent: owns its own dialog + hook)
packages/dashboard-core/src/
├── components/export-button.tsx    # filtered-vs-all dialog, wraps useExport
└── hooks/use-export.ts             # create → poll(done) → blob-download, email-fallback on timeout

# packages/dashboard — route wiring (3 of 7 types only)
packages/dashboard/src/routes/_authenticated/$storeId/
├── products/index.tsx    # <ExportButton type="Spree::Exports::Products" .../>
├── orders/index.tsx      # <ExportButton type="Spree::Exports::Orders" .../>
└── customers/index.tsx   # <ExportButton type="Spree::Exports::Customers" .../>

# [NOT WIRED] GiftCards, NewsletterSubscribers, CouponCodes, ProductTranslations —
# fully implemented server-side, no dashboard route currently renders ExportButton for them

# packages/admin-sdk — generated client
packages/admin-sdk/src/  # ExportType, Export, ExportCreateParams types + adminClient.exports.{create,get}
```

**Structure Decision**: Backend (`spree/core` + `spree/api`) implements all 7 export types uniformly. Frontend (`packages/dashboard-core` for the shared component/hook, `packages/dashboard` for route wiring) only exposes 3 of them today — confirmed by directory/grep search, not merely out of scope. `packages/dashboard-ui` has no export-specific primitives (the dialog is built directly in `dashboard-core` from existing primitives).

## Complexity Tracking

*No Constitution Check violations for existing code — table intentionally empty. The dashboard-coverage and frontend-test gaps are tracked as Migration Notes, not violations.*
</content>
