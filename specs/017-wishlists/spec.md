# Feature Specification: Wishlists

**Feature Branch**: `017-wishlists`

**Created**: 2026-08-24

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — customer wishlists via the Store API v3.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create and manage wishlists (Priority: P1)

A logged-in storefront customer creates one or more named wishlists (e.g. "Birthday", "Default"), each private or shared, with exactly one marked as their default.

**Why this priority**: Core capability — without a wishlist container, nothing else in this feature can exist.

**Independent Test**: Authenticate as a customer, `POST /api/v3/store/wishlists` with a name, confirm it is returned with a prefixed ID (`wl_...`) and a unique `token`; list/show/update/delete via the standard collection endpoints.

**Acceptance Scenarios**:

1. **Given** an authenticated customer with no wishlists, **When** they `POST /api/v3/store/wishlists` with `{ name: "Birthday" }`, **Then** a wishlist is created scoped to the current store and current user, with a generated `token`.
2. **Given** a customer marks a new wishlist `is_default: true`, **When** the record is saved, **Then** any previously-default wishlist for that user/store is unset (`ensure_default_exists_and_is_unique`), leaving exactly one default.
3. **Given** a customer with multiple wishlists, **When** they `GET /api/v3/store/wishlists`, **Then** only wishlists belonging to their own user and the current store are returned (`current_user.wishlists.for_store(current_store)`).

---

### User Story 2 - Add/update/remove variants in a wishlist (Priority: P2)

A customer adds a specific product variant (with quantity) to one of their wishlists, adjusts the quantity, or removes it.

**Why this priority**: The wishlist container alone has no value without items — this is the feature's actual payload.

**Independent Test**: `POST /api/v3/store/wishlists/:wishlist_id/items` with a `variant_id` and `quantity`; confirm it appears nested under the wishlist (`?expand=items`), then `PATCH`/`DELETE` it.

**Acceptance Scenarios**:

1. **Given** a wishlist owned by the current customer, **When** they `POST .../items` with a valid `variant_id` and `quantity`, **Then** a `Spree::WishedItem` is created linking that variant to the wishlist.
2. **Given** a variant already exists on a wishlist, **When** the same `variant_id` is added again, **Then** the request fails validation (uniqueness of `variant` scoped to `wishlist`).
3. **Given** a wished item, **When** `quantity` is set to `0` or a non-integer, **Then** the request fails validation (`greater_than: 0`, `only_integer: true`).
4. **Given** a wished item on wishlist A, **When** a request targets it via `wishlist_id` for wishlist B (or a wishlist owned by another user), **Then** it 404s — item lookup is always scoped through `set_parent` (`current_user.wishlists.find_by_prefix_id!`).

---

### Edge Cases

- Deleting a wishlist cascades and destroys its `wished_items` (`dependent: :destroy`).
- A wished item's `price`/`total` return `nil` for the requested currency if the variant has no price in that currency (no exception raised).
- All wishlist and wishlist-item endpoints require authentication (`prepend_before_action :require_authentication!`) — there is no guest/anonymous wishlist token flow in this API surface (unlike guest carts, which use `X-Spree-Token`).
- A wishlist is validated as belonging to exactly one store (`Spree::SingleStoreResource`) — no cross-store sharing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow an authenticated customer to create, list, show, update, and delete their own wishlists via the Store API.
- **FR-002**: System MUST scope all wishlist reads/writes to the current authenticated user and the current store (`current_user.wishlists.for_store(current_store)`).
- **FR-003**: System MUST enforce at most one default wishlist per user per store, automatically clearing prior defaults on save.
- **FR-004**: System MUST allow an authenticated customer to add, update, and delete items (variant + quantity) within a wishlist they own.
- **FR-005**: System MUST reject duplicate variants on the same wishlist and non-positive/non-integer quantities.
- **FR-006**: System MUST expose prefixed IDs (`wl_...` for wishlists, `wi_...` for wished items) in all API responses and accept them on nested routes.
- **FR-007**: System MUST publish lifecycle events (`wishlist.created`/`updated`/`deleted`, and equivalent for wished items) for webhook subscribers (`publishes_lifecycle_events`).
- **FR-008**: System MUST expose wished items on a wishlist only when explicitly requested (`?expand=items`), not by default.

### Key Entities

- **Wishlist**: A named, user-owned, store-scoped collection of desired variants. Attributes: `name`, `token` (secure, unique), `is_private`, `is_default`. Belongs to one `Spree.user_class` and one `Spree::Store`; has many `WishedItem`s (and, through them, `variants`/`products`).
- **WishedItem**: A single variant entry on a wishlist, with a `quantity`. Belongs to one `Wishlist` and one `Spree::Variant`; unique per `(wishlist, variant)`. Exposes computed `price(currency)` / `total(currency)` via `variant.amount_in`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Wishlist`, `Spree::WishedItem` models; migration `20210921070813_create_spree_wishlists.rb` (wished items table predates this feature slice and isn't separately migrated here — see Migration Notes) |
| `spree/api` (Store/Admin API v3) | Yes | `Spree::Api::V3::Store::WishlistsController` + `WishlistItemsController`, `Spree::Api::V3::WishlistSerializer` + `WishlistItemSerializer`, nested routes under `/api/v3/store/wishlists`. Store API only — no Admin API v3 controller/serializer exists for wishlists. |
| `packages/dashboard` (admin SPA) | No | No admin route for wishlists; only referenced as a webhook event group (`wishlist.created/updated/deleted`) in the webhook-endpoint event picker |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Yes / No | `packages/sdk` has a full hand-written `client.wishlists` resource (list/get/create/update/delete + nested `.items`) and generated `Wishlist`/`WishlistItem` types+Zod. `packages/admin-sdk` has no wishlist surface (matches no Admin API). |
| `docs/plans/` | No | Feature predates the 6.0 plan set; no active `docs/plans/*.md` references or governs wishlists |

### API Contract

- **Endpoints**: `GET/POST /api/v3/store/wishlists`, `GET/PATCH/DELETE /api/v3/store/wishlists/:id`, `POST/PATCH/DELETE /api/v3/store/wishlists/:wishlist_id/items/:id` (create/update/destroy only — no index/show for individual items outside the parent's `?expand=items`)
- **Serializer fields (read)**: Wishlist — `name`, `token`, `is_default`, `is_private`, `items` (expandable, nested `WishlistItem`s). WishlistItem — `variant_id`, `wishlist_id`, `quantity`, `variant` (nested).
- **Write params**: `wishlist_attributes = [:name, :is_default, :is_private]`; `wished_item_attributes = [:variant_id, :quantity]` (via `Spree::PermittedAttributes`, `spree/core/lib/spree/permitted_attributes.rb`) — matches serializer read fields except `token`, which is server-generated and never client-writable.
- **Auth**: JWT customer auth only (`require_authentication!`); no publishable-key guest access and no secret-key Admin API surface.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A customer can create a wishlist and add an item to it in two API calls.
- **SC-002**: Exactly one wishlist per user/store is ever flagged `is_default: true`, verified by `wishlist_spec.rb`.
- **SC-003**: Attempting to duplicate a variant on the same wishlist, or access another user's wishlist/item, always fails (422 / 404 respectively), verified by controller specs.

## Assumptions

- Wishlists are single-store resources (`Spree::SingleStoreResource`); the historic multi-store `spree_wishlists_stores`-style sharing is out of scope here.
- No guest (anonymous) wishlist support is in scope — this mirrors the current code, which requires authentication on every action.
- A legacy `Spree::V2::Storefront::WishlistSerializer` and `Spree::Api::V2::Platform::WishlistSerializer` exist for older API versions but are out of scope for this V3 spec.

## Migration Notes

- **No Admin API v3 controller/serializer for wishlists** — this is a Store API (customer-facing) only feature. There's nothing for store staff to view/manage a customer's wishlist through the back office today.
- **No admin dashboard (`packages/dashboard`) UI** — no route, hook, or page for wishlists. The only dashboard reference is the webhook event-group picker listing `wishlist.created/updated/deleted` as subscribable event types.
- **No Playwright e2e coverage** (`packages/dashboard/e2e`) — consistent with there being no dashboard UI to exercise.
- **`packages/admin-sdk` has no wishlist methods** — consistent with there being no Admin API endpoint to wrap.
- Backend test coverage is solid: `spree/core/spec/models/spree/wishlist_spec.rb` (141 lines) plus `spree/api/spec/controllers/.../wishlists_controller_spec.rb` (188 lines) and `wishlist_items_controller_spec.rb` (153 lines), plus a happy-path integration spec (`spree/api/spec/integration/.../wishlists_spec.rb`, 264 lines) used for OpenAPI generation.
- `packages/sdk` (Store API TS client) already has full CRUD coverage (`client.wishlists.*`, `client.wishlists.items.*`) plus generated types/Zod schemas and its own Vitest suite (`packages/sdk/tests/wishlists.test.ts`) and docs (`docs/developer/sdk/store/wishlists.mdx`) — this side is fully migrated already.
