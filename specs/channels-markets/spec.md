---
status: migrated
---

# Spec: Channels & Markets

**Feature**: Sales channels for product publishing control; one default channel per store; channel-scoped product publication with scheduling

---

## Overview

A `Spree::Channel` is a named sales outlet (e.g. "Online Store", "Mobile App", "Wholesale Portal"). Products are published to channels via `Spree::ProductPublication` join records with optional `published_at`/`unpublished_at` scheduling. Each store has one `default` channel (auto-created as "online" on store creation). Orders are assigned a `channel_id`. The 6.0 plan layers `Catalog`, `Company`, and B2B features on top of this foundation.

---

## User Scenarios

### US1 — Merchant views and creates channels
Given the Settings → Channels page,
When the merchant creates a new channel "B2B Portal",
Then it appears in the list; the first channel is automatically `default`.

### US2 — Merchant publishes a product to a specific channel
Given a product and a "B2B Portal" channel,
When the merchant uses the product publishing panel or the bulk action,
Then a `ProductPublication` record is created linking the product to the channel with optional scheduling dates.

### US3 — Merchant removes a product from a channel
Given a published product,
When the merchant unpublishes from a channel via the admin,
Then the `ProductPublication` is destroyed; the product is no longer visible on that channel.

### US4 — Order is assigned to a channel
Given an order placed through the Store API with a publishable key scoped to a channel,
Then the order's `channel_id` is set automatically; routing rules can reference it.

### US5 — Merchant sets the order routing strategy for a channel
Given a channel detail form,
When the merchant selects "Rules" as the routing strategy,
Then `preferred_order_routing_strategy` is persisted on the channel.

---

## Functional Requirements

### FR-001 — Channel model
`Spree::Channel` with prefix `ch_`. Columns: `store_id` (NOT NULL), `name` (NOT NULL), `code` (NOT NULL, unique per store), `default` (boolean, partial unique index ensuring one default per store), `active` (boolean). `has_many :order_routing_rules, dependent: :destroy`. `OrderRouting::HasStrategyPreference` concern. `after_create :ensure_default_order_routing_rules`. `before_save :demote_other_defaults`.

### FR-002 — ProductPublication model
`Spree::ProductPublication` with prefix `pp_`. Columns: `product_id`, `channel_id`, `published_at` (nullable scheduling), `unpublished_at` (nullable scheduling). Unique index `(product_id, channel_id)`.

### FR-003 — Product integration
`Spree::Product::Channels` concern — `has_many :product_publications`, `has_many :channels through: :product_publications`. Custom `product_publications=` setter for SPA writes. `publish_to!`, `unpublish_from!`, `published_to_channel?`.

### FR-004 — Channel bulk product actions
`Channel#add_products(product_ids, published_at:, unpublished_at:)` — idempotent upsert. `Channel#remove_products(product_ids)` — destroys publications.

### FR-005 — Admin API
`Admin::ChannelsController` — full CRUD; `add_products` (POST), `remove_products` (POST). `Admin::ProductsController` bulk: `bulk_add_to_channels`, `bulk_remove_from_channels`.

### FR-006 — Admin SPA
`settings/channels.tsx` — channel list; create/edit sheet with name, code, active toggle, routing strategy selector. Hooks: `use-channels.ts`.

### FR-007 — 6.0 — Catalog + Company (PENDING)
`Spree::Catalog` (optional price list, has_many catalog_products), `Spree::CatalogAssignment` (polymorphic: Channel/CustomerGroup), `Spree::Company`/`CompanyLocation`/`CompanyContact` for B2B. Visibility resolution via `Spree::Products::ForContext`.

---

## Success Criteria

- [ ] `GET /api/v3/admin/channels` returns list with `default`, `code`, `preferred_order_routing_strategy`
- [ ] `POST /api/v3/admin/channels/:id/add_products` creates ProductPublication records
- [ ] Default channel auto-created when store is seeded
- [ ] Order `channel_id` set on placement via store's default channel
- [ ] SPA Settings → Channels allows CRUD + routing strategy selection

---

## Out of Scope

- Catalog model (6.0 pending)
- Company/B2B hierarchy (6.0 pending)
- ProductPublication scheduling UI (model supports it; SPA exposes basic publish/unpublish)
