# Implementation Plan: Shipping Methods & Zones

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Models + legacy Rails admin shipped; v3 API + SPA entirely PENDING; 6.0 rename pending

---

## Summary

`Spree::ShippingMethod` links a calculator (pricing strategy) to one or more geographic zones and shipping categories. `Spree::Zone` groups countries and states into reusable geographic targets. Together they control which shipping options appear at checkout and at what price. Today, both are managed exclusively via the legacy Rails admin (ERB views + Turbo). No v3 Admin API or React SPA page exists. The 6.0 plan renames ShippingMethod → DeliveryMethod and Zone → DeliveryZone as part of `6.0-fulfillment-and-delivery.md`.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Calculators** | `CalculatedAdjustments` concern + 6 built-in shipping calculators |
| **Scope** | Models complete; API + SPA entirely PENDING |

---

## Key Decisions

1. **`dm_` prefix anticipates 6.0 rename.** `ShippingMethod` already uses `has_prefix_id :dm` (DeliveryMethod). This is intentional forward-compatibility; the prefix will match the new model name in 6.0.

2. **`CalculatedAdjustments` for pricing.** Calculator is a first-class association (`belongs_to :calculator`). Each calculator subclass defines its own preferences and `compute` method. Swapping calculators on a live method is safe (old rates are denormalized on `ShippingRate`).

3. **Zone polymorphism for country/state.** `ZoneMember` is polymorphic (`Spree::Country` or `Spree::State`). Zone `kind` (`country`/`state`) constrains which member type is valid. This enables fine-grained geographic targeting (e.g., California-only express shipping).

4. **`default_tax` on Zone.** Tax zones use the same `Zone` model. The `default_tax` flag marks the zone whose tax rates apply when no other zone matches a customer's address. This will be decoupled in 6.0 when the Zone model is dropped per `6.0-tax-provider.md`.

5. **`ShippingCategory` for method eligibility.** Methods can be restricted to items in specific shipping categories (e.g., hazmat, digital). This is dropped in 6.0 — delivery providers will handle eligibility differently.

6. **Legacy admin manages this today.** `spree/admin/app/controllers/spree/admin/shipping_methods_controller.rb` and `zones_controller.rb` with ERB form views are the only management interface. The v3 API and SPA are a pending gap.

---

## Constitution Check

- [ ] **API-First**: _(PENDING)_ No v3 admin API yet; legacy admin only
- [ ] **Read/Write Symmetry**: _(PENDING)_ Pending serializer design
- [x] **Prefixed IDs**: `dm_…` (ShippingMethod), `zone_…` (Zone), `dr_…` (ShippingRate), `scat_…` (ShippingCategory)
- [ ] **Serializer Hierarchy**: _(PENDING)_ No admin serializer yet
- [ ] **Type Pipeline**: _(PENDING)_ No Typelizer output yet
- [x] **Security**: CanCanCan guards exist on legacy admin; v3 API will inherit same
- [x] **Namespace**: `Spree::ShippingMethod`, `Spree::Zone`, `Spree::ZoneMember`, `Spree::ShippingRate`
- [x] **Plan Conflicts**: Reviewed `6.0-fulfillment-and-delivery.md` — ShippingMethod→DeliveryMethod; `6.0-tax-provider.md` — Zone model dropped for tax (delivery zone survives as `Spree::DeliveryZone`)

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/shipping_method.rb                        ← dm_ prefix, CalculatedAdjustments, paranoid
spree/core/app/models/spree/shipping_category.rb                      ← scat_ prefix
spree/core/app/models/spree/shipping_method_category.rb               ← join
spree/core/app/models/spree/zone.rb                                   ← zone_ prefix, default_tax, paranoid
spree/core/app/models/spree/zone_member.rb                            ← polymorphic Country/State join
spree/core/app/models/spree/shipping_method_zone.rb                   ← join
spree/core/app/models/spree/shipping_rate.rb                          ← dr_ prefix, denormalized cost

# Calculators (✅ shipped)
spree/core/app/models/spree/calculator/shipping/
  ├── digital_delivery.rb
  ├── flat_rate.rb
  ├── flat_percent_item_total.rb
  ├── flexi_rate.rb
  ├── per_item.rb
  └── price_sack.rb

# Backend — legacy admin (✅ shipped, will be replaced)
spree/admin/app/controllers/spree/admin/shipping_methods_controller.rb
spree/admin/app/controllers/spree/admin/zones_controller.rb
spree/admin/app/views/spree/admin/shipping_methods/
spree/admin/app/views/spree/admin/zones/

# Backend — v3 API (PENDING)
spree/api/app/controllers/spree/api/v3/admin/shipping_methods_controller.rb
spree/api/app/controllers/spree/api/v3/admin/zones_controller.rb
spree/api/app/serializers/spree/api/v3/admin/shipping_method_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/zone_serializer.rb

# Frontend (PENDING)
packages/dashboard/src/routes/_authenticated/$storeId/settings/shipping-methods.tsx
packages/dashboard/src/routes/_authenticated/$storeId/settings/zones.tsx
packages/dashboard/src/hooks/use-shipping-methods.ts
packages/dashboard/src/hooks/use-zones.ts
```

---

## Phase 1: Models (✅ Complete)

- `Spree::ShippingMethod` with calculators, zones, shipping categories, `acts_as_list`, paranoid
- 6 built-in shipping calculators
- `Spree::Zone` with polymorphic `ZoneMember` (Country/State), `default_tax`
- `Spree::ShippingRate` denormalized on shipments
- Legacy admin Rails controllers + ERB views (full management)

---

## Phase 2: v3 API + SPA (PENDING)

- Admin v3 API: shipping methods CRUD + zones CRUD
- Serializers for shipping method + zone
- Typelizer + Zod pipeline
- SPA settings pages for shipping methods and zones
- Zone member picker (country/state autocomplete)
- Calculator type `<Select>` + dynamic preferences form (same pattern as payment methods)

---

## Phase 3: 6.0 — Renames (PENDING)

Per `6.0-fulfillment-and-delivery.md`:

- `Spree::ShippingMethod` → `Spree::DeliveryMethod`
- `Spree::Zone` → `Spree::DeliveryZone` (delivery context only; tax context Zone dropped per `6.0-tax-provider.md`)
- `Spree::ShippingRate` → `Spree::DeliveryRate`
- `Spree::ShippingCategory` dropped — delivery providers handle eligibility directly
- `display_on` → `storefront_visible` column rename

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Calculator as first-class association | Swappable pricing strategies per method; each has own preferences | Storing calculator config as JSON on the method collapses type safety for calculator subclasses |
| Zone polymorphism (Country OR State) | Merchants need both country-level and state-level targeting | Two separate zone tables (country zone + state zone) would duplicate the zone/method join logic |
