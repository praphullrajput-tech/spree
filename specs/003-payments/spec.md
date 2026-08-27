# Feature Specification: Payments

**Feature Branch**: `003-payments`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing code as part of `/speckit.brownfield.migrate`. No original user description — this document describes the payment capture/authorization system as built in `spree/core`, `spree/api`, `spree/admin`, and `packages/dashboard`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin captures/voids an order payment (Priority: P1)

An admin viewing an order's payment tab needs to authorize, capture, or void a payment against a configured payment method (gateway or store credit), and see the result reflected on the order.

**Why this priority**: Core to order fulfillment — without capture/void, revenue can't be collected or reversed.

**Independent Test**: Create an order with a `Spree::Gateway::Bogus` payment method, add a payment, call capture, and confirm the payment transitions to `completed` and the order's payment/shipment state updates.

**Acceptance Scenarios**:

1. **Given** an order in the `payment` state with a bogus/test credit card, **When** an admin creates a payment via `Spree::Admin::PaymentsController#create`, **Then** the payment authorizes or purchases (`auto_capture?`) and the order advances via `order.next`.
2. **Given** a `pending`/`checkout` payment, **When** the admin calls `capture` (full or partial amount), **Then** a `Spree::PaymentCaptureEvent` is recorded, the payment transitions to `completed` on full capture, and any uncaptured remainder is split into a new pending payment (`split_uncaptured_amount`).
3. **Given** any non-`failed`/non-`void` payment, **When** the admin calls `void`, **Then** the gateway is asked to void the transaction and, on success, the payment transitions to `void`.

---

### User Story 2 - Admin configures a payment method / gateway (Priority: P1)

A store admin needs to add, configure (preferences/API keys), enable/disable, and reorder payment methods available at checkout, either through the legacy Rails admin or the React dashboard Settings > Payment Methods page.

**Why this priority**: No payments can be taken until a store has at least one active, correctly configured payment method.

**Independent Test**: Create a payment method of an allowed `Spree.payment_methods` type via the Admin API (`POST /api/v3/admin/payment_methods`) or the dashboard sheet, set its preferences, and confirm it appears active in `Spree::PaymentMethod.available` for the store.

**Acceptance Scenarios**:

1. **Given** the list of registered provider types (`Spree.payment_methods`), **When** an admin picks a type and fills in name/preferences in the dashboard `PaymentMethodForm`, **Then** a new STI subclass instance of `Spree::PaymentMethod` is created scoped to the current store.
2. **Given** an existing payment method, **When** an admin toggles `active`/`auto_capture`/`storefront_visible` or edits preferences, **Then** the update persists and the checkout/admin lists reflect it (password-type preferences are not overwritten when submitted blank).
3. **Given** multiple payment methods, **When** an admin reorders them (`acts_as_list`), **Then** their `position` changes and the checkout picker lists them in that order.

---

### User Story 3 - Customer completes checkout payment via a hosted/embedded flow (Priority: P2)

A storefront customer pays for a cart using a provider-hosted or embedded payment flow (e.g. Stripe Elements) driven by `Spree::PaymentSession`, without the storefront needing gateway-specific code beyond the generic session lifecycle.

**Why this priority**: Needed for real (non-test) gateways that require client-side tokenization/3DS rather than server-side raw-card submission.

**Independent Test**: Call `create_payment_session` on a session-requiring payment method (e.g. `Spree::Gateway::Bogus`, `session_required? == true`), drive it through `pending → processing → completed`, and confirm `find_or_create_payment!` produces a `Spree::Payment` linked by `response_code`/`external_id`.

**Acceptance Scenarios**:

1. **Given** a cart and a payment method with `session_required?`, **When** the Store API creates a payment session, **Then** a `Spree::PaymentSession` (STI, provider-specific) is created in `pending` status via `payment_method.create_payment_session`.
2. **Given** an active payment session, **When** the provider confirms success, **Then** `payment_method.complete_payment_session` verifies with the provider, creates/patches the `Spree::Payment`, and transitions the session to `completed` — without completing the order itself (`Carts::Complete` owns that).
3. **Given** a provider webhook arrives, **When** `Spree::Api::V3::Webhooks::PaymentsController` calls `payment_method.parse_webhook_event`, **Then** the corresponding session/payment is updated (captured/authorized/failed/canceled) idempotently.

---

### User Story 4 - Customer saves a payment method for future use (Priority: P3)

A logged-in customer tokenizes a card/wallet outside of an active order (e.g. account "Payment Methods" page) via `Spree::PaymentSetupSession`, producing a reusable `Spree::CreditCard`/`Spree::PaymentSource`.

**Why this priority**: Improves repeat-purchase UX; not required for a first checkout to work.

**Independent Test**: Call `create_payment_setup_session` for a customer on a `setup_session_supported?` payment method, complete it, and confirm a `Spree::CreditCard` (or other `Spree::PaymentSource` subtype) is created and linked via `payment_source` polymorphic association.

**Acceptance Scenarios**:

1. **Given** a customer and a setup-session-capable payment method, **When** the Store API creates a payment setup session, **Then** a `Spree::PaymentSetupSession` is created in `pending` status.
2. **Given** provider confirmation of the tokenization, **When** `complete_payment_setup_session` runs, **Then** a payment source record is created/linked and the session transitions to `completed`.

---

### Edge Cases

- What happens when a gateway call raises `Spree::PaymentConnectionError`? → `protect_from_connection_error` catches it, transitions the payment to `failed`, and re-raises as `Spree::Core::GatewayError` with a translated message.
- How does the system handle a payment source that doesn't belong to the order's customer? → `build_source` nils out the source if `source.user_id != order.user_id`; the Admin API's off-session charge (`find_source!`) scopes lookup to `@parent.user.credit_cards` only.
- What happens to other `checkout`-state payments when a new one is created? → `invalidate_old_payments` invalidates sibling checkout payments on the same order (store-credit payments are exempt in both directions).
- What happens when a payment source is destroyed while attached to incomplete-order payments? → `PaymentSourceConcern#cleanup_payments_on_incomplete_orders` invalidates checkout payments and voids non-checkout payments first.
- What happens on partial capture? → `capture!(amount)` captures only the given amount and calls `split_uncaptured_amount`, spinning off a new `pending` payment for the remainder with `capture_on_dispatch: true`.
- What happens if `amount` exceeds what's owed? → `amount_must_be_less_than_or_equal_to_max_amount` validates against `max_amount` (order balance, capped further by available store credit for store-credit payments).
- What happens when a payment method becomes unavailable for an order/store mid-checkout? → `payment_method_available_for_order` validation blocks payment creation via `available_for_order?`/`available_for_store?`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST model a `Spree::Payment` state machine (`checkout → processing → pending/completed/void/invalid`) with `authorize!`/`purchase!`/`capture!`/`void_transaction!`/`cancel!` operations delegating to the associated `Spree::PaymentMethod`.
- **FR-002**: System MUST support multiple payment method types via STI (`Spree::PaymentMethod` base, `Spree::Gateway` for gateway-backed methods, `Spree::PaymentMethod::StoreCredit`), each store-scoped (`belongs_to :store`) and orderable (`acts_as_list`).
- **FR-003**: System MUST support a polymorphic `source` on `Payment` (`Spree::CreditCard`, `Spree::StoreCredit`, or generic `Spree::PaymentSource` subtypes) validated as required unless `skip_source_requirement`/`source_required?` says otherwise.
- **FR-004**: System MUST record every gateway response as a `log_entries` entry and every state transition as a `state_changes` entry for auditability.
- **FR-005**: System MUST support session-based payment flows (`Spree::PaymentSession`, `Spree::PaymentSetupSession`) with their own state machines (`pending → processing → completed/failed/canceled/expired`) for gateways that require hosted/embedded/tokenized flows, decoupled from order completion.
- **FR-006**: System MUST support inbound provider webhooks via a per-payment-method `parse_webhook_event(raw_body, headers)` contract, raising `Spree::PaymentMethod::WebhookSignatureError` on invalid signatures.
- **FR-007**: System MUST publish lifecycle events (`payment.completed`, `payment.voided`, `payment.paid`, `order.paid`, `payment_session.*`, `payment_setup_session.*`) for external consumers/subscribers.
- **FR-008**: System MUST expose an off-session admin charge API (`POST /api/v3/admin/orders/:order_id/payments`) that can charge an existing saved source (`source_id`) scoped to the order's own customer.
- **FR-009**: System MUST prevent deletion of payments via the admin interface (`can_be_deleted?` hardcoded `false`); void/invalidate are the only reversal paths.
- **FR-010**: System MUST allow admins to reorder, activate/deactivate, and configure preferences (including password-type fields that are not clobbered by blank resubmission) for payment methods, in both the legacy Rails admin and `packages/dashboard`.
- **FR-011**: System MUST ship a non-production test gateway (`Spree::Gateway::Bogus`) that simulates authorize/purchase/capture/void/credit/webhook/session flows using hardcoded test card numbers, hidden from the admin payment-method picker (`show_in_admin? == false`).

### Key Entities

- **Spree::Payment**: A charge attempt against an order for a given `payment_method` and polymorphic `source`, with `amount`, `state`, `response_code` (aliased `transaction_id`), AVS/CVV response fields, capture events, refunds, and offsets (negative-amount refund payments).
- **Spree::PaymentMethod**: STI base for configurable payment providers (store-scoped, ordered, soft-deletable); defines the extension contract (`payment_source_class`, `create_payment_session`, `parse_webhook_event`, etc.) that gateway/store-credit subclasses implement.
- **Spree::Gateway**: `PaymentMethod` subclass delegating `authorize`/`purchase`/`capture`/`void`/`credit` to an ActiveMerchant-style `provider` object built from preferences.
- **Spree::Gateway::Bogus**: Test-only `Gateway` subclass simulating a real processor for specs/demos; not shown in the admin UI.
- **Spree::CreditCard**: A `Spree::PaymentSource` subtype storing tokenized card metadata (brand, last4, expiry, gateway profile IDs) — never the raw PAN (`number`/`verification_value` are `attr_reader`, not persisted columns).
- **Spree::PaymentSource**: Generic base for non-card sources (wallets, accounts) sharing capture/void/credit eligibility logic via `Spree::PaymentSourceConcern`.
- **Spree::PaymentSession**: STI, gateway-specific session tracking a hosted/embedded payment attempt from `pending` to `completed`/`failed`/etc., later linked 1:1 to the resulting `Spree::Payment` via `response_code`/`external_id`.
- **Spree::PaymentSetupSession**: STI, gateway-specific session for tokenizing a payment method for future use, independent of any order.
- **Spree::Payment::GatewayOptions**: Value object assembling the hash (`customer`, `billing_address`, `shipping`, `tax`, etc.) passed to gateway calls.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::Payment` (+ `Processing`, `Webhooks`, `CustomEvents` concerns, `GatewayOptions`), `Spree::PaymentMethod`, `Spree::Gateway` (+ `Bogus`), `Spree::CreditCard`, `Spree::PaymentSource` (+ `PaymentSourceConcern`), `Spree::PaymentSession`, `Spree::PaymentSetupSession` |
| `spree/api` (Store/Admin API v3) | Yes | `Spree::Api::V3::Admin::Orders::PaymentsController` (create/capture/void), `Spree::Api::V3::Admin::PaymentMethodsController`, `Spree::Api::V3::Store::Carts::PaymentsController`/`PaymentSessionsController`, `Spree::Api::V3::Store::Customer::PaymentSetupSessionsController`, `Spree::Api::V3::Webhooks::PaymentsController`; serializers `PaymentSerializer`, `Admin::PaymentSerializer`, `PaymentMethodSerializer`, `PaymentSessionSerializer`, `PaymentSetupSessionSerializer`, `PaymentSourceSerializer` (+ admin variants) |
| `packages/dashboard` (admin SPA) | Yes | `routes/.../settings/payment-methods.tsx`, `hooks/use-payment-methods.ts`, `schemas/payment-method.ts`, `components/spree/payment-method-editors/*`, `tables/payment-methods.tsx` |
| `packages/dashboard-ui` / `dashboard-core` | Yes | Slot registry entries (`paymentMethodFormSlot`, `paymentMethodGuideSlot`, `paymentMethodActionsSlot`) for provider-specific editor injection; `PreferencesForm` reuse |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated `Payment`, `PaymentMethod`, `PaymentMethodCreateParams`/`UpdateParams` types from Alba serializers |
| `docs/plans/` | No | This is stable, already-shipped surface — no active `docs/plans/6.0-*` entry governs `Spree::Payment` itself (the STI/gateway shape isn't targeted by the state→status rename plan since `Payment` already uses `state`; see Migration Notes) |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints** (existing, documented as-built): `POST /api/v3/admin/orders/:order_id/payments`, `PATCH /api/v3/admin/orders/:order_id/payments/:id/capture`, `PATCH /api/v3/admin/orders/:order_id/payments/:id/void`, full CRUD on `/api/v3/admin/payment_methods`, Store API cart payment/payment-session endpoints, customer payment-setup-session endpoints, provider webhook endpoint.
- **Serializer fields (read)**: `status` (aliases `state`), `payment_method_id`, `response_code`, `number`, `amount`/`display_amount` (money, nulled for price-gated guests), `source_type`, `source_id`, `source` (nested), `payment_method` (nested). Admin adds `metadata`, `captured_amount`, `order_id`, `avs_response`, `cvv_response_code`, `cvv_response_message`, `created_at`/`updated_at`, expandable `order`/`refunds`.
- **Auth**: Admin API (secret key + scopes, or JWT + CanCanCan) for order payment capture/void/create and payment method CRUD; Store API (publishable key or customer JWT + guest cart token) for cart payment/payment-session/payment-setup-session endpoints; webhook endpoint uses provider-specific signature verification (`parse_webhook_event`), not standard API auth.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can create, authorize/capture, and void a payment against an order using only the documented state-machine events, with every transition recorded in `state_changes`.
- **SC-002**: A gateway connectivity failure never leaves a payment in an ambiguous state — it always resolves to `failed` with a translated `Spree::Core::GatewayError`.
- **SC-003**: Partial captures never lose track of the uncaptured remainder — it is always represented as a new `pending` payment.
- **SC-004**: A payment session/setup session reaches a terminal status (`completed`/`failed`/`canceled`/`expired`) without ever completing the order itself.
- **SC-005**: The bogus/test gateway is never selectable in the admin payment-method picker (`show_in_admin? == false`), preventing accidental production use.

## Assumptions

- Real (non-bogus) gateway providers (Stripe, Adyen, PayPal, etc.) ship as separate extension gems implementing the `Spree::Gateway`/`Spree::PaymentMethod` contract; none are vendored in this monorepo — `Spree::Gateway::Bogus` is the only concrete implementation present.
- "Payment methods" and "gateways" are used interchangeably in places (`Spree::Gateway < Spree::PaymentMethod`); store credit is treated as a `Spree::PaymentMethod` subtype with no gateway/source.
- ActiveMerchant-style response objects (`Spree::PaymentResponse`) are assumed as the `provider` contract for `Gateway` subclasses (`authorize`/`purchase`/`capture`/`void`/`credit` must return `.success?`/`.authorization`/`.avs_result`/`.cvv_result`).
- The legacy Rails admin (`spree/admin`) payments UI is being phased out per constitution Principle I / `docs/plans/6.0-admin-spa.md`, but is still the only surface for order-level payment capture/void today — the dashboard SPA currently only manages `Spree::PaymentMethod` settings, not per-order payment actions.

## Migration Notes

Honest gaps found while reverse-engineering this feature:

- **Bogus gateway is test/demo-only.** `Spree::Gateway::Bogus#show_in_admin?` returns `false` and it hardcodes a fixed set of "valid" test card numbers with no real network call — confirmed test-only stub, not a reference implementation of a production processor.
- **No real gateway integration ships in this monorepo.** All Stripe/Adyen/PayPal-style integrations referenced in code comments (`Gateway.api_type`, `SpreeStripe::Gateway`, etc.) live in separate, unfound extension gems. This spec describes the extension point contract (`Spree::PaymentMethod`/`Spree::Gateway` overridable methods), not a concrete working gateway beyond Bogus.
- **No admin-SPA payment-capture UI found.** `packages/dashboard` only has payment method (provider) CRUD (`use-payment-methods.ts`, `settings/payment-methods.tsx`). Order-level payment actions (create/capture/void) exist only in the legacy Rails admin (`Spree::Admin::PaymentsController`) and the Admin API — no dashboard route/hook for `adminClient.orders.payments.*` was found. This is either an intentional 6.0-pending gap or an oversight; not addressed by any `docs/plans/6.0-*.md` entry found in `CLAUDE.md`'s active list.
- **`Payment#state` is not covered by `6.0-normalize-state-to-status.md`.** That plan targets `Payment`, `Shipment`, `InventoryUnit`, `ReturnAuthorization`, `GiftCard` state→status renames, but the current `Payment` model still uses `state_machine initial: :checkout` on the `state` column with an API-level `status` alias in the serializer only (`attribute :status { |payment| payment.state }`) — the underlying column rename appears not yet implemented for `Payment` specifically, despite being named in the active plan list.
- **`Spree::PaymentSetupSession#payment_source` association exists but its completion flow's card-creation step is entirely gateway-defined** (see `Bogus#complete_payment_setup_session` creating a `CreditCard` directly) — no shared/generic helper was found for gateway subclasses to reuse when producing a `PaymentSource` from setup-session completion; each gateway extension apparently duplicates this.
- **Webhook signature verification is unimplemented in core.** `Spree::Payment::Webhooks#send_payment_voided_webhook`/`#send_payment_completed_webhook` are explicit no-op stubs (`# Implement your logic here`) — outbound webhook firing is an extension point, not a built feature, despite `Payment` including the concern by default.
- **RSpec coverage exists** (`spree/core/spec/models/spree/payment_spec.rb`, `payment_method_spec.rb`, `payment_session_spec.rb`, `payment_setup_session_spec.rb`, `payment_source_spec.rb`, `order/payment_spec.rb`) but was not fully read line-by-line for this migration — acceptance scenarios above are inferred from model code, not verified against existing specs' exact assertions.
