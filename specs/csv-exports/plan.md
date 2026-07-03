# Implementation Plan: CSV Exports

**Branch**: `main` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Status**: Backend + SDK + hooks shipped in 5.5; SPA toolbar buttons shipped; no E2E tests

---

## Summary

CSV export is an async STI pattern: create an `Export` record → job generates CSV → attaches to record → signed URL returned. The `useExport` hook handles polling. Three resource types supported: Products, Orders, Customers.

---

## Key Decisions

1. **STI for export types.** `Spree::Exports::Products`, `Orders`, `Customers` each implement `generate_csv`. New export types are registered in `Spree.export_types`. STI makes it easy to add new types without controller changes.

2. **`done?` checks attachment, not a status column.** No state machine or status enum — the export is either done (attachment present) or pending. This is simple and avoids orphaned status records if jobs fail silently.

3. **Signed URL with 5-minute expiry.** Active Storage `blob.url(expires_in: 5.minutes)` is generated at serialization time. The client downloads immediately; no permanent public URL is created.

4. **`record_selection: 'filtered' | 'all'`.** Filtered exports pass the current Ransack `search_params`; "all" ignores them. The `filtersToRansack()` helper in the SPA converts the UI's filter state into the serialized Ransack format the API expects.

5. **Auth scoped by export type.** A JWT admin can export anything they can read. A secret API key needs the matching `read_products`/`read_orders`/`read_customers` scope. The controller enforces this before enqueueing.

---

## Constitution Check

- [x] **Prefixed IDs**: `exp_`
- [x] **SingleStoreResource**: exports scoped to `current_store`
- [x] **API-First**: controller + SDK before SPA
- [x] **Plan Conflicts**: `5.5-admin-spa-csv-export.md` — fully shipped

---

## Project Structure

```text
spree/core/app/models/spree/export.rb                                         ← exp_ prefix, STI base
spree/core/app/models/spree/exports/products.rb
spree/core/app/models/spree/exports/orders.rb
spree/core/app/models/spree/exports/customers.rb
spree/api/app/jobs/spree/exports/generate_job.rb
spree/api/app/controllers/spree/api/v3/admin/exports_controller.rb
spree/api/app/serializers/spree/api/v3/admin/export_serializer.rb            ← done, download_url, filename
packages/admin-sdk/src/admin-client.ts                                        ← exports.* methods
packages/dashboard-core/src/hooks/use-export.ts                              ← polling hook
packages/dashboard-core/src/components/export-button.tsx
packages/dashboard-core/src/components/export-modal.tsx
```
