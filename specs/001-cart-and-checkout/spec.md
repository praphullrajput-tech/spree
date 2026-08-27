# Feature Specification: Cart & Checkout

**Feature Branch**: `001-cart-and-checkout`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing code (brownfield migration) — no original feature description; behavior inferred from `spree/core/app/services/spree/{cart,carts,checkout,addresses,orders}/*.rb`, `spree/core/app/models/spree/order/checkout.rb`, `spree/core/app/models/spree/checkout/*.rb`, `spree/core/app/models/spree/order_contents.rb`, `spree/api/app/controllers/spree/api/v3/store/carts*`, and their RSpec suites.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a cart and progress through checkout (Priority: P1)

A shopper (guest or logged in) adds items to a cart, supplies contact/shipping/billing information, selects a delivery method, pays, and completes the order. The checkout flow is a state machine (`cart → address → delivery → payment → confirm → complete`, with `delivery`/`payment`/`confirm` conditionally skipped per order) implemented in `spree/core/app/models/spree/order/checkout.rb`, and driven from the Store API via `Spree::Carts::Update` (`spree/core/app/services/spree/carts/update.rb`) and `Spree::Checkout::Advance` (`spree/core/app/services/spree/checkout/advance.rb`).

**Why this priority**: This is the only path by which a store ever collects revenue — without it, nothing else in the catalog/pricing/promotions system matters.

**Independent Test**: Can be fully tested by creating a cart via `POST /api/v3/store/carts`, adding a line item, patching shipping/billing addresses, selecting a shipping rate, submitting a payment, and calling `POST /api/v3/store/carts/:id/complete` — verifying the resulting order reaches the `complete` state.

**Acceptance Scenarios**:

1. **Given** an empty cart, **When** a variant is added via `Cart::AddItem`/`Carts::UpsertItems`, **Then** a line item is created, priced in the order's currency, and (if the order is already in checkout) stock is reserved for it.
2. **Given** a cart with line items and no ship/bill address, **When** an address is submitted (`Addresses::Create` / `Checkout::Update`), **Then** the order advances past the `address` step and totals/tax are recalculated.
3. **Given** an order in the `delivery` step, **When** a shipping rate is selected, **Then** shipment cost is set and totals persisted (delivery is skipped entirely if the order does not require shipping — `delivery_required?`).
4. **Given** an order in the `payment` step with a valid payment, **When** checkout is advanced to `complete`, **Then** the order transitions to `complete`, coupon codes are consumed, gift cards are redeemed, and a completion event fires.
5. **Given** an order missing a required capability (no line items, no ship address, no shipping method, no valid payment), **When** `Spree::Checkout::Requirements` is evaluated, **Then** it returns the specific unmet requirement(s) rather than a generic checkout failure.

---

### User Story 2 - Modify cart contents before completion (Priority: P1)

A shopper changes quantities, removes items, applies a discount code, changes currency, or has an item auto-removed because it went out of stock — all before the order is completed.

**Why this priority**: Cart mutation is exercised on nearly every storefront page view and is the highest-frequency code path in the feature; a bug here blocks all downstream checkout activity.

**Independent Test**: Can be fully tested by adding two line items, changing one's quantity via `Cart::SetQuantity`, removing the other via `Cart::RemoveItem`/`RemoveLineItem`, and asserting the cart's item count/total reflect only the remaining item.

**Acceptance Scenarios**:

1. **Given** a line item with quantity 3, **When** quantity is set to 1, **Then** the line item quantity updates and, if the order is mid-checkout, stock is re-reserved for the new quantity.
2. **Given** a line item, **When** it is removed via `Cart::RemoveLineItem` while the order is in checkout, **Then** stock reservations for the remaining items are recomputed; if remaining items can no longer be reserved, the removal fails with an insufficient-stock error rather than leaving the cart in an inconsistent state.
3. **Given** a variant/product that becomes inactive, deleted, discontinued, or insufficiently stocked, **When** `Cart::RemoveOutOfStockItems` runs, **Then** the affected line item(s) are removed and a structured `line_item_removed` warning is returned to the caller.
4. **Given** a cart in a currency the store no longer supports, **When** `Cart::ChangeCurrency` is called with an unsupported currency, **Then** the change is rejected with a `'Currency not supported'` error and the order is left unchanged.
5. **Given** a cart mid-checkout, **When** any mutation runs, **Then** any `checkout`-state store-credit/gift-card payments are invalidated so totals are recomputed cleanly (`Cart::Recalculate`, `Carts::Update`).

---

### User Story 3 - Manage addresses across orders (Priority: P2)

A shopper enters a new address, edits an existing saved address, or reuses a default address; the system must not silently corrupt an address that is already referenced by a completed order.

**Why this priority**: Address handling underlies both the `address` checkout step and account-level address book management; getting it wrong causes either checkout breakage or cross-order data corruption.

**Independent Test**: Can be fully tested by creating an address on an order, completing the order, then editing that same address on a new cart — verifying the completed order's address is untouched and the cart gets a new address record.

**Acceptance Scenarios**:

1. **Given** a user with no existing addresses, **When** their first address is created, **Then** it is set as both default billing and default shipping.
2. **Given** an address that is still `editable?` (not shared with a completed order), **When** it is updated, **Then** it is mutated in place.
3. **Given** an address that is no longer `editable?` (e.g. referenced by a completed order), **When** an update is submitted, **Then** a new (or matching existing) address is created/found and the order/user is re-pointed to it — the original address record is left unchanged.
4. **Given** an order whose ship/bill address is changed, **When** the update completes, **Then** the order's checkout `state` reverts to `address` so downstream steps (tax, shipping) are recalculated.
5. **Given** a checkout update request that references another user's saved address ID, **When** submitted, **Then** the request is rejected (ownership validation in `Checkout::Update#validate_address_ownership`) rather than silently attaching another user's address to the order.

---

### User Story 4 - Admin creates/edits an order on a customer's behalf (Priority: P3)

A store admin builds or edits an order directly (phone/in-person orders), bypassing the storefront cart flow, using the `Spree::Orders::*` service family.

**Why this priority**: Lower request volume than storefront checkout but required for back-office operations; reuses the same underlying pricing/shipment/tax machinery.

**Independent Test**: Can be fully tested by calling `Spree::Orders::Create` with an email, address, and item list, then verifying the resulting order has priced line items, built shipments, and (if a coupon was supplied) either an applied discount or a non-fatal discount error recorded.

**Acceptance Scenarios**:

1. **Given** admin-supplied order attributes and items, **When** `Orders::Create` runs, **Then** an order is built with resolved store/market/currency/locale/stock-location, addresses assigned, items upserted, shipments built, and totals updated.
2. **Given** an invalid coupon code supplied at creation, **When** `Orders::Create` runs, **Then** the order is still created and the coupon failure is recorded in `discount_application_errors` rather than aborting the whole order.
3. **Given** an existing order, **When** an admin cancels it, **Then** an `OrderCancellation` record is created, `canceled_at`/`canceler_id` are set, and an `order.canceled` event is published; an invalid state transition fails gracefully rather than raising.
4. **Given** a guest order, **When** "create an account" is invoked, **Then** an existing user with that email is linked, or a new user is created (random password) with name/phone copied from the order's addresses.

---

### Edge Cases

- What happens when a line item's variant has no price in the order's currency? `Cart::AddItem` / `Orders::UpsertItems` fail explicitly (`"#{variant.name} is not available in #{order.currency}"`) rather than adding a zero-priced item.
- How does the system handle removing every line item from an in-progress checkout? `Cart::Empty` destroys line items/adjustments/shipments/state_changes/promotions, restarts the checkout flow, and releases stock reservations, returning the order to `cart`.
- How does the system handle a shopper whose delivery step requires no ship address (e.g. digital-only order)? The `delivery` step is skipped automatically after being entered (`move_to_next_step_if_address_not_required`).
- What happens if `Checkout::Advance` runs but the order never reaches the requested target state? It returns a `failure(order)` result rather than partially advancing silently.
- What happens when store-credit/gift-card payments alone would fully cover the order during an interim cart update? `Carts::Update#try_advance` deliberately never auto-advances to `complete` — completion always requires an explicit `complete` call.
- What happens if a shipping rate is re-selected via the deprecated `Checkout::SelectShippingMethod`? It still functions but is marked `@deprecated`, slated for removal in 6.0 in favor of a `ShippingRate` callback that auto-updates totals.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow adding a variant to a cart, creating or incrementing a line item priced in the order's currency, and MUST reject the add if the variant has no price in that currency.
- **FR-002**: System MUST allow removing a line item entirely or decrementing its quantity, and MUST reserve/re-reserve stock for the remaining cart contents whenever the order is mid-checkout.
- **FR-003**: System MUST automatically remove line items whose product/variant has become inactive, deleted, discontinued, or insufficiently stocked, and MUST report each removal as a structured warning to the API caller.
- **FR-004**: System MUST restrict cart currency changes to currencies the store explicitly supports (`store.supported_currencies_list`).
- **FR-005**: System MUST drive checkout through an ordered state machine (`cart → address → delivery? → payment? → confirm? → complete`), skipping `delivery`/`payment`/`confirm` per order based on `delivery_required?`, `payment_required?`/`payment?`, and `confirmation_required?`.
- **FR-006**: System MUST block the transition to `complete` unless line items are all still in stock and not discontinued, and unless a valid payment exists when payment is required.
- **FR-007**: System MUST expose a pluggable requirements/step registry (`Spree::Checkout::Registry`/`Step`/`Requirement`/`DefaultRequirements`) so extensions can add checkout steps and per-step validation requirements without monkey-patching the state machine, and so the Cart API's `requirements` field stays stable across an eventual state-machine replacement.
- **FR-008**: System MUST validate that any submitted address ID on a checkout update belongs to the order's own user, rejecting cross-user address references.
- **FR-009**: System MUST treat completed-order addresses as immutable: an update to a no-longer-`editable?` address creates/reuses a separate address record instead of mutating the shared one.
- **FR-010**: System MUST revert an order's checkout state back to `address` whenever its ship or bill address changes, so downstream tax/shipping/payment steps are recalculated.
- **FR-011**: System MUST NOT auto-advance a cart update all the way to `complete`, even when existing store-credit/gift-card balance would otherwise fully cover the order total.
- **FR-012**: System MUST allow an admin to create, update, cancel, and approve an order directly via `Spree::Orders::*` services, independent of the storefront cart/checkout flow, reusing the same shipment-building and pricing logic.
- **FR-013**: System MUST support linking a completed guest order to an existing or newly-created user account, copying name/phone from the order's addresses.
- **FR-014**: System MUST resolve a cart for the Store API strictly by prefixed ID + CanCanCan authorization (guest token header or JWT), and separately support session/cookie-based `current_order` resolution for legacy storefront controllers — these are two distinct, non-overlapping resolution paths.

*Marking as unclear (found in code but not fully specified/tested):*

- **FR-015**: System behavior when `Spree::Orders::Complete` (admin) is invoked without the caller wrapping it in `Api::V3::OrderLock#with_order_lock` is [NEEDS CLARIFICATION: the service's own doc comment requires external locking but does not enforce it — concurrent-safety under a missing lock is undefined].

### Key Entities

- **Order**: the aggregate root for both "cart" (pre-checkout) and "order" (post-address) states; carries the `state` column driving the checkout state machine, line items, addresses, shipments, payments, promotions, adjustments.
- **LineItem**: a variant + quantity + price snapshot within an order; the unit cart mutations operate on.
- **Address**: shipping/billing address; may be shared across a user's default addresses and past completed orders, which drives the "immutable once referenced" behavior.
- **Checkout::Step / Checkout::Requirement**: value objects describing a pluggable checkout stage and an attachable validation rule on a stage, aggregated by `Checkout::Registry` and evaluated by `Checkout::Requirements`.
- **OrderCancellation / OrderApproval**: audit records created when an admin cancels/approves an order (see `docs/plans/5.5-6.0-order-cancellation-and-approval.md`).

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | This IS the feature: `app/services/spree/{cart,carts,checkout,addresses,orders}/*.rb`, `app/models/spree/order/checkout.rb`, `app/models/spree/checkout/*.rb`, `app/models/spree/order_contents.rb` |
| `spree/api` (Store/Admin API v3) | Yes | Store API `carts`, `carts/items`, `carts/fulfillments`, `carts/payments`, `carts/discount_codes`, `carts/store_credits` controllers; `Spree::Api::V3::CartResolvable` concern |
| `packages/dashboard` (admin SPA) | No | Admin order editing currently uses the legacy Rails admin (`spree/admin/app/controllers/spree/admin/checkouts_controller.rb`), not the SPA, per the files inspected |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Yes | `packages/sdk` generated types (`Cart`, `LineItem`, `Address`, `Payment`, `PaymentMethod`, `Fulfillment`) mirror the Store API cart/checkout serializers — regenerated, not hand-written |
| `docs/plans/` | Yes | Governed by `docs/plans/6.0-cart-order-split.md` (Cart/Order model separation this whole dual `Cart::*`/`Carts::*` namespace is migrating toward) and `docs/plans/6.0-stock-reservations.md` (stock reservation calls seen throughout `Cart::*`) |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints** (existing, documented for completeness): `POST /api/v3/store/carts`, `GET/PATCH/DELETE /api/v3/store/carts/:id`, `PATCH /api/v3/store/carts/:id/associate`, `POST /api/v3/store/carts/:id/complete`, `POST/PATCH/DELETE /api/v3/store/carts/:id/items`, `POST/DELETE /api/v3/store/carts/:id/discount_codes`, `POST/DELETE /api/v3/store/carts/:id/gift_cards`, `PATCH /api/v3/store/carts/:id/fulfillments`, `POST /api/v3/store/carts/:id/payments`, `.../payment_sessions` (+ nested `complete`), `POST/DELETE /api/v3/store/carts/:id/store_credits`.
- **Serializer fields (read)**: cart-level `email`, `customer_note`, `market_id`, `currency`, `locale`, `shipping_address`, `billing_address`, `metadata`, `items[]` (`variant_id`, `quantity`, `metadata`, `options`) — matched 1:1 by `permitted_params` in `carts_controller.rb` per read/write symmetry (Constitution Principle III).
- **Auth**: Store API publishable key (guest) or JWT (logged-in customer), resolved per-request by `Spree::Api::V3::CartResolvable` (`x-spree-token` header for guest carts, CanCanCan `authorize!` otherwise).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A cart can go from first item added to a `complete` order state without any manual state-column manipulation — the state machine transitions unassisted whenever guard conditions are met.
- **SC-002**: Removing a line item never leaves the order in a state where remaining items have inconsistent stock reservations — either the removal succeeds with reservations correct, or it fails outright with an explicit insufficient-stock error.
- **SC-003**: No update to an address ever mutates an address record referenced by a different, already-completed order.
- **SC-004**: Every cart-mutating service returns a `success`/`failure` result object with a specific, machine-readable error rather than raising unhandled exceptions for expected failure modes (unsupported currency, missing variant price, IDOR address reference).
- **SC-005**: 26+ existing RSpec spec files across `cart/`, `carts/`, `checkout/`, `addresses/`, `orders/`, and the `order/checkout` state machine pass, covering the scenarios above (see Migration Notes for exact gaps).

## Assumptions

- The dual `Spree::Cart::*` (singular) and `Spree::Carts::*` (plural) service namespaces are both currently live: `Cart::*` is the legacy layer reached via `Spree::OrderContents` (`order.contents.add`), while `Carts::*` is what the Store API v3 controllers actually call. Both are treated as in-scope for this spec since both are exercised in production code paths today.
- "Checkout" in this spec refers to the state-machine-driven flow in `Order::Checkout`, not the deprecated legacy Rails `spree/admin/app/controllers/spree/admin/checkouts_controller.rb`, which is out of scope per the constitution's "do not add new features to `spree/admin`" guidance.
- The `Checkout::Registry`/`Step`/`Requirement` layer is documented in-code as a forward-compatible abstraction for the pending Cart/Order model split (`docs/plans/6.0-cart-order-split.md`); this spec describes its current behavior against the existing state machine, not its eventual Spree 6.0 backing store.
- Admin order creation/editing (`Spree::Orders::*`) is treated as in-scope because it shares the same pricing/shipment/tax primitives as storefront checkout, even though it is invoked from a different surface (legacy Rails admin controllers, not `packages/dashboard`).

## Migration Notes

Honest gaps found while reverse-engineering this feature:

- **Missing specs** for several services that are otherwise exercised only indirectly: `Cart::Create`, `Cart::Recalculate` (invoked by nearly every cart mutation, yet has no dedicated spec), `Cart::Update`, `Cart::EstimateShippingRates`, `Checkout::Complete`, `Checkout::Next`, `Addresses::Create`, `Orders::BuildShipments`, `Orders::UpdateContactInformation`.
- **`Cart::ChangeCurrency`** swallows the update failure with a bare `rescue false`, collapsing any underlying `ActiveRecord` error into a generic `'Failed to update order'` message — root cause is not surfaced or logged.
- **`Orders::Complete` (admin)** documents a requirement to be called inside `Api::V3::OrderLock#with_order_lock` but does not enforce or assert it itself; there is no test confirming behavior when called unlocked, which is a latent concurrency risk.
- **`Carts::Update#try_advance`** wraps checkout-advance in a bare `rescue StandardError => e; Rails.error.report`, silently continuing past transition errors — there is no spec confirming the resulting warnings are still present on `order.reload` as the inline comment claims.
- **Address immutability behavior** (`Addresses::Update` creating a new address instead of mutating a shared one) is not obvious from the API surface — a client `PATCH`ing an address can silently get back a different address ID. This is undocumented outside the source comment and could confuse API consumers; worth a follow-up `docs/developer/` note.
- **`Checkout::SelectShippingMethod`** is `@deprecated` and slated for removal in 6.0, but is still on the only code path certain flows (Quick Checkout + Google Pay via `Checkout::Advance`) rely on — its removal is a cross-cutting risk that should be tracked against `docs/plans/6.0-cart-order-split.md` before it is deleted.
- **FR-015** above: no test coverage found for the "no lock held" case of `Orders::Complete`.
