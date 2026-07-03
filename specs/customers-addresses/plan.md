# Implementation Plan: Customers & Addresses

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped in 5.5; 6.0 User→Customer rename pending

---

## Summary

The customer management feature shipped in 5.5 per `5.5-admin-customers-api.md`. The Admin API URL is `/api/v3/admin/customers`; the model is accessed via `Spree.user_class` (defaults to `Spree::LegacyUser`). The Admin SPA has a customer list with bulk operations and a customer detail page with addresses, orders, and store credits. Addresses are nested under customers with their own CRUD. The 6.0 User→Customer rename per `6.0-platform-auth.md` will change the model constant and prefix (`cus_` → `cust_`).

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **User model** | Configurable via `Spree.user_class`; default `Spree::LegacyUser` |
| **Scope** | Fully shipped (5.5); 6.0 rename pending |

---

## Key Decisions

1. **`Spree.user_class` indirection.** The controller never references `Spree::User`. All model access goes through `Spree.user_class`. This allows hosts to swap in a Devise user model without modifying core.

2. **URL `/customers` from day one.** The plan mandated the `/customers` URL (not `/users`) from the 5.5 launch. This matches the 6.0 model rename target and avoids a URL migration later.

3. **`skip_password_validation` for admin creation.** Admins create customer accounts without knowing their password. The controller sets a flag that bypasses password presence validation; the customer sets their password on first login.

4. **Computed stats are read-only on the serializer.** `orders_count`, `total_spent`, and `last_order_completed_at` are not stored columns — they are computed via SQL in the serializer or model. No write path for these fields.

5. **Addresses nested under customers.** `/api/v3/admin/customers/:id/addresses` scopes address access to the customer. The controller auto-manages `default_billing` and `default_shipping` flags when a new default is set.

6. **Address validation is country-configurable.** Zipcode is required for most countries but optional for some. State is required for US/AU/CA but optional elsewhere. This is enforced at model validation level per `Spree::Country` settings.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Read/Write Symmetry**: All serialized fields accepted on write; `orders_count` etc. are read-only computed
- [x] **Prefixed IDs**: `cus_…` on customers (5.5); `addr_…` on addresses
- [x] **Serializer Hierarchy**: `Admin::CustomerSerializer` (admin-only)
- [x] **Type Pipeline**: Typelizer + Zod regen done
- [x] **Security**: CanCanCan `can :manage, Spree.user_class`; Ransack allowlist on model; store-scoped
- [x] **Namespace**: `Spree.user_class`, `Spree::Address`, `Spree::LegacyUser`
- [x] **Plan Conflicts**: `6.0-platform-auth.md` governs User→Customer rename; GDPR endpoints deferred per `5.4-6.0-eu-legal-compliance.md`

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/concerns/spree/user_methods.rb                  ← cus_ prefix, associations, computed stats
spree/core/app/models/spree/legacy_user.rb                            ← default user class (BCrypt, no Devise)
spree/core/app/models/spree/address.rb                                ← addr_ prefix, paranoid, metafields, country validation

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/customer_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/address_serializer.rb

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/customers_controller.rb
spree/api/app/controllers/spree/api/v3/admin/customers/addresses_controller.rb

# Frontend (✅ shipped)
packages/dashboard/src/routes/_authenticated/$storeId/customers/index.tsx
packages/dashboard/src/routes/_authenticated/$storeId/customers/$customerId.tsx
packages/dashboard/src/hooks/use-customers.ts
```

---

## Phase 1: 5.5 — Admin API + SPA (✅ Complete)

- `CustomerSerializer` + `AddressSerializer`
- `CustomersController` with `skip_password_validation`
- `Customers::AddressesController` nested under customers
- SPA: customer list with bulk operations + CSV export
- SPA: customer detail with addresses, orders, store credits sub-sections
- `use-customers.ts` with Ransack search

---

## Phase 2: 6.0 — User→Customer Rename (PENDING)

Per `6.0-platform-auth.md`:

- `Spree::User` → `Spree::Customer` model rename
- `Spree.user_class` → `Spree.customer_class`
- Prefix: `cus_` → `cust_`
- Drop Devise dependency; own JWT auth stack
- GDPR endpoints (data export, anonymization) per `5.4-6.0-eu-legal-compliance.md`

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| `Spree.user_class` indirection | Hosts must be able to swap in their own user model (Devise, custom auth) | Hardcoding `Spree::User` would force hosts to monkey-patch core to use custom auth |
| Country-configurable address validation | Different countries have different required fields (zipcode, state) | A single rigid validation set would reject valid addresses from many countries |
