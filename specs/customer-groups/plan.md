# Implementation Plan: Customer Groups

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped

---

## Summary

`Spree::CustomerGroup` is a simple named grouping model for customer segmentation. Groups are store-scoped via `SingleStoreResource`, soft-deleted via `acts_as_paranoid`, and linked to customers via a polymorphic join model (`CustomerGroupUser`). The Admin API provides full CRUD. The SPA has a groups list page with inline member management. Groups are used by promotions, price lists, and shipping rule targeting.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Store ownership** | `Spree::SingleStoreResource` |
| **Scope** | Fully shipped |

---

## Key Decisions

1. **Simple named group, not a rule-based segment.** Groups are manual assignments. Automatic rule-based segmentation (e.g., "all customers who spent > $1000") is out of scope — that would require a query-builder DSL. Groups are cheap to reason about and sufficient for most merchant use cases.

2. **Polymorphic join allows future user types.** `CustomerGroupUser.user_type` can hold both `Spree::User` and future `Spree::Customer` (after 6.0 rename) without schema changes. The join model is future-proof for the platform-auth rename.

3. **`customers_count` counter cache.** Eliminates N+1 on group list view; stale only on soft-delete (acceptable — paranoid groups don't decrement the count on the fly).

4. **`expand=customers` lazy loading.** The group serializer returns `customers_count` by default; `expand=customers` returns the embedded customer list. This keeps the default group list fast when there are many members.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Read/Write Symmetry**: `name`, `description` serialized and accepted on write
- [x] **Prefixed IDs**: `cg_…` on customer groups
- [x] **Serializer Hierarchy**: `Admin::CustomerGroupSerializer` (admin-only)
- [x] **Type Pipeline**: Typelizer + Zod regen done
- [x] **Security**: CanCanCan `can :manage, Spree::CustomerGroup`; store-scoped via SingleStoreResource
- [x] **Namespace**: `Spree::CustomerGroup`, `Spree::CustomerGroupUser`
- [x] **Plan Conflicts**: None; used by promotions and price lists for targeting

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/customer_group.rb                         ← cg_ prefix, paranoid, SingleStoreResource
spree/core/app/models/spree/customer_group_user.rb                    ← polymorphic join

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/customer_group_serializer.rb

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/customer_groups_controller.rb

# Frontend (✅ shipped)
packages/dashboard/src/routes/_authenticated/$storeId/customers/groups.tsx
packages/dashboard/src/hooks/use-customer-groups.ts
```

---

## Phase 1: Core + API + SPA (✅ Complete)

- `CustomerGroup` model with `cg_` prefix, paranoid, SingleStoreResource, `customers_count` counter
- `CustomerGroupUser` polymorphic join model
- Admin API: full CRUD + bulk customer assignment
- Admin SPA: groups list page with inline member management via autocomplete
- `use-customer-groups.ts` hook

---

## Complexity Tracking

No significant violations. This is a straightforward named-group model with a join table.
