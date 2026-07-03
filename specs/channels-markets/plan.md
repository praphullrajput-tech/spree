# Implementation Plan: Channels & Markets

**Branch**: `main` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Status**: Phase 1 shipped in 5.5; Phase 2 (Catalog + Company/B2B) pending in 6.0

---

## Summary

Channels are named sales outlets scoped to a store. Products are published to channels via `ProductPublication` join records. The default channel is enforced at the DB level (partial unique index on `default = true`). Order routing strategy is a preference stored on the channel, falling back to the store preference. The 6.0 plan adds `Catalog` (price list + product visibility overlay) and `Company` (B2B org hierarchy) on top.

---

## Key Decisions

1. **`default` is a boolean column with a partial unique index.** Ensures exactly one default channel per store at the database level. MySQL falls back to a model-level uniqueness validation (MySQL doesn't support partial indexes). `before_save :demote_other_defaults` handles promotion atomically.

2. **`ProductPublication` replaces `StoreProduct`.** The old `spree_store_products` join table is retired. `ProductPublication` adds scheduling (`published_at`/`unpublished_at`) and enables per-channel visibility rather than per-store. The product `belongs_to :store` (single-owner, shipped in 5.5) for creation, but can be published to many channels.

3. **`add_products` uses `upsert_all` for idempotency.** Creating publications in bulk must be safe to re-run. `upsert_all` on `(product_id, channel_id)` unique key handles duplicates without errors. Re-publishing preserves existing windows unless dates are passed.

4. **`code` is a parameterized slug.** Auto-derived from name. Stable after user edit. Used in API routing and as the `channel` param in publishable key creation.

5. **`ensure_default_order_routing_rules` seeds built-in rules on channel creation.** New channels get the 3 default routing rules (PreferredLocation, MinimizeSplits, DefaultLocation) in order. Merchants can customize positions later.

6. **Phase 2 (Catalog/Company) is architecturally separate.** The `Channel` model is feature-complete for Phase 1. Catalog adds a visibility + pricing overlay. Company adds B2B org gating. Neither requires changes to the Channel model itself — they attach via `CatalogAssignment`.

---

## Constitution Check

- [x] **Prefixed IDs**: `ch_` (Channel), `pp_` (ProductPublication)
- [x] **API-First**: Admin API before SPA
- [x] **Read/Write Symmetry**: `name`, `code`, `active`, `default`, `preferred_order_routing_strategy` round-trip
- [x] **Serializer Hierarchy**: `Admin::ChannelSerializer` extends `V3::ChannelSerializer`
- [x] **Security**: CanCanCan; `current_store.channels` scope
- [x] **Plan Conflicts**: `6.0-channels-catalogs-b2b.md` — Phase 1 shipped; Phase 2 pending

---

## Project Structure

```text
spree/core/app/models/spree/channel.rb                                        ← ch_ prefix, default boolean
spree/core/app/models/spree/product_publication.rb                            ← pp_ prefix
spree/core/app/models/spree/product/channels.rb                               ← concern on Product
spree/api/app/controllers/spree/api/v3/admin/channels_controller.rb           ← CRUD + add/remove products
spree/api/app/serializers/spree/api/v3/admin/channel_serializer.rb
packages/dashboard/src/routes/_authenticated/$storeId/settings/channels.tsx
packages/dashboard/src/hooks/use-channels.ts
packages/dashboard/src/tables/channels.tsx
packages/dashboard/e2e/channels.spec.ts
packages/dashboard/e2e/channels-settings.spec.ts
```

---

## Phase 1 (✅ Shipped — 5.5)

Channel + ProductPublication models, Admin API, SPA settings page, E2E.

## Phase 2 (PENDING — 6.0)

Per `6.0-channels-catalogs-b2b.md`: Catalog, CatalogAssignment, Company, CompanyLocation, CompanyContact.
