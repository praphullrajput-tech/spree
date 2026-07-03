# Implementation Plan: Products & Variants

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped; 6.0 remove-master-variant + product-types pending

---

## Summary

`Spree::Product` is the central catalog entity. It carries name, description, slug, status (draft/active/archived), and SEO metadata. Pricing lives on `Spree::Variant`. The product has a `default_variant_id` FK pointing to the primary variant. `is_master` on Variant is a legacy pattern targeted for removal in 6.0. The Admin SPA has a comprehensive product management interface with bulk operations, variant editor, media gallery, pricing, inventory, categories, channels, metafields, and translations.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Search** | `SearchIndexable` concern → Meilisearch or DB fallback |
| **Scope** | Fully shipped; 6.0 model cleanup pending |

---

## Key Decisions

1. **Status is a plain string, not a state machine.** `draft`/`active`/`archived` transitions have no guards — an admin can set any status at any time. This was intentional to keep product management simple; guard logic (e.g., requiring a price before publishing) is handled at the UI layer.

2. **Price lives on Variant, not Product.** A product's "price" is the `default_variant` price. This allows per-variant pricing for size/color combinations without a parallel price table on Product.

3. **`default_variant_id` over `is_master`.** 6.0 eliminates `is_master` in favor of an explicit `default_variant_id` FK on Product. This removes the ambiguity of "what is the master variant?" and allows the FK to be indexed efficiently.

4. **`SearchIndexable` concern abstracts the search backend.** Products sync to Meilisearch when configured; fall back to database full-text search. The concern handles the sync on save/destroy.

5. **Bulk operations via custom controller actions.** `bulk_status_update`, `add_to_categories`, `remove_from_categories`, `add_to_channels`, `remove_from_channels` are POST actions on the products controller taking arrays of IDs. Atomic — all-or-nothing within a transaction.

6. **Channels for product publication.** `Channels` concern gives products a many-to-many with `Spree::Channel`. Products are published per-channel. `6.0-channels-catalogs-b2b.md` introduces `ProductPublication` to replace `StoreProduct`.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Read/Write Symmetry**: `name`, `description`, `slug`, `status`, `available_on` serialized and accepted
- [x] **Prefixed IDs**: `prod_…` on products; `variant_…` on variants
- [x] **Serializer Hierarchy**: `Admin::ProductSerializer` extends `V3::ProductSerializer`
- [x] **Type Pipeline**: Typelizer + Zod regen done
- [x] **Security**: CanCanCan `can :manage, Spree::Product`; Ransack allowlist on model
- [x] **Namespace**: `Spree::Product`, `Spree::Variant`
- [x] **Plan Conflicts**: `6.0-remove-master-variant.md` governs `is_master` removal; `6.0-product-types.md` governs Prototype→ProductType rename; `6.0-channels-catalogs-b2b.md` governs ProductPublication

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/product.rb                               ← prod_ prefix, status, paranoid
spree/core/app/models/spree/product/channels.rb                      ← channel publication
spree/core/app/models/spree/product/slugs.rb                         ← URL slug generation
spree/core/app/models/spree/product/webhooks.rb                      ← lifecycle events
spree/core/app/models/spree/variant.rb                               ← variant_ prefix, price, SKU

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/product_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/variant_serializer.rb

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/products_controller.rb
spree/api/app/controllers/spree/api/v3/admin/variants_controller.rb

# Frontend (✅ shipped)
packages/dashboard/src/routes/_authenticated/$storeId/products/index.tsx
packages/dashboard/src/routes/_authenticated/$storeId/products/$productId.tsx
packages/dashboard/src/hooks/use-products.ts
packages/dashboard/e2e/products-*.spec.ts                            ← 10+ E2E files
```

---

## Phase 1: Core + API + SPA (✅ Complete)

- Product + Variant models with all concerns
- Admin API: full CRUD + bulk operations + clone
- Admin SPA: product list + detail (variants, media, pricing, inventory, SEO, categories, channels, metafields, translations)
- Comprehensive E2E coverage (pricing, inventory, publishing, bulk, variants, translations, media)

---

## Phase 2: 6.0 Cleanup (PENDING)

Per `6.0-remove-master-variant.md`:
- Remove `is_master` column from `spree_variants`
- `default_variant_id` FK becomes the sole source of truth on `Spree::Product`
- Update all code that queries `variants.where(is_master: true)`

Per `6.0-product-types.md`:
- `Spree::Prototype` renamed to `Spree::ProductType`
- `MetafieldDefinition` schema enforcement per product type

Per `6.0-channels-catalogs-b2b.md`:
- `ProductPublication` replaces `StoreProduct`
- Products get `belongs_to :store` (single-owner)

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| 9 concerns on Product | Each concern is independently testable and optionally replaceable (e.g., swap `SearchIndexable`) | Monolithic product model would be 1000+ lines; concerns keep responsibilities separated |
| Variant holds price, not Product | Multi-variant products need per-variant pricing; no clean way to put this on Product | Duplicate price columns on Product and Variant would create sync issues |
