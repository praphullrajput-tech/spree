# Implementation Plan: Tax Rates & Categories

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Tax categories fully shipped; tax rates models-only; 6.0 TaxProvider replaces system

---

## Summary

Tax categories (`Spree::TaxCategory`, prefix `taxcat_`) link products/variants to applicable tax rates. Tax rates (`Spree::TaxRate`, prefix `tax_`) associate a category with a geographic zone and a calculator-based amount. Rates can be included in price (EU-style VAT) or added on top (US-style). The Admin API for tax categories is fully shipped. Tax rate management has no v3 admin controller, no serializer, and no SPA page — it is managed via the legacy Rails admin only. The 6.0 `TaxProvider` plan replaces `TaxRate` + `Zone` entirely with a per-market provider strategy and direct country/state FKs.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Tax adjustment** | `CalculatedAdjustments` concern + `AdjustmentSource` on TaxRate |
| **Scope** | Tax categories: fully shipped. Tax rates: models-only |

---

## Key Decisions

1. **Tax category is the product-side link.** Products/variants carry `tax_category_id`. The category name is merchant-defined; the system has no built-in categories. A `default` category applies when a product has no explicit assignment.

2. **Tax rate uses `CalculatedAdjustments`.** The calculator on a rate computes the adjustment amount. In practice, most stores use `Spree::Calculator::FlatRate` configured with the tax percentage. The calculator indirection enables unusual cases (tiered rates, etc.).

3. **`included_in_price` per rate.** EU merchants mark rates as included; US merchants do not. A product's display price must be consistent — the serializer derives `price_including_vat` for Store API consumers.

4. **`default_tax` on Zone determines fallback.** When a customer's address matches no zone, the `default_tax: true` zone's rates apply. This is used for stores without address validation (guest checkout without address).

5. **Tax rates not in v3 API — intentional gap or oversight?** Given that the 6.0 plan replaces the entire tax system, building a full v3 API for tax rates may not be worth the investment. The legacy admin covers this for 5.x stores.

---

## Constitution Check

- [x] **Prefixed IDs**: `taxcat_…` (TaxCategory), `tax_…` (TaxRate)
- [x] **Serializer Hierarchy**: `Admin::TaxCategorySerializer` — shipped; TaxRate serializer PENDING
- [x] **Security**: CanCanCan guards; legacy admin controller for tax rates
- [x] **Plan Conflicts**: `6.0-tax-provider.md` — Zone dropped; TaxRate replaced by TaxProvider per-market; `6.0-fulfillment-and-delivery.md` — DeliveryZone replaces Zone (delivery context only)

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/tax_category.rb                          ← taxcat_ prefix, paranoid
spree/core/app/models/spree/tax_rate.rb                              ← tax_ prefix, paranoid, CalculatedAdjustments

# Backend — serializers (partial)
spree/api/app/serializers/spree/api/v3/admin/tax_category_serializer.rb   ← exists
# MISSING: tax_rate_serializer.rb

# Backend — controllers (partial)
spree/api/app/controllers/spree/api/v3/admin/tax_categories_controller.rb ← exists
# MISSING: tax_rates_controller.rb

# Frontend (partial)
packages/dashboard/src/routes/_authenticated/$storeId/settings/tax-categories.tsx   ← exists
packages/dashboard/e2e/tax-categories.spec.ts                                        ← exists
# MISSING: tax-rates.tsx
```

---

## Phase 1: Tax Categories — Core + API + SPA (✅ Complete)

- `Spree::TaxCategory` with `taxcat_` prefix, paranoid, default class method
- Admin API: full CRUD
- Admin SPA: `settings/tax-categories.tsx`
- E2E: `tax-categories.spec.ts`

---

## Phase 2: Tax Rates — v3 API + SPA (PENDING / LOW PRIORITY)

Given that 6.0 replaces the entire tax system, this phase may be skipped in favor of waiting for the `TaxProvider` implementation.

- `tax_rate_serializer.rb`
- `tax_rates_controller.rb` (full CRUD)
- SPA `settings/tax-rates.tsx` with zone + category pickers, calculator selector

---

## Phase 3: 6.0 — TaxProvider (PENDING)

Per `6.0-tax-provider.md`:

- `Spree::TaxProvider` — per-market strategy (replaces `TaxRate.adjust`)
- `Spree::TaxRate` — gets direct country/state FKs (drops `zone_id`)
- `Spree::Zone` model dropped (tax context only; delivery zone survives as `Spree::DeliveryZone`)
- Drop `Spree::Calculator` indirection for tax rates — rates store `amount` directly

---

## Complexity Tracking

No significant violations for tax categories. Tax rates are complex but well-understood; the complexity comes from the zone/calculator indirection which 6.0 simplifies.
