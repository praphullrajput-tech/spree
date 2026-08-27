# Feature Specification: Order Management

**Feature Branch**: `002-order-management`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — no original user description; behavior inferred from `spree/core/app/models/spree/order.rb`, `spree/core/app/models/spree/order_updater.rb`, `spree/admin/app/controllers/spree/admin/orders_controller.rb`, `spree/api/app/controllers/spree/api/v3/admin/orders_controller.rb`, and related finders/serializers/presenters/dashboard hooks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin views and manages an order's lifecycle (Priority: P1)

An admin user opens an order in the back office to inspect its contents, totals, and current status (draft/placed/canceled, plus payment/shipment sub-states), and drives it through cancel, approve, resume, or resend-confirmation actions.

**Why this priority**: This is the core, highest-traffic admin workflow — every order that comes through the store passes through this view for fulfillment, support, and dispute handling.

**Independent Test**: Create a completed order via factory, hit `GET /admin/orders/:id` (legacy Rails) or `GET /api/v3/admin/orders/:id` (v3), and confirm status, totals, and line items render; call `PATCH /api/v3/admin/orders/:id/cancel` and confirm `status` becomes `canceled` and `shipment_state`/`payment_state` update accordingly.

**Acceptance Scenarios**:

1. **Given** a completed order with a valid canceler, **When** the admin cancels the order (`Order#canceled_by`), **Then** `status` becomes `canceled`, all shipments are canceled, non-store-credit payments are voided/canceled, and an `order.updated`-triggering hook (`after_cancel`) recomputes totals.
2. **Given** a canceled order that is resumed, **When** `after_resume` runs, **Then** `status` reverts to `placed`, shipments resume, risk is reconsidered, and `order.resumed` webhook/event fire.
3. **Given** an order with `considered_risky` and no approver, **When** an admin approves it (`Order#approved_by`), **Then** `approved_at`/`approver` are set and `can_approve?` becomes false.
4. **Given** a completed order, **When** the admin requests resend confirmation, **Then** `order.completed` (legacy: `order.resend_confirmation_email` event) is published and the confirmation email flow re-fires.

---

### User Story 2 - Admin creates and edits a draft order (Priority: P2)

An admin creates a new order on behalf of a customer (draft), attaches a customer, items, addresses, and later completes it — mirroring "quick order" / phone-order workflows.

**Why this priority**: Common secondary workflow (manual/phone orders, quotes) but not on the primary storefront checkout path.

**Independent Test**: `POST /api/v3/admin/orders` with `email`, `items[]` and address payloads; assert `status: "draft"` order returned with prefixed `or_...` id; then `PATCH .../complete` and assert it transitions to a completed state (`completed_at` present).

**Acceptance Scenarios**:

1. **Given** valid `order_create_params` (email, currency, items, addresses), **When** `Spree.order_create_service` succeeds, **Then** a new `Spree::Order` scoped to `current_store` is returned serialized via `Spree::Api::V3::Admin::OrderSerializer`.
2. **Given** an existing draft order and updated attributes (customer, addresses, items, market/channel), **When** `PATCH /api/v3/admin/orders/:id` runs under `with_order_lock`, **Then** `Spree.order_update_service` applies changes or returns the order's validation errors (422).
3. **Given** the order-create/update params reference `customer_id` or `user_id`, **When** resolved, **Then** the record is looked up via `Spree.user_class.find_by_param!` (prefixed-ID aware).

---

### User Story 3 - Admin lists and filters orders (Priority: P2)

An admin browses the orders index (legacy Rails table and/or dashboard SPA table), filtering/searching by customer name/email, channel, status, and sorting by completion date, to locate a specific order.

**Why this priority**: Necessary for day-to-day order operations but depends on Story 1/2 data existing.

**Independent Test**: Seed several orders with distinct emails/names; call `Spree::Order.search("jane")` and confirm only matching orders (by bill address first/last name or email) return; confirm the admin index scope (`current_store.orders.accessible_by(...).complete`) excludes incomplete/cart orders by default.

**Acceptance Scenarios**:

1. **Given** a completed order with billing address "Jane Doe" and email `jane@x.com`, **When** searching `"jane"` or `"doe"` or the exact email, **Then** the order is returned; unrelated orders are not.
2. **Given** the admin orders index, **When** no explicit sort is requested, **Then** results default to `completed_at desc` (`collection_default_sort`).
3. **Given** Ransack query params, **When** filtering by `state`, `status`, `payment_state`, `shipment_state`, `channel_id`, or `store`/`bill_address`/`ship_address` associations, **Then** only allow-listed attributes/associations/scopes (`whitelisted_ransackable_*` on `Spree::Order`) are queryable.

---

### Edge Cases

- Canceling an order paid entirely by store credit/gift card voids (not refunds) the store-credit payment (`after_cancel` gift-card branch).
- `outstanding_balance` for a canceled order returns the negative of `payment_total` (refund-owed sentinel) rather than `total - payment_total`.
- An order routed through an unregistered/typo'd `order_routing_strategy` class name logs a warning and falls back to `Spree::OrderRouting::Strategy::Rules` rather than raising.
- `guest_checkout_disallowed?` blocks guest order completion when the channel has `storefront_prices_hidden?` set, even if `guest_checkout` is otherwise enabled — treated as a hard business rule, not merely a display concern.
- Currency change on a persisted, non-market order triggers `resolve_market_from_currency`, silently reassigning `market` to whichever store market matches the new currency (first match wins if multiple markets share a currency — unresolved ambiguity, see Migration Notes).
- `ensure_updated_shipments` destroys shipments and restarts checkout to `cart` state whenever currency changes on an incomplete order with existing shipments — no confirmation step.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a canonical `status` field (`draft`/`placed`/`canceled`) on `Spree::Order`, independent of the legacy `state` checkout-flow column, validated against `Order::STATUSES`.
- **FR-002**: System MUST recompute `item_total`, `shipment_total`, `adjustment_total`, `promo_total`, `included_tax_total`, `additional_tax_total`, and `total` via `Spree::OrderUpdater#update_totals` whenever line items, shipments, or adjustments change, and persist them via `update_columns` (bypassing callbacks) in `persist_totals`.
- **FR-003**: System MUST derive `payment_state` (`balance_due`/`credit_owed`/`paid`/`failed`/`void`) and `shipment_state` (`backorder`/`partial`/`ready`/`pending`/`shipped`/`canceled`) from live payment/shipment data rather than storing them as independently-editable fields.
- **FR-004**: System MUST support canceling a completed, non-canceled order (`allow_cancel?` gate), recording the canceling user and timestamp, voiding/canceling associated payments, and canceling all shipments.
- **FR-005**: System MUST support resuming a canceled order back to `placed`, re-resuming shipments and re-running risk assessment.
- **FR-006**: System MUST support admin approval of risky orders (`considered_risky` + no `approved_at`), recording `approver` and `approved_at`.
- **FR-007**: Admin API MUST enforce per-request advisory locking (`OrderLock`/`with_order_lock`) around `update`, `complete`, `cancel`, `approve`, `resume` to prevent concurrent-write races on the same order.
- **FR-008**: System MUST scope all order access through `current_store.orders` (Store-scoped, per `Spree::SingleStoreResource`) — never a bare `Spree::Order` query — for both legacy admin and Admin API v3 controllers.
- **FR-009**: System MUST return/accept prefixed IDs (`or_...`) for orders and prefixed IDs for related resources (`customer_id`, `channel_id`, `market_id`, `preferred_stock_location_id`, `approver_id`, `canceler_id`, `created_by_id`) in the Admin API v3 order representation.
- **FR-010**: System MUST expose an order summary breakdown (subtotal, shipping, promo, manual/custom adjustments, tax, total, payment total, outstanding balance) via `Spree::Admin::OrderSummaryPresenter` for the legacy admin order view.
- **FR-011**: System MUST support full-text-ish order search across order number, billing first/last name, and exact email match (`Spree::Order.search`/`.multi_search`).
- **FR-012**: Admin API create/update MUST resolve `customer_id`/`user_id` params via `Spree.user_class.find_by_param!` and route persistence through `Spree.order_create_service` / `Spree.order_update_service` (swappable via the Dependencies registry), never inline `Order.create`/`update` in the controller.

### Key Entities *(include if feature involves data)*

- **Spree::Order**: The central commerce entity — line items, addresses, payments, shipments/fulfillments, adjustments, promotions, cancellations/approvals, store credit, gift card, tags, metadata/metafields. Belongs to `store`, optionally `market`, `channel`, `user` (customer), `created_by`/`approver`/`canceler` (admin users), `preferred_stock_location`.
- **Spree::OrderUpdater**: Stateless calculator/persister for order totals and derived state (`payment_state`, `shipment_state`); invoked via `Order#updater`/`#update_with_updater!`.
- **Spree::OrderCancellation / Spree::OrderApproval**: First-class records of cancel/approve actions (`has_many :cancellations`, `:approvals`), per `docs/plans/5.5-6.0-order-cancellation-and-approval.md`.
- **Spree::Orders::FindComplete / FindCurrent**: Finder objects encapsulating "look up a completed order by user/number/prefix_id/token/store/email" and "find the customer's current incomplete cart," respectively.
- **Spree::Admin::OrderSummaryPresenter**: View-model that assembles the order totals/adjustments breakdown for the legacy admin order show page.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Order` + concerns (`order/checkout.rb`, `order/payments.rb`, `order/digital.rb`, `order/store_credit.rb`, `order/gift_card.rb`, `order/address_book.rb`, `order/currency_updater.rb`, `order/webhooks.rb`), `Spree::OrderUpdater`, `Spree::Orders::FindComplete`/`FindCurrent`, `Spree.order_create_service`/`order_update_service`/`order_complete_service`/`order_cancel_service`/`order_approve_service` (Dependencies-registered service objects) |
| `spree/api` (Store/Admin API v3) | Yes | `Spree::Api::V3::Admin::OrdersController` (create/update/complete/cancel/approve/resume/resend_confirmation), nested `orders/{adjustments,fulfillments,gift_cards,items,payments,refunds,store_credits}_controller.rb`, `Spree::Api::V3::OrderSerializer` + `Admin::OrderSerializer` |
| `spree/admin` (legacy Rails admin — being phased out) | Yes | `Spree::Admin::OrdersController` (index/show/new/create/edit/cancel/resend/destroy) + nested `orders/{adjustments,billing_address,contact_information,customer_returns,order_promotions,payment_links,return_authorizations,shipping_address,user}_controller.rb`, `Spree::Admin::OrderSummaryPresenter` |
| `packages/dashboard` (admin SPA) | Yes | `routes/_authenticated/$storeId/orders/{index,new,drafts,$orderId}.tsx`, `hooks/use-order.ts`, `schemas/order.ts`, `tables/orders.tsx` — consumes Admin API v3 only |
| `packages/dashboard-ui` / `dashboard-core` | No | No order-specific primitives or registry entries found beyond generic table/query infra already documented elsewhere |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated types (`admin-sdk/src/types/generated/Order.ts`, `LineItem.ts`, `Payment.ts`, `Fulfillment.ts`, `Adjustment.ts`, `Discount.ts`, `Reimbursement.ts`, `ReturnAuthorization.ts`) — regenerated from serializers, not hand-written |
| `docs/plans/` | Yes | Governed by `6.0-cart-order-split.md` (Cart/Order model separation — pending), `6.0-normalize-state-to-status.md` (`state`→`status` rename — `status` column already shipped alongside legacy `state`), `5.5-6.0-order-cancellation-and-approval.md` (shipped models consumed here), `6.0-split-adjustments.md` (Adjustment polymorphism referenced by `OrderSummaryPresenter`/`update_adjustment_total`) |

### API Contract *(include if feature touches spree/api)*

- **Endpoints**: `POST /api/v3/admin/orders`, `GET /api/v3/admin/orders`, `GET/PATCH/DELETE /api/v3/admin/orders/:id`, `PATCH /api/v3/admin/orders/:id/{complete,cancel,approve,resume}`, `POST /api/v3/admin/orders/:id/resend_confirmation`
- **Serializer fields (read)**: Store API (`V3::OrderSerializer`): `number, email, customer_note, market_id, channel_id, currency, locale, total_quantity, fulfillment_status, payment_status, item_total..total (+display_*), amount_due, completed_at, discounts, items, fulfillments, payments, billing_address, shipping_address, gift_card, market`. Admin API adds: `status, last_ip_address, considered_risky, confirmation_delivered, store_owner_notification_delivered, internal_note, approver_id, canceler_id, created_by_id, customer_id, preferred_stock_location_id, canceled_at, approved_at, payment_total, display_payment_total, tags, metadata, created_at, updated_at`, plus admin-serialized associations (`adjustments`, `return_authorizations`, `reimbursements`, `payment_methods`).
- **Read/write symmetry**: `order_update_params`/`order_create_params` permit `email, customer_id, user_id, currency, locale, market_id, channel_id, preferred_stock_location_id, customer_note, internal_note, metadata, tags, ship_address/bill_address, items` — matching serializer field names 1:1 (e.g. `customer_note` maps to `Order#customer_note` alias of `special_instructions`).
- **Auth**: Admin API secret key (scopes) or Admin JWT + CanCanCan (`authorize_resource!` maps state-transition actions to the `:update` permission).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can locate a specific completed order by partial customer name, exact email, or order number via `Spree::Order.search` in a single query without a full table scan on unrelated columns (uses `arel_table`/`ILIKE`-style `matches` predicates).
- **SC-002**: Order totals (`total`, `payment_state`, `shipment_state`) remain consistent with underlying line items/payments/shipments after any mutating action (cancel, resume, item/payment/shipment change) — verified by `OrderUpdater#update` being invoked as part of every state-changing path found in code (`finalize!`, `fulfill!`, `after_cancel`, `after_resume`, `apply_free_shipping_promotions`).
- **SC-003**: Concurrent admin-initiated mutations (`update`, `complete`, `cancel`, `approve`, `resume`) on the same order do not corrupt state, enforced by `with_order_lock` wrapping every such Admin API v3 action.
- **SC-004**: 100% of order and related-resource IDs returned by the Admin API v3 order endpoints are prefixed (`or_`, `customer_`, `market_`, `channel_`, etc.) — no raw integer/UUID leaks in the serializer as read.

## Assumptions

- The `state` (checkout-flow state machine) and `status` (draft/placed/canceled) columns coexist during the 6.0 migration window (`docs/plans/6.0-normalize-state-to-status.md`); this spec documents both as currently implemented.
- `Spree.order_create_service`, `order_update_service`, `order_complete_service`, `order_cancel_service`, `order_approve_service` are assumed registered in `Spree::Dependencies` per repo convention, though their concrete implementations were not opened in this pass (out of scope: service internals, in scope: controller contract).
- Legacy Rails `spree/admin` orders controller is treated as the source-of-truth for current business rules per constitution Principle I, but is explicitly being phased out — no new admin UI work should target it.
- Dashboard SPA order routes (`index.tsx`, `new.tsx`, `drafts.tsx`, `$orderId.tsx`) were located but not individually read line-by-line in this pass; `use-order.ts` confirms the `expand[]` contract consumed from `@spree/admin-sdk`.

## Migration Notes

Honest gaps found while reverse-engineering this spec (not fixed here — flagged for follow-up):

- **No RSpec coverage found for `OrderUpdater#update_shipment_state`'s "unassigned inventory units" TODO branch** — the code has a commented-out `# TODO: inventory unit states?` in `update_shipment_state` (order_updater.rb:166-172) indicating a known-incomplete edge case (shipments exist but some inventory units are unassigned) that is neither implemented nor tested.
- **`resolve_market_from_currency` ambiguity**: if a store has multiple markets sharing the same currency, `store.markets.find_by(currency: currency)` picks the first match with no documented tie-breaker (order.rb:1188-1194). No spec found exercising the multi-market-same-currency case.
- **No integration/controller spec located for the Admin API v3 `OrdersController#complete`, `#approve`, `#resume`, or `#resend_confirmation` actions** in the reviewed paths — only the model-level `Spree::Order` spec (`order_spec.rb`) was found covering `#cancel`/`#canceled_by`/`#finalize!`/`#after_resume`. This violates the constitution's "API integration tests for happy-path" guidance if no `spec/integration` file exists for these endpoints; scope did not include exhaustively grepping `spree/api/spec/integration`, so this should be verified before treating it as a confirmed gap.
- **Guest-checkout gating interaction is subtle and undertested from what was seen**: `guest_checkout_disallowed?`'s `prices_hidden` override (order.rb:516-531) is documented in a code comment as intentional business logic but no spec file was opened confirming test coverage of this exact branch combination (guest + prices_hidden + guest_checkout enabled).
- **Error handling for `order_routing_strategy` misconfiguration is a soft-fail (log + fallback)** by design (order.rb:799-813), which is good defensively, but there's no alerting/metrics hook visible in this code path — a persistently-misconfigured channel/store would silently degrade to the default routing strategy with only a log line as evidence.
- **`Order#can_be_destroyed?` is deprecated in favor of `can_be_deleted?`** but the legacy admin `OrdersController#destroy` action still calls `@order.destroy` directly (not through a cancellation/deletion service) — no guard against destroying an order with completed payments was visible in the controller itself; the guard exists only as an unused-here `can_be_deleted?` predicate on the model.
- **Dashboard SPA order routes were located but not read in full** (`index.tsx`, `new.tsx`, `drafts.tsx`, `$orderId.tsx`, `tables/orders.tsx`, `schemas/order.ts`) — the Module Impact and API Contract sections above are inferred from `use-order.ts` and the Admin API v3 serializer/controller only; a follow-up pass should open these files to confirm exact form fields and table columns match the read/write symmetry principle.
