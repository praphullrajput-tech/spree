# Feature Specification: Returns & Reimbursements

**Feature Branch**: `007-returns-and-reimbursements`

**Created**: 2026-08-24

**Status**: migrated

**Input**: Reverse-engineered from existing code (brownfield migration) — no original feature request survives; behavior below is inferred from `spree/core`, `spree/admin`, `spree/api`, and `spree/emails` source.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin authorizes a return (Priority: P1)

A store admin, working an order that has shipped inventory, creates a `Spree::ReturnAuthorization` (RMA) specifying which shipped units may come back, a reason, and the stock location they'll be received at. The RMA can later be canceled if none of its return items have progressed.

**Why this priority**: Nothing else in the flow (receiving, reimbursing) can happen without an authorization — it's the entry point that gates the rest of the return lifecycle.

**Independent Test**: Create an order with a shipped inventory unit, create a `Spree::ReturnAuthorization` with a reason + stock location, and verify it persists in `authorized` state and rejects orders with no shipped units.

**Acceptance Scenarios**:

1. **Given** an order with shipped inventory units, **When** an admin creates a `ReturnAuthorization` with a reason and stock location, **Then** the RMA is created in `authorized` state with associated `ReturnItem`s.
2. **Given** an order with no shipped inventory units, **When** an admin attempts to create a `ReturnAuthorization`, **Then** creation fails validation (`must_have_shipped_units`).
3. **Given** an authorized RMA whose return items can all be canceled, **When** an admin cancels it, **Then** the RMA transitions to `canceled` and its return items are canceled too.

---

### User Story 2 - Warehouse records a customer return (Priority: P1)

Once physical items arrive back at the warehouse, an admin creates a `Spree::CustomerReturn` referencing the `ReturnItem`s being received. Each return item runs through eligibility validation and is marked received, restocking inventory where applicable. The parent order transitions to `returned` once every inventory unit on it has come back.

**Why this priority**: This is the "money-adjacent" event that actually receives goods and drives inventory + order-state changes — the return has no real-world effect until this happens.

**Independent Test**: Build a `CustomerReturn` from `ReturnItem`s tied to an existing `ReturnAuthorization` and verify `after_create` receives every item, restocks inventory (when `resellable?` + `should_track_inventory?` + `Spree::Config[:restock_inventory]`), and flips the order to `returned` once all units are back.

**Acceptance Scenarios**:

1. **Given** return items that all belong to RMAs, **When** a `CustomerReturn` is created, **Then** each return item transitions `awaiting → received`, attempts eligibility acceptance, and (if resellable) creates a `Spree::StockMovement`.
2. **Given** a return item with no `return_authorization`, **When** a `CustomerReturn` is created referencing it, **Then** validation fails (`must_have_return_authorization`).
3. **Given** all inventory units on an order have been returned, **When** the last `CustomerReturn` is processed, **Then** the order transitions to `returned`.

---

### User Story 3 - Admin reimburses the customer (Priority: P2)

Once a `CustomerReturn`'s items are "completely decided" (accepted/rejected, not pending), an admin builds a `Spree::Reimbursement` from it, selecting a reimbursement type per return item (original payment, store credit, or exchange). Performing the reimbursement calculates tax, computes the total, and delegates to the configured `ReimbursementType` classes to create `Refund`/`Credit`/`Exchange` records; the reimbursement then settles into `reimbursed` or `errored`.

**Why this priority**: This is the step that actually returns money/value to the customer — it's the payoff of the whole flow, but depends on Stories 1 and 2 having already run.

**Independent Test**: Build a `Reimbursement` from a fully-decided `CustomerReturn`, call `perform!`, and verify it recalculates `total` via `ReimbursementTaxCalculator`, creates `Refund`/`Credit`/`Exchange` records via the configured `reimbursement_performer`, and transitions to `reimbursed` (within a one-cent-per-type rounding tolerance) or `errored` + raises `IncompleteReimbursementError` otherwise.

**Acceptance Scenarios**:

1. **Given** a `CustomerReturn` whose return items are all accepted, **When** an admin builds and performs a `Reimbursement` against the original payment, **Then** `Spree::Refund` records are created against completed payments up to `credit_allowed`, any remainder becomes a `Spree::Reimbursement::Credit` (store credit), and the reimbursement becomes `reimbursed`.
2. **Given** return items requesting an exchange variant, **When** the reimbursement is performed, **Then** a `Spree::Exchange` is created/performed instead of a refund for those items.
3. **Given** the reimbursement performer cannot fully pay out the calculated total (outside tolerance), **When** `perform!` runs, **Then** the reimbursement transitions to `errored` and `IncompleteReimbursementError` is raised.
4. **Given** a reimbursement transitions to `reimbursed` and the store allows consumer transactional emails, **When** the `reimbursement.reimbursed` event fires, **Then** `Spree::ReimbursementMailer#reimbursement_email` is enqueued via `deliver_later`.

---

### Edge Cases

- What happens when a return item's inventory unit already has another completed (received/given) return item? → Creation fails validation (`validate_no_other_completed_return_items`).
- What happens when a return item requests more quantity than was purchased? → `sufficient_quantity_for_return` rejects it.
- What happens when the order's `return_eligibility_number_of_days` window has elapsed? → `TimeSincePurchase` validator marks the item ineligible (auto-reject or manual intervention, depending on which other validators also fail).
- What happens when no RMA exists for a return item? → `RMARequired` validator fails it; `NoReimbursements` also blocks items whose inventory unit already has a reimbursed return item.
- How does the system handle multiple reimbursement types splitting one reimbursement? → A per-type one-cent rounding tolerance (`unpaid_amount_within_tolerance?`) allows the reimbursement to still settle as `reimbursed`.
- What happens when `Spree::Config[:expedited_exchanges]` is enabled? → `ReturnAuthorization#generate_expedited_exchange_reimbursements` auto-builds and performs a `Reimbursement` for any return items with an accepted exchange, immediately after the RMA is saved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow creating a `Spree::ReturnAuthorization` only against an order that has at least one shipped inventory unit.
- **FR-002**: System MUST validate return-item eligibility through a pluggable chain (`Spree::ReturnItem::EligibilityValidator::Default`: `OrderCompleted`, `TimeSincePurchase`, `RMARequired`, `InventoryShipped`, `NoReimbursements`), each contributing to `eligible_for_return?` / `requires_manual_intervention?`.
- **FR-003**: System MUST prevent more than one active (non-cancelled) return item per inventory unit once one has reached a completed reception status (`received`/`given_to_customer`).
- **FR-004**: System MUST create a `Spree::CustomerReturn` only from return items that all belong to the same order and all have an associated `ReturnAuthorization`.
- **FR-005**: System MUST mark the parent order `returned` once every inventory unit on it has been returned.
- **FR-006**: System MUST restock inventory on receipt only when the return item is `resellable`, its variant tracks inventory, and `Spree::Config[:restock_inventory]` is enabled.
- **FR-007**: System MUST support at least three reimbursement mechanisms via STI (`Spree::ReimbursementType::OriginalPayment`, `::StoreCredit`, `::Credit`, `::Exchange`), each pluggable via `class_attribute` on `Spree::Reimbursement`/`Spree::ReturnItem`.
- **FR-008**: System MUST recompute tax on return items at reimbursement time via a pluggable `reimbursement_tax_calculator` (default `Spree::ReimbursementTaxCalculator`).
- **FR-009**: System MUST NOT allow a reimbursement to associate with a return item unless that item is `accepted`.
- **FR-010**: System MUST send a transactional "reimbursement" email when a reimbursement completes, but only if the store's `prefers_send_consumer_transactional_emails?` is true.
- **FR-011**: System MUST expose `ReturnAuthorization`, `CustomerReturn`, `ReturnItem`, `Reimbursement`, and `Refund` as read-only, expandable nested resources on the Admin API v3 order/reimbursement serializers — there is currently **no dedicated Admin API v3 CRUD controller** for creating/updating returns or reimbursements (see Migration Notes).
- **FR-012**: The only mutation path for this feature today is the legacy Rails `spree/admin` engine (`Spree::Admin::Orders::ReturnAuthorizationsController`, `::CustomerReturnsController`, `Spree::Admin::ReimbursementsController`), which the constitution and `CLAUDE.md` flag as being phased out with no new feature work expected there.

### Key Entities

- **ReturnAuthorization (RMA)**: Permission to return shipped units of an order; has a reason, stock location, state machine (`authorized` → `canceled`), and `has_many :return_items`.
- **ReturnAuthorizationReason**: Named, activatable lookup (`Spree::NamedType`) referenced by RMAs; `restrict_with_error` on destroy while referenced.
- **CustomerReturn**: Physical receipt event at a stock location; derives its `order` transitively through `return_items.first.inventory_unit.order`; drives inventory-unit `return!` on create.
- **ReturnItem**: Per-inventory-unit record spanning two independent state machines — `reception_status` (`awaiting`/`received`/`cancelled`/`given_to_customer`) and `acceptance_status` (`pending`/`accepted`/`rejected`/`manual_intervention_required`); also carries exchange-variant + tax fields.
- **Reimbursement**: Money-back execution against an order/customer_return; state machine `pending` → `reimbursed`/`errored`; fans out to `Refund`/`Credit`/`Exchange` via `ReimbursementType` STI.
- **ReimbursementType (STI)**: `Credit`, `Exchange`, `OriginalPayment`, `StoreCredit` — each implements `self.reimburse(reimbursement, return_items, simulate)`.
- **ReimbursementTaxCalculator**: Stateless service recomputing `included_tax_total`/`additional_tax_total` proportionally against the refund calculator's output.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `ReturnAuthorization`, `ReturnAuthorizationReason`, `CustomerReturn`, `ReturnItem` (+ 5 eligibility validators), `Reimbursement`, `ReimbursementType` (+ 4 STI subtypes + helpers module), `ReimbursementTaxCalculator`, `Seeds::ReturnsEnvironment` |
| `spree/api` (Store/Admin API v3) | Yes (read-only) | Serializers only: `V3::ReturnAuthorizationSerializer`, `V3::CustomerReturnSerializer`, `V3::ReturnItemSerializer`, `V3::ReimbursementSerializer` (+ `V3::Admin::ReimbursementSerializer`), `V3::RefundSerializer`, all reached only as `expand?`-gated nested attributes on `Admin::OrderSerializer`. No dedicated controller/route exists. |
| `spree/admin` (legacy Rails admin) | Yes | `Orders::ReturnAuthorizationsController`, `Orders::CustomerReturnsController`, `ReimbursementsController`, plus `reimbursement_types` / `return_authorization_reasons` CRUD and full ERB view set — this is the **only** surface with write access today. Per `CLAUDE.md`, no new feature work should land here. |
| `packages/dashboard` (admin SPA) | No | No routes, hooks, or schemas reference returns/reimbursements today. |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Yes (generated only) | `ReturnAuthorization`, `ReturnItem`, `Refund`, `Reimbursement` generated types exist (from the serializers above) but are read-only artifacts of the type-generation pipeline; no hand-written client resource methods. |
| `spree/emails` (deprecated in 6.0) | Yes | `Spree::ReimbursementEmailSubscriber` (subscribes to `reimbursement.reimbursed`) + `Spree::ReimbursementMailer#reimbursement_email`. **Flag**: per `CLAUDE.md`, `spree/emails` is deprecated in 6.0 in favor of the Next.js storefront handling consumer emails via webhooks — this feature currently depends on the deprecated path for its one customer-facing notification. |
| `docs/plans/` | Yes (pre-existing) | `docs/plans/6.0-returns-exchanges-claims.md` already targets replacing this entire 6-model chain (`ReturnAuthorization`/`ReturnItem`/`CustomerReturn`/`Reimbursement`/`ReimbursementType`/`Refund`) with three first-class `Return`/`Exchange`/`Claim` models. This migrated spec documents the **current** (pre-6.0) implementation; the 6.0 plan is the forward-looking replacement and binds future work in this area per Constitution Principle VI. |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints**: None — no dedicated `spree/api/v3` controller exists for returns/reimbursements. All exposure is via `expand=return_authorizations` / `expand=reimbursements` query params on the Admin Order/Reimbursement endpoints.
- **Serializer fields (read)**: `ReturnAuthorizationSerializer` (`number`, `status`, `order_id`, `stock_location_id`, `return_authorization_reason_id`); `CustomerReturnSerializer` (`number`, `created_at`, `updated_at`, `stock_location_id`); `ReturnItemSerializer` (`reception_status`, `acceptance_status`, `pre_tax_amount`, `included_tax_total`, `additional_tax_total`, `inventory_unit_id`, `return_authorization_id`, `customer_return_id`, `reimbursement_id`, `exchange_variant_id`, timestamps); `ReimbursementSerializer`/`Admin::ReimbursementSerializer` (`number`, `reimbursement_status`, `total`, `order_id`, `customer_return_id`, `created_at`, `updated_at`); `RefundSerializer` (`transaction_id`, `amount`, `payment_id`, `refund_reason_id`, `reimbursement_id`).
- **Auth**: Admin JWT + CanCanCan (these are nested attributes reached through the Admin order/reimbursement endpoints, which are Admin API v3 surfaces); no Store API exposure, no secret-key scopes defined for this domain since there are no dedicated endpoints.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can authorize, receive, and reimburse a return for a completed order entirely through the existing `spree/admin` UI without hitting an unhandled validation error for the documented happy path.
- **SC-002**: Reimbursement totals reconcile with the sum of created `Refund`/`Credit`/`Exchange` records within the documented one-cent-per-type tolerance.
- **SC-003**: 100% of `reimbursement.reimbursed` events for stores with `prefers_send_consumer_transactional_emails?` enabled result in a queued `ReimbursementMailer` email.
- **SC-004**: No inventory unit is ever double-counted as returned/restocked (enforced by `validate_no_other_completed_return_items` + `should_restock?` gating).

## Assumptions

- This spec documents **existing, shipped behavior** reverse-engineered from source, not a new feature request — there is no original PRD/issue to cite.
- The legacy `spree/admin` engine remains the return/reimbursement UI of record until `docs/plans/6.0-returns-exchanges-claims.md` (or a dashboard-SPA equivalent) ships; per the constitution, no new admin-SPA work is scoped here.
- `Spree::Exchange` (referenced by `ReimbursementType::Exchange`) is treated as an existing collaborator, out of scope for this spec's own model list, since it lives outside the read files reviewed.
- Store credit/refund creation assumes `Spree.admin_user_class`/`Spree.user_class` and `Spree::StoreCredit`/`Spree::Refund` are available and correctly configured per store.

## Migration Notes

- **Gap — no Admin API v3 write surface**: Returns/reimbursements can only be mutated through the legacy Rails admin (`spree/admin`), which `CLAUDE.md` explicitly says not to add new features to. There is no `spree/api/v3/admin/return_authorizations_controller.rb` (or customer_returns/reimbursements equivalent) at all — only read-only, expand-gated serializer attributes on the order/reimbursement endpoints. Any dashboard-SPA work here would first require building that Admin API surface (Constitution Principle II).
- **Gap — `spree/emails` dependency**: The only customer-facing outcome of a successful reimbursement (the confirmation email) is implemented in the deprecated `spree/emails` gem. `CLAUDE.md` states the Next.js storefront is expected to handle consumer emails via webhooks in 6.0; no such webhook/event-driven replacement exists yet for `reimbursement.reimbursed`.
- **Gap — no dashboard SPA presence**: Zero references to returns/reimbursements exist in `packages/dashboard`, `packages/dashboard-ui`, or `packages/dashboard-core`. The React admin has no UI for this domain today.
- **Superseding plan**: `docs/plans/6.0-returns-exchanges-claims.md` (Draft, target 6.0) intends to delete `CustomerReturn`, `Reimbursement`, `ReimbursementType` (and its 4 subtypes), and `ReturnAuthorization` outright, replacing them with `Return`, `Exchange`, and `Claim` as three first-class Order-owned models with their own simplified state machines. Anyone building new returns functionality should read that plan's "Constraints on Current Work" before extending the current models, per Constitution Principle VI.
- **`Spree::Exchange` not reviewed**: Referenced throughout (`ReimbursementType::Exchange`, `ReturnItem#exchange_shipments`) but its source was out of scope for the file list given for this migration; flagged for completeness, not a defect.
