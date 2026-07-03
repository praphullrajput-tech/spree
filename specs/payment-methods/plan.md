# Implementation Plan: Payment Methods

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped (5.6 single-store migration complete); 6.0 cleanup pending

---

## Summary

`Spree::PaymentMethod` is an STI base model for payment processing integrations. Built-in types: `Check` and `StoreCredit`. External gateways register STI subclasses via `Spree.payment_methods`. The 5.6 release migrated from multi-store join tables to single `store_id` FK via `SingleStoreResource`. The Admin SPA has a settings page with full CRUD and drag-to-reorder (via `acts_as_list`). Dynamic preferences forms are rendered from `preference_schema`.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Extension point** | STI subclass + `Spree.payment_methods` registry |
| **Ordering** | `acts_as_list` on `position` |
| **Store ownership** | `Spree::SingleStoreResource` (5.6) |

---

## Key Decisions

1. **STI for type safety.** Each gateway type is a distinct Ruby class with its own `preference_schema` and gateway client. STI over a polymorphic `type` enum avoids runtime class name validation.

2. **`preference_schema` drives dynamic forms.** The model declares its preference fields (name, type, encrypted flag) as a hash. The SPA reads this from the API and generates form inputs — no hardcoded gateway forms in the frontend.

3. **`Spree.payment_methods` is the allowlist.** Only registered STI types can be created via the API. This prevents arbitrary class injection and lets the admin `types` action show only installed gateways.

4. **`acts_as_list` for position.** Checkout renders methods in `position` order. Drag-to-reorder in the SPA updates position via `POST /reposition`. Same pattern as OptionType, PriceList.

5. **5.6 single-store migration.** `Spree::PaymentMethod` migrated from `has_many :stores` (via `spree_payment_methods_stores`) to `belongs_to :store` via `SingleStoreResource`. Join table preserved in 5.6 for backward compatibility; dropped in 6.0. Shared methods (existing multi-store records) logged a deprecation warning during backfill.

6. **`display_on` bridged to `storefront_visible`.** Legacy tri-state (`front_end`/`back_end`/`both`) is bridged via `storefront_visible` accessor per `5.5-6.0-display-on-to-boolean.md`. Column rename pending for 6.0.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Read/Write Symmetry**: `name`, `active`, `storefront_visible`, `position`, `preference_schema` serialized and accepted
- [x] **Prefixed IDs**: `pm_…` on all payment methods
- [x] **Serializer Hierarchy**: `Admin::PaymentMethodSerializer` (admin-only)
- [x] **Type Pipeline**: Typelizer + Zod regen after serializer changes
- [x] **Security**: CanCanCan `can :manage, Spree::PaymentMethod`; Ransack allowlist on model
- [x] **Namespace**: `Spree::PaymentMethod`, `Spree::PaymentMethod::Check`, `Spree::PaymentMethod::StoreCredit`
- [x] **Plan Conflicts**: `5.6-6.0-single-store-promotions-payment-methods.md` governs the single-store migration; `5.5-6.0-display-on-to-boolean.md` governs `storefront_visible` bridge

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/payment_method.rb                        ← STI base, SingleStoreResource, acts_as_list
spree/core/app/models/spree/payment_method/check.rb                  ← no preferences
spree/core/app/models/spree/payment_method/store_credit.rb           ← no external credentials

# Backend — serializers
spree/api/app/serializers/spree/api/v3/admin/payment_method_serializer.rb

# Backend — controllers
spree/api/app/controllers/spree/api/v3/admin/payment_methods_controller.rb

# Frontend (✅ shipped)
packages/dashboard/src/routes/_authenticated/$storeId/settings/payment-methods.tsx
packages/dashboard/src/hooks/use-payment-methods.ts
packages/dashboard/e2e/payment-methods.spec.ts
```

---

## Phase 1: Core + API + SPA (✅ Complete)

- `Spree::PaymentMethod` STI base with preference storage, `acts_as_list`, `active` flag
- `Check` and `StoreCredit` built-in subclasses
- `Spree.payment_methods` registry + `types` controller action
- Admin API: full CRUD + `types` + `reposition`
- Admin SPA: settings page with drag-to-reorder, dynamic preferences form via `preference_schema`
- E2E tests

---

## Phase 2: 5.6 — Single-Store Migration (✅ Complete)

Per `5.6-6.0-single-store-promotions-payment-methods.md`:

- `store_id` FK added + `SingleStoreResource` included
- `LegacyMultiStoreSupport` deprecation bridge for existing shared records
- Backfill rake task — logs deprecation per record with multiple stores; assigns primary store
- `spree_payment_methods_stores` join table preserved (not yet dropped)

---

## Phase 3: 6.0 Cleanup (PENDING)

- Drop `spree_payment_methods_stores` join table
- `store_id` column becomes `null: false`
- `display_on` column renamed to `storefront_visible` (boolean) per `5.5-6.0-display-on-to-boolean.md`
- Remove `LegacyMultiStoreSupport` bridge

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| STI + registry | Type safety + allowlist; each gateway needs its own preference schema | Simple polymorphic string would allow arbitrary class injection; preference schema would have no home |
| Dynamic preference forms | Gateways have different credential shapes (API key vs OAuth vs webhook secret) | Hardcoded forms per gateway would require frontend changes for each new extension |
