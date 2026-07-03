---

description: "Task list for CSV Exports — backend + SDK + SPA toolbar shipped in 5.5; no dedicated E2E tests"
---

# Tasks: CSV Exports

**Status**: Fully shipped in 5.5; no dedicated E2E tests

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Export job | `spree/api/app/jobs/spree/exports/generate_job.rb` |
| Admin controller | `spree/api/app/controllers/spree/api/v3/admin/exports_controller.rb` |
| Admin serializer | `spree/api/app/serializers/spree/api/v3/admin/export_serializer.rb` |
| Admin SDK | `packages/admin-sdk/src/admin-client.ts` |
| Dashboard-core hook | `packages/dashboard-core/src/hooks/use-export.ts` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core + API + SDK + SPA ✅

- [x] T001 `spree/core/app/models/spree/export.rb` — `has_prefix_id :exp`; `include Spree::SingleStoreResource`; `include Spree::NumberIdentifier`; `enum :format, csv: 0`; `record_selection` string; `search_params` JSON; `has_one_attached :attachment`; `done?`; `generate_async`; `send_export_done_email`
- [x] T002 `spree/core/app/models/spree/exports/products.rb` — implements `generate_csv`
- [x] T003 `spree/core/app/models/spree/exports/orders.rb` — implements `generate_csv`
- [x] T004 `spree/core/app/models/spree/exports/customers.rb` — implements `generate_csv`
- [x] T005 `spree/api/app/jobs/spree/exports/generate_job.rb` — generates CSV; attaches to record; triggers notification
- [x] T006 `spree/api/app/serializers/spree/api/v3/admin/export_serializer.rb` — `exp_` prefix; `done`, `download_url` (5-min signed URL), `filename`, `byte_size`, timestamps
- [x] T007 `spree/api/app/controllers/spree/api/v3/admin/exports_controller.rb` — index, show, create, delete; `download` action; scope auth by export type
- [x] T008 Admin SDK: `client.exports.list()`, `get()`, `create()`, `delete()` in `packages/admin-sdk/src/admin-client.ts`
- [x] T009 `packages/dashboard-core/src/hooks/use-export.ts` — create + poll (2s, 5-min timeout) + `triggerBrowserDownload`
- [x] T010 `ExportButton` + `ExportModal` components in `packages/dashboard-core/src/`
- [x] T011 Export button wired on Products, Orders, Customers index pages
- [x] T012 `filtersToRansack()` utility in `packages/dashboard/src/lib/` — converts SPA filter state to Ransack hash
- [x] T013 Add i18n keys under `admin.exports.*` in all locale files

**Checkpoint**: async CSV export for products/orders/customers; signed download URL; polling hook ✅

---

## Phase 2: E2E Coverage (PENDING)

- [ ] T014 `packages/dashboard/e2e/csv-exports.spec.ts` — trigger products export; poll until done; download CSV; verify content headers
- [ ] T015 Run `pnpm test:e2e`

## Phase 3: Export History Page (PENDING)

- [ ] T016 `packages/dashboard/src/routes/_authenticated/$storeId/exports/index.tsx` — list of past exports with status and download links
- [ ] T017 Add export history to admin navigation

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No dedicated E2E tests for export flow | Medium | T014–T015; async polling + download is non-trivial to test manually |
| No export history page | Low | Merchants can't review past exports; T016–T017 deferred per 5.5 plan |
