---
status: migrated
---

# Spec: CSV Exports

**Feature**: Async CSV export of admin resources (Products, Orders, Customers) with signed download URLs

---

## Overview

`Spree::Export` is an STI model representing an async CSV generation job. Merchants trigger an export from the admin SPA toolbar (with current filters or all records). The export is generated in a background job, attached via Active Storage, and made available via a 5-minute signed download URL. The Admin SDK provides polling support via `useExport` hook.

---

## User Scenarios

### US1 — Merchant exports filtered products
Given the Products list with an active "status = active" filter,
When the merchant clicks "Export" and selects "Filtered records",
Then `POST /api/v3/admin/exports` is called with `type: Spree::Exports::Products` and the current Ransack search params; a job is enqueued.

### US2 — Merchant downloads the export
Given a completed export,
When the merchant clicks "Download",
Then the browser downloads the CSV from the signed Active Storage URL (valid 5 minutes).

### US3 — Merchant exports all orders
Given the Orders list,
When the merchant selects "All records" in the export dialog,
Then `record_selection: 'all'` is sent and all store orders are included regardless of current filters.

### US4 — Export completion email
Given an export job that completes,
When the attachment is ready,
Then the merchant receives a notification email with a download link.

---

## Functional Requirements

### FR-001 — Export model
`Spree::Export` with prefix `exp_`. STI base. `include Spree::SingleStoreResource`. `include Spree::NumberIdentifier`. `enum :format, csv: 0`. `record_selection` (`filtered`/`all`). `search_params` (JSON Ransack hash). `has_one_attached :attachment` (private storage). `done?` checks `attachment.attached?`. `generate_async` → `Spree::Exports::GenerateJob.perform_later`. `send_export_done_email`.

### FR-002 — STI subclasses
`Spree::Exports::Products`, `Spree::Exports::Orders`, `Spree::Exports::Customers` — each implements `generate_csv`. Registered in `Spree.export_types`.

### FR-003 — GenerateJob
`Spree::Exports::GenerateJob` — runs export, attaches CSV to `attachment`, triggers notification email.

### FR-004 — Admin API
`Admin::ExportsController` — `index`, `show`, `create`, `delete`. `download` action streams CSV inline. `download_url` is a signed ActiveStorage blob URL (5-minute expiry). Auth: JWT or secret key with matching `read_*` scope.

### FR-005 — Admin SDK
`client.exports.list()`, `get(id)`, `create(params)`, `delete(id)`. `ExportCreateParams`: `type`, `search_params`, `record_selection`, `format`.

### FR-006 — Admin SPA
`useExport` hook in `packages/dashboard-core/src/hooks/use-export.ts` — wraps create + polling (2s interval, 5-min timeout). `ExportButton` + `ExportModal` in toolbar. Wired on Products, Orders, Customers index pages. `filtersToRansack()` converts SPA filter state to Ransack hash.

---

## Success Criteria

- [ ] `POST /api/v3/admin/exports` with `type: Spree::Exports::Products` enqueues a job
- [ ] `GET /api/v3/admin/exports/:id` returns `done: true` and `download_url` when ready
- [ ] `download_url` is a signed 5-minute Active Storage URL
- [ ] `useExport` hook polls until `done: true` then triggers browser download
- [ ] Filtered exports pass current Ransack params; "all records" ignores filters

---

## Out of Scope

- Export history page (not implemented; plan defers it)
- Import (exports only)
- Non-CSV formats
- Custom export column selection
