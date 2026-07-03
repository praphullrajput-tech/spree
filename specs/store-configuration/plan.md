# Implementation Plan: Store Configuration

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped

---

## Summary

`Spree::Store` is the root configuration entity. Each admin session is scoped to one store via `Spree::Current.store`. The model includes many concerns covering markets, channels, user management, translations, metafields, and order routing. The Admin API exposes `show` and `update` only — stores are created via the Spree CLI or seeder, not via the admin. The SPA has a store settings page with all configurable fields.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Soft delete** | `acts_as_paranoid` (used for data integrity, not routine deletion) |
| **Slug** | `friendly_id` |
| **Scope** | Fully shipped |

---

## Key Decisions

1. **No `POST /stores` in admin API.** Stores are created via CLI or seeds. The admin is always scoped to a single store; multi-store management is an extension (`spree_multi_store`).

2. **`Spree::Current.store` is the session-scoped store.** All resource controllers scope their queries through `current_store`. The store is set per-request by middleware.

3. **Preferences via a serialized column + dedicated columns.** Frequently-accessed preferences (`default_currency`, `default_locale`, `timezone`) have dedicated columns for query performance. Less-common preferences live in a serialized `preferences` column.

4. **`Stores::Markets` concern manages multi-currency.** Supported currencies and the default currency are configured here. Products must have prices in all supported currencies.

5. **`OrderRouting::HasStrategyPreference` on Store.** Stores carry a routing strategy preference (same concern as Channel). This is the fallback strategy for orders without an explicit channel assignment.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Read/Write Symmetry**: All serialized store fields accepted on update
- [x] **Prefixed IDs**: `store_…`
- [x] **Serializer Hierarchy**: `Admin::StoreSerializer`
- [x] **Type Pipeline**: Typelizer + Zod regen done
- [x] **Security**: CanCanCan `can :manage, Spree::Store`; only current store accessible
- [x] **Namespace**: `Spree::Store`

---

## Project Structure

```text
# Backend — model (✅ shipped)
spree/core/app/models/spree/store.rb                                 ← store_ prefix, friendly_id, paranoid
# Concerns mixed directly into Store:
#   Stores::Setup, Stores::Markets, Stores::Channels
#   TranslatableResource, Metafields, Metadata
#   UserManagement, OrderRouting::HasStrategyPreference

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/store_serializer.rb

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/store_controller.rb     ← show + update only

# Frontend (✅ shipped)
packages/dashboard/src/routes/_authenticated/$storeId/settings/store.tsx
packages/dashboard/e2e/store-settings.spec.ts
```

---

## Phase 1: Core + API + SPA (✅ Complete)

- `Spree::Store` with all concerns
- Admin API: `show` + `update` (no create/delete)
- SPA: store settings form
- E2E: store settings spec

---

## Complexity Tracking

No significant violations — store configuration is intentionally simple (show + update).
