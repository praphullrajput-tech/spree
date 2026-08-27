---

description: "Retroactive task list for existing Returns & Reimbursements feature (brownfield migration)"
---

# Tasks: Returns & Reimbursements

**Input**: Design documents from `/specs/007-returns-and-reimbursements/`

**Prerequisites**: plan.md, spec.md

**Tests**: All listed test tasks reference specs that already exist in the repository — this is a reverse-engineering pass, not new development. Every task below is marked `[x]` because the corresponding code and tests are already shipped.

**Organization**: Tasks are grouped by the actual components found in the codebase (authorization → receiving → reimbursement → API exposure → notifications → seeds), not by hypothetical user-story phasing, since all stories ship together as one existing feature.

## Path Conventions

- **Backend model/service**: `spree/core/app/models/spree/...`, `spree/core/app/services/spree/...`, migration in `spree/core/db/migrate/`, specs in `spree/core/spec/...`
- **Legacy admin**: `spree/admin/app/controllers/spree/admin/...`, views in `spree/admin/app/views/spree/admin/...`
- **API serializers**: `spree/api/app/serializers/spree/api/v3/...`
- **Email**: `spree/emails/app/{subscribers,mailers}/spree/...`
- No `packages/dashboard`, `packages/dashboard-ui/-core`, or `packages/sdk` rows apply — see spec.md Module Impact (no SPA/hand-written-client code exists for this domain).

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core` gem test app exists (`bundle exec rake test_app`) — prerequisite for all specs below
- [x] T002 [P] Baseline: `cd spree/core && bundle exec rspec` passes on main, covering this domain's existing specs

---

## Phase 2: Foundational — Return Authorization Reasons & Seeds

- [x] T003 [spree/core] `Spree::ReturnAuthorizationReason` model (`spree/core/app/models/spree/return_authorization_reason.rb`) — `Spree::NamedType`, `has_prefix_id :rar`, `has_many :return_authorizations, dependent: :restrict_with_error`
- [x] T004 [spree/core] `Spree::Seeds::ReturnsEnvironment` service (`spree/core/app/services/spree/seeds/returns_environment.rb`) seeds the default `RefundReason`, 9 stock `ReturnAuthorizationReason`s, and the 3 seedable `ReimbursementType`s (`StoreCredit`, `Exchange`, `OriginalPayment`) — covered by `spree/core/spec/services/spree/seeds/returns_environment_spec.rb`
- [x] T005 [spree/admin] `return_authorization_reasons` CRUD controller + views registered in `spree/admin` routes (`resources :return_authorization_reasons, except: :show`)

**Checkpoint**: Reason/seed infrastructure in place before any RMA can be created with a real reason.

---

## Phase 3: User Story 1 — Admin Authorizes a Return (Priority: P1)

**Goal**: Admin creates a `ReturnAuthorization` against shipped inventory units, which can later be canceled.

**Independent Test**: Order with shipped units → create RMA with reason + stock location → verify `authorized` state; order with no shipped units → verify validation failure.

### Tests for User Story 1

- [x] T006 [P] [US1] RSpec model spec `spree/core/spec/models/spree/return_authorization_spec.rb` — covers `must_have_shipped_units`, `cancel` transition + `can_cancel_return_items?`, `pre_tax_total`, `refundable_amount`, `generate_expedited_exchange_reimbursements`

### Implementation for User Story 1

- [x] T007 [US1] `Spree::ReturnAuthorization` model (`spree/core/app/models/spree/return_authorization.rb`) — `has_prefix_id :ra`, RA-prefixed `NumberGenerator`, `publishes_lifecycle_events`, `belongs_to :order/:stock_location/:reason`, `has_many :return_items` (+ `through:` to `inventory_units`/`customer_returns`/`reimbursements`/`refunds`), `state_machine` (`authorized` → `canceled`), `pre_expedited_exchange_hooks` class_attribute, `whitelisted_ransackable_attributes`
- [x] T008 [US1] `Spree::Admin::Orders::ReturnAuthorizationsController` (`spree/admin/app/controllers/spree/admin/orders/return_authorizations_controller.rb`) — builds placeholder `ReturnItem`s for unassociated inventory units, loads reimbursement types + active reasons, permits `return_authorization` params
- [x] T009 [P] [US1] Admin views: `spree/admin/app/views/spree/admin/orders/return_authorizations/_return_authorization.html.erb`, `spree/admin/app/views/spree/admin/orders/_return_authorizations.html.erb`, `return_authorizations` index/destroy views + shared `_returns_and_refunds_nav.html.erb`
- [x] T010 [P] [US1] Routes: `resources :return_authorizations, except: [:index, :destroy], controller: 'orders/return_authorizations'` (nested under order) + `resources :return_authorizations, only: [:index, :destroy]` (top-level)

**Checkpoint**: RMA creation/cancellation fully functional and independently testable.

---

## Phase 4: User Story 2 — Warehouse Records a Customer Return (Priority: P1)

**Goal**: Admin records physical receipt via `CustomerReturn`, driving `ReturnItem` reception + eligibility acceptance and order-level `returned` status.

**Independent Test**: Build `CustomerReturn` from RMA-linked return items → verify `received` transition, restock behavior, and order `returned` once complete.

### Tests for User Story 2

- [x] T011 [P] [US2] RSpec model spec `spree/core/spec/models/spree/customer_return_spec.rb` — covers `process_return!`, `must_have_return_authorization`, `return_items_belong_to_same_order`, `completely_decided?`/`fully_reimbursed?`, `can_create_reimbursement?`/`no_pending_reimbursements?`
- [x] T012 [P] [US2] RSpec model spec `spree/core/spec/models/spree/return_item_spec.rb` — covers both state machines, `validate_no_other_completed_return_items`, `sufficient_quantity_for_return`, `extract_inventory_unit`/`split_inventory!`, `should_restock?`, exchange helpers
- [x] T013 [P] [US2] RSpec spec `spree/core/spec/models/spree/return_item/eligibility_validator/no_reimbursements_spec.rb` — covers the `NoReimbursements` validator specifically; the other 4 validators (`OrderCompleted`, `TimeSincePurchase`, `RMARequired`, `InventoryShipped`) are exercised indirectly through `Default`'s `eligible_for_return?`/`requires_manual_intervention?` composition in the return-item spec

### Implementation for User Story 2

- [x] T014 [P] [US2] `Spree::CustomerReturn` model (`spree/core/app/models/spree/customer_return.rb`) — `has_prefix_id :cr`, CR-prefixed `NumberGenerator`, `Spree::Metafields`/`Spree::Metadata`, `after_create :process_return!`, derived `order` (no direct FK), `pre_tax_total`, `can_create_reimbursement?`
- [x] T015 [US2] `Spree::ReturnItem` model (`spree/core/app/models/spree/return_item.rb`) — dual state machines (`reception_status`, `acceptance_status`), `return_eligibility_validator`/`exchange_variant_engine`/`refund_amount_calculator` class_attributes, exchange-inventory-unit support, tax fields, `COMPLETED_RECEPTION_STATUSES` guard
- [x] T016 [P] [US2] Eligibility validator chain: `base_validator.rb`, `default.rb` (composes the 5 below), `order_completed.rb`, `time_since_purchase.rb` (uses `Spree::Config[:return_eligibility_number_of_days]`), `rma_required.rb`, `inventory_shipped.rb`, `no_reimbursements.rb` — all under `spree/core/app/models/spree/return_item/eligibility_validator/`
- [x] T017 [US2] `Spree::Admin::Orders::CustomerReturnsController` (`spree/admin/app/controllers/spree/admin/orders/customer_returns_controller.rb`) — builds return items from nested `returned` checkbox params, partitions items by acceptance status for `edit`
- [x] T018 [P] [US2] Admin views: `spree/admin/app/views/spree/admin/orders/customer_returns/{_customer_return,_reimbursements_table,_return_item_decision,_return_item_selection}.html.erb`, `spree/admin/app/views/spree/admin/orders/_customer_returns.html.erb`, `customer_returns` index/edit views
- [x] T019 [P] [US2] Routes: `resources :customer_returns, except: [:index, :destroy], controller: 'orders/customer_returns'` (nested) + `resources :customer_returns, only: :index` (top-level)

**Checkpoint**: Receiving flow fully functional; inventory restocking and order status transitions verified independently of reimbursement.

---

## Phase 5: User Story 3 — Admin Reimburses the Customer (Priority: P2)

**Goal**: Build and perform a `Reimbursement` against a fully-decided `CustomerReturn`, fanning out to `ReimbursementType` STI for `Refund`/`Credit`/`Exchange` creation with tax recomputed.

**Independent Test**: `Reimbursement.build_from_customer_return` → `perform!` → verify `reimbursed`/`errored` transition and generated payout records.

### Tests for User Story 3

- [x] T020 [P] [US3] RSpec model spec `spree/core/spec/models/spree/reimbursement_spec.rb` — covers `perform!`/`simulate`, `calculated_total`/`paid_amount`/`unpaid_amount`, `unpaid_amount_within_tolerance?` rounding leniency, success/failure hooks, `IncompleteReimbursementError`
- [x] T021 [P] [US3] RSpec spec `spree/core/spec/models/spree/reimbursement_performer_spec.rb` — covers the `reimbursement_performer` collaborator (`perform`/`simulate` contract)
- [x] T022 [P] [US3] RSpec spec `spree/core/spec/models/spree/reimbursement_tax_calculator_spec.rb` — covers `ReimbursementTaxCalculator.call` proportional tax recomputation
- [x] T023 [P] [US3] RSpec spec `spree/core/spec/models/spree/returns_calculator_spec.rb` — covers `refund_amount_calculator` (`Calculator::Returns::DefaultRefundAmount`) used by `set_default_pre_tax_amount`/tax calculator
- [x] T024 [P] [US3] RSpec specs `spree/core/spec/models/spree/reimbursement/reimbursement_type_engine_spec.rb` + `reimbursement_type_validator_spec.rb` — cover STI dispatch and the `validate_acceptance_status_for_reimbursement` guard
- [x] T025 [P] [US3] RSpec specs under `spree/core/spec/models/spree/reimbursement_type/` — per-subtype behavior for `Credit`, `Exchange`, `OriginalPayment`, `StoreCredit`

### Implementation for User Story 3

- [x] T026 [US3] `Spree::Reimbursement` model (`spree/core/app/models/spree/reimbursement.rb`) — REIMB-prefixed number, `reimbursement_status` state machine (`pending`→`reimbursed`/`errored`), pluggable `reimbursement_tax_calculator`/`reimbursement_simulator_tax_calculator`/`reimbursement_models`/`reimbursement_performer`, success/failure hooks, `build_from_customer_return`
- [x] T027 [US3] `Spree::ReimbursementType` STI base (`spree/core/app/models/spree/reimbursement_type.rb`) — `Spree::NamedType`, `KINDS` registry, abstract `self.reimburse`
- [x] T028 [P] [US3] STI subtypes: `reimbursement_type/credit.rb`, `reimbursement_type/original_payment.rb`, `reimbursement_type/store_credit.rb` (all `extend ReimbursementHelpers`), `reimbursement_type/exchange.rb` (delegates to `Spree::Exchange`)
- [x] T029 [US3] `Spree::ReimbursementType::ReimbursementHelpers` module (`spree/core/app/models/spree/reimbursement_type/reimbursement_helpers.rb`) — shared `create_refunds`/`create_credits`/`create_refund`/`create_credit` used by the credit/original-payment/store-credit subtypes
- [x] T030 [US3] `Spree::ReimbursementTaxCalculator` (`spree/core/app/models/spree/reimbursement_tax_calculator.rb`) — proportional tax recomputation against `Spree::ReturnItem.refund_amount_calculator`
- [x] T031 [US3] Migration `spree/core/db/migrate/20250304115943_add_performed_by_to_spree_reimbursements.rb` — adds `performed_by` FK-less reference used by `perform!(performer)`
- [x] T032 [US3] `Spree::Admin::ReimbursementsController` (`spree/admin/app/controllers/spree/admin/reimbursements_controller.rb`) — `build_from_customer_return_id` param path, `perform` action, `load_simulated_refunds` for `edit`, `Spree::Core::GatewayError` rescue
- [x] T033 [P] [US3] Admin views under `spree/admin/app/views/spree/admin/reimbursements/` + `reimbursement_types/` CRUD views
- [x] T034 [P] [US3] Routes: `resources :reimbursements, except: [:destroy, :index]` (nested under order) + `resources :reimbursement_types` (top-level CRUD)

**Checkpoint**: Full authorize → receive → reimburse lifecycle functional end-to-end through the legacy admin UI.

---

## Phase 6: API Exposure (Read-Only)

**Goal**: Expose the chain as expandable nested Admin API v3 attributes — no write endpoints exist.

- [x] T035 [P] [spree/api] `V3::ReturnAuthorizationSerializer` (`spree/api/app/serializers/spree/api/v3/return_authorization_serializer.rb`) — `number`, `status`, `order_id`, `stock_location_id`, `return_authorization_reason_id`
- [x] T036 [P] [spree/api] `V3::CustomerReturnSerializer` (`spree/api/app/serializers/spree/api/v3/customer_return_serializer.rb`) — `number`, `created_at`, `updated_at`, `stock_location_id`
- [x] T037 [P] [spree/api] `V3::ReturnItemSerializer` (`spree/api/app/serializers/spree/api/v3/return_item_serializer.rb`) — reception/acceptance status, tax fields, all prefixed FK attributes
- [x] T038 [P] [spree/api] `V3::ReimbursementSerializer` + `V3::Admin::ReimbursementSerializer` (`spree/api/app/serializers/spree/api/v3/{reimbursement_serializer.rb,admin/reimbursement_serializer.rb}`) — admin variant adds timestamps + expandable `order`
- [x] T039 [P] [spree/api] `V3::RefundSerializer` (`spree/api/app/serializers/spree/api/v3/refund_serializer.rb`)
- [x] T040 [spree/api] `Admin::OrderSerializer` wires `return_authorizations`/`reimbursements` as `expand?`-gated nested attributes (`spree/api/app/serializers/spree/api/v3/admin/order_serializer.rb`)

**Note**: No dedicated `spree/api/v3/admin/return_authorizations_controller.rb` (or customer_returns/reimbursements equivalent) exists — this is a documented gap, not a missing task (see spec.md Migration Notes).

---

## Phase 7: Notifications (spree/emails — deprecated in 6.0)

- [x] T041 [spree/emails] `Spree::ReimbursementEmailSubscriber` (`spree/emails/app/subscribers/spree/reimbursement_email_subscriber.rb`) — subscribes to `reimbursement.reimbursed`, gates on `store.prefers_send_consumer_transactional_emails?`
- [x] T042 [spree/emails] `Spree::ReimbursementMailer#reimbursement_email` (`spree/emails/app/mailers/spree/reimbursement_mailer.rb`) — resend-aware subject line, store-scoped `from`/`reply_to`/`storefront_url`

---

## Phase 8: Polish & Cross-Cutting (documentation only — no code changes)

- [x] T043 Cross-reference `docs/plans/6.0-returns-exchanges-claims.md` in spec.md Module Impact + Migration Notes, per Constitution Principle VI (this domain's superseding architectural plan)
- [x] T044 Full backend suite already green on main: `cd spree/core && bundle exec rspec` covers every model/service task above
- [x] T045 Record the Admin-API-write-surface gap and the `spree/emails` deprecation dependency in spec.md Migration Notes for future planning

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Reasons/seeds must exist before RMAs reference a real `ReturnAuthorizationReason` — blocks Phase 3.
- **US1 (Phase 3)**: Depends on Phase 2. Produces the RMA + `ReturnItem`s that US2 receives against.
- **US2 (Phase 4)**: Depends on Phase 3 (needs authorized `ReturnItem`s to receive).
- **US3 (Phase 5)**: Depends on Phase 4 (needs a `CustomerReturn` with completely-decided items to build a `Reimbursement` from).
- **API Exposure (Phase 6)**: Depends on Phases 3–5 (serializes their models); independently deployable/testable as a read surface.
- **Notifications (Phase 7)**: Depends on Phase 5 (fires on `reimbursement.reimbursed`).
- **Polish (Phase 8)**: Depends on all prior phases.

### Parallel Opportunities

- All `[P]`-marked spec tasks within a phase were (and can be) run in parallel — they touch independent spec files.
- The 5 eligibility validators (T016) are independent files and were implemented/tested in parallel.
- The 4 `ReimbursementType` STI subtypes (T028) are independent files sharing only the `ReimbursementHelpers` mixin (T029).
- Serializer tasks in Phase 6 (T035–T039) are independent files.

---

## Notes

- This tasks.md is retroactive: every task reflects code already present on `main` as of this migration pass. No new tests were written and no new code was added — see `spec.md` → Migration Notes for the honestly-scoped gaps (no Admin API write surface, no dashboard SPA presence, dependency on deprecated `spree/emails`).
- Future work extending this domain should consult `docs/plans/6.0-returns-exchanges-claims.md` first — it plans to replace every model listed here.
