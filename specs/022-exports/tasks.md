---

description: "Task list for feature migration (retrospective — feature already shipped)"
---

# Tasks: Exports

**Input**: Design documents from `/specs/022-exports/`

**Prerequisites**: plan.md, spec.md

**Status**: migrated — all tasks below reflect code that already exists in the repository. This is a retrospective record, not pending work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent files, no dependency ordering required
- **[Story]**: US1 = product catalog export, US2 = order/customer export, US3 = programmatic/app-driven export (gift cards, newsletter subscribers, coupon codes, product translations)

## Phase 1: Core Export Model & Infrastructure (shared by all stories)

- [x] T001 `spree/core/app/models/spree/export.rb` — STI base: store/vendor/ability-scoped `records_to_export`, `record_selection` (`filtered`/`all`), Ransack `search_params` + prefixed-ID decoding, private-storage attachment, `has_prefix_id :exp`
- [x] T002 [P] `spree/core/app/jobs/spree/exports/generate_job.rb` — async CSV generation, narrow non-retry-safe retry policy
- [x] T003 [P] `spree/core/app/subscribers/spree/export_subscriber.rb` — `export.create` event → `generate_async`
- [x] T004 [P] `spree/core/app/mailers/spree/export_mailer.rb` — completion email, skipped when `user.blank?` (app-created exports)
- [x] T005 [P] `spree/core/app/presenters/spree/csv/formula_sanitizer.rb` — CSV-injection defense (CWE-1236/OWASP), applied to every cell in `generate_csv`
- [x] T006 [P] `spree/core/app/presenters/spree/csv/metafields_helper.rb` — mixin exposing metafield columns to presenters
- [x] T007 [spree/api] `spree/api/app/controllers/spree/api/v3/admin/exports_controller.rb` — index/show/create/destroy/download, per-type scope gating via `Export.required_scope`
- [x] T008 [P] [spree/api] `spree/api/app/serializers/spree/api/v3/export_serializer.rb`, `admin/export_serializer.rb` — base fields + admin-only `done`/`filename`/`byte_size`/`download_url`

## Phase 2: Product Catalog Export [US1]

- [x] T009 `spree/core/app/models/spree/exports/products.rb` — multi-line CSV (one row per variant incl. master), excludes archived products on unfiltered export, N+1-safe `scope_includes`
- [x] T010 [P] `spree/core/app/models/spree/exports/product_translations.rb` — per-locale multi-line CSV via `to_translation_csv`, `required_scope :products`
- [x] T011 [P] `spree/core/app/presenters/spree/csv/product_variant_presenter.rb`, `product_translation_presenter.rb`
- [x] T012 [P] `packages/dashboard/src/routes/_authenticated/$storeId/products/index.tsx` — `<ExportButton type="Spree::Exports::Products">`

## Phase 3: Order & Customer Export [US2]

- [x] T013 `spree/core/app/models/spree/exports/orders.rb` — multi-line CSV (one row per line item), N+1-safe `scope_includes` across bill/ship address, payments, shipments, line items
- [x] T014 [P] `spree/core/app/models/spree/exports/customers.rb` — single-line CSV with computed fields (`amount_spent_in`, `completed_orders.count`)
- [x] T015 [P] `spree/core/app/presenters/spree/csv/order_line_item_presenter.rb`, `customer_presenter.rb`
- [x] T016 [P] `packages/dashboard/src/routes/_authenticated/$storeId/orders/index.tsx`, `customers/index.tsx` — `<ExportButton type="Spree::Exports::Orders">` / `<ExportButton type="Spree::Exports::Customers">`

## Phase 4: Programmatic/App-Driven Export Types [US3]

- [x] T017 [P] `spree/core/app/models/spree/exports/gift_cards.rb` — single-line CSV, `user`-includes for N+1 safety
- [x] T018 [P] `spree/core/app/models/spree/exports/newsletter_subscribers.rb` — `required_scope :customers`
- [x] T019 [P] `spree/core/app/models/spree/exports/coupon_codes.rb` — `required_scope :promotions`, scoped to `store.promotions` explicitly (not `for_store`)
- [x] T020 [P] `spree/core/app/presenters/spree/csv/gift_card_presenter.rb`, `newsletter_subscriber_presenter.rb`, `coupon_code_presenter.rb`
- [x] T021 No dashboard route wires any of these 3 types (nor `ProductTranslations` from Phase 2) to `<ExportButton>` — confirmed via `grep -rl "ExportButton" packages/dashboard/src`; reachable only via direct Admin API calls with an appropriately-scoped key

## Phase 5: Dashboard Shared Component/Hook (shared, all stories with UI coverage)

- [x] T022 [P] `packages/dashboard-core/src/components/export-button.tsx` — filtered-vs-all radio dialog, filter/search summary via `filtersToRansack`
- [x] T023 [P] `packages/dashboard-core/src/hooks/use-export.ts` — create → poll (`GET .../:id` until `done`) → blob-download with in-memory-JWT auth; falls back to email-notification toast on 5-minute poll timeout
- [x] T024 [P] `packages/admin-sdk` — `ExportType`/`Export`/`ExportCreateParams` generated types + `adminClient.exports.{create,get}`

## Notes

- Every phase above is already implemented; nothing here is scheduled work.
- Per spec.md's Migration Notes, **4 of 7 export types (`GiftCards`, `NewsletterSubscribers`, `CouponCodes`, `ProductTranslations`) have no dashboard entry point** — confirmed by grep, not merely undocumented. This is the largest open question for any future SPA-coverage work: intentional narrower audience, or a pending task.
- **No Vitest or Playwright coverage was found** for `export-button.tsx` or `use-export.ts` — flagged, not remediated (retrospective plan, no code changes made in this pass).
- `Spree::CSV::FormulaSanitizer` (T005) is the one component in this feature classified as a security control rather than a data-shaping concern — any future export type MUST continue routing through it.
</content>
