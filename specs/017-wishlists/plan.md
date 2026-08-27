# Implementation Plan: Wishlists

**Branch**: `017-wishlists` | **Date**: 2026-08-24 | **Spec**: `specs/017-wishlists/spec.md`

**Input**: Feature specification from `specs/017-wishlists/spec.md`

**Note**: This is a reverse-engineered (brownfield) plan for an already-shipped feature. It documents the actual implementation rather than prescribing new work.

## Summary

Customer-owned, store-scoped wishlists exposed exclusively through the Store API v3. Each `Spree::Wishlist` belongs to a user and a store, has a unique secure `token`, and a single-default-per-user invariant enforced in an `after_commit` callback. Each wishlist has many `Spree::WishedItem` rows (variant + quantity), unique per variant. Both models publish lifecycle events for webhook subscribers. `packages/sdk` ships a fully hand-written, generated-type-backed client resource; there is no Admin API or admin dashboard surface.

## Technical Context

**Language/Version**: Ruby (Rails 7.2-compatible engine code in `spree/core`, `spree/api`) and TypeScript (`packages/sdk` client + generated types/Zod)

**Primary Dependencies**: Backend — CanCanCan-free here (auth is JWT-only, no abilities check in these controllers), `has_secure_token`, Alba serializers, `Spree::PermittedAttributes`, `Spree::SingleStoreResource`, publishable lifecycle events. Frontend — `packages/sdk`'s generic `request()` HTTP layer (via `sdk-core`), typed models generated from Alba serializers.

**Storage**: PostgreSQL/SQLite3 via ActiveRecord — `spree_wishlists` table (migration `20210921070813_create_spree_wishlists.rb`); `Spree::WishedItem` persists to its own table (`spree_wished_items`, predates this migrated slice, not separately tracked here).

**Testing**: RSpec + Factory Bot — model spec (`spree/core/spec/models/spree/wishlist_spec.rb`), controller specs (`spree/api/spec/controllers/spree/api/v3/store/{wishlists,wishlist_items}_controller_spec.rb`), one integration spec for OpenAPI examples (`spree/api/spec/integration/spree/api/v3/store/wishlists_spec.rb`). Vitest on the frontend (`packages/sdk/tests/wishlists.test.ts`).

**Target Platform**: Rails engine gems (`spree_core`, `spree_api`) consumed by a Spree host app; `packages/sdk` consumed by any TS storefront.

**Project Type**: Monorepo — `spree/core`, `spree/api`, `packages/sdk` only. No `packages/dashboard*`, no `packages/admin-sdk`.

**Performance Goals**: N/A — standard CRUD on small per-user collections; no documented perf target.

**Constraints**: Authenticated-customer-only (JWT); no guest wishlist token flow, unlike guest carts.

**Scale/Scope**: Per-user collection, typically single/low-digit wishlists per customer, low-dozens of items each — no pagination edge cases documented beyond the standard Pagy default on `index`.

## Constitution Check

- **I. Module Boundaries**: Touches `spree/core` (models), `spree/api` (Store API v3 controllers/serializers), `packages/sdk` (hand-written client + generated types). No cross-boundary reach — `packages/sdk` only talks to `spree/api` over HTTP. Pass.
- **II. Admin API Is the Only Frontend Data Source**: N/A — no dashboard/admin-facing frontend exists for this feature; `packages/sdk` is a Store API client, not the admin SPA.
- **III. Read/Write Field Symmetry**: Pass. Wishlist serializer reads `name`, `token`, `is_default`, `is_private`; write params (`wishlist_attributes`) accept `name`, `is_default`, `is_private` — `token` is intentionally read-only/server-generated, not a mismatch. WishedItem serializer reads `variant_id`, `wishlist_id`, `quantity`; write params (`wished_item_attributes`) accept `variant_id`, `quantity` — `wishlist_id` is implicit from the nested route, not client-writable, which is consistent (nested-resource parent ID, not a renamed field).
- **IV. Test-Backed**: RSpec model spec + two controller specs + one integration spec cover this feature; Vitest covers the SDK client. No Playwright — there is no dashboard UI to exercise. Pass (proportionate to a Store-API-only feature).
- **V. Translations and Prefixed IDs**: No user-visible dashboard strings (no dashboard surface). Prefixed IDs are used throughout (`wl_...`, `wi_...`, `has_prefix_id`). Pass.
- **VI. `docs/plans/` for Architectural Changes**: N/A — feature predates the current `docs/plans/` set and isn't referenced by any active plan; no architectural change is being made as part of this migration (documentation-only).

No violations. Complexity Tracking not applicable.

## Project Structure

### Documentation (this feature)

```text
specs/017-wishlists/
├── plan.md              # This file
└── spec.md              # Feature specification
```

(No `tasks.md`-driving research/data-model/contracts artifacts were generated — this is a reverse-engineered spec of shipped code, not a forward design.)

### Source Code (repository root)

```text
# spree/core — models
spree/core/
├── app/models/spree/wishlist.rb
├── app/models/spree/wished_item.rb
├── db/migrate/20210921070813_create_spree_wishlists.rb
├── lib/spree/testing_support/factories/wishlist_factory.rb
└── spec/models/spree/wishlist_spec.rb

# spree/api — Store API v3
spree/api/
├── app/controllers/spree/api/v3/store/wishlists_controller.rb
├── app/controllers/spree/api/v3/store/wishlist_items_controller.rb
├── app/serializers/spree/api/v3/wishlist_serializer.rb
├── app/serializers/spree/api/v3/wishlist_item_serializer.rb
├── config/routes.rb                      # `resources :wishlists do resources :items ... end`
├── lib/spree/api/dependencies.rb         # wishlist_serializer / wishlist_item_serializer registration
├── spec/controllers/spree/api/v3/store/wishlists_controller_spec.rb
├── spec/controllers/spree/api/v3/store/wishlist_items_controller_spec.rb
└── spec/integration/spree/api/v3/store/wishlists_spec.rb

# spree/core — shared permitted-params allowlist
spree/core/lib/spree/permitted_attributes.rb   # wishlist_attributes / wished_item_attributes

# packages/sdk — Store API TS client (already fully migrated)
packages/sdk/src/store-client.ts               # client.wishlists.* + .items.*
packages/sdk/src/types/generated/{Wishlist,WishlistItem}.ts
packages/sdk/src/zod/generated/{Wishlist,WishlistItem}.ts
packages/sdk/tests/wishlists.test.ts
packages/sdk/examples/wishlists/
docs/developer/sdk/store/wishlists.mdx
```

**Structure Decision**: Backend (`spree/core` models + `spree/api` Store API v3 controllers/serializers) plus an already-complete `packages/sdk` client. No `packages/dashboard`, `dashboard-ui`, `dashboard-core`, or `packages/admin-sdk` work exists or is planned — this is a Store-API-only, customer-facing feature with no back-office surface.

## Complexity Tracking

Not applicable — no Constitution violations.
