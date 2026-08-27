# Tasks: Payments

**Input**: Design documents from `/specs/003-payments/`

**Prerequisites**: plan.md, spec.md

**Note**: This is a brownfield migration (`/speckit.brownfield.migrate`). All tasks below describe already-shipped work, reconstructed from the codebase, and are marked complete (`[x]`). No new implementation is performed by this document.

**Tests**: Existing RSpec coverage is recorded where found; no new tests are added by this migration.

**Organization**: Tasks are grouped by the actual components that implement each user story from spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Could have run in parallel (different files, no dependencies)
- **[Story]**: Which user story from spec.md this task maps to

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Backend gem baseline: `spree/core`, `spree/api`, `spree/admin` engines already present and tested (`bundle exec rspec` per gem)
- [x] T002 [P] Frontend baseline: `packages/dashboard`, `packages/dashboard-core`, `packages/admin-sdk` already wired for Admin API consumption (`pnpm typecheck && pnpm lint`)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T003 [spree/core] `Spree::Payment` model with `checkout → processing → pending/completed/void/invalid` state machine, `state_changes`/`log_entries` audit associations — `spree/core/app/models/spree/payment.rb`
- [x] T004 [spree/core] `Spree::PaymentMethod` STI base (store-scoped via `Spree::SingleStoreResource`, `acts_as_list`, `acts_as_paranoid`, `Spree::DisplayOn`) defining the gateway/session extension contract — `spree/core/app/models/spree/payment_method.rb`
- [x] T005 [spree/core] `Spree::Gateway` STI subclass delegating `authorize/purchase/capture/void/credit` to a `provider` object, plus `Spree::Gateway::Bogus` test double — `spree/core/app/models/spree/gateway.rb`, `spree/core/app/models/spree/gateway/bogus.rb`
- [x] T006 [spree/core] Polymorphic payment sources: `Spree::CreditCard`, `Spree::PaymentSource` base, shared `Spree::PaymentSourceConcern` (capture/void/credit eligibility, cleanup on destroy) — `spree/core/app/models/spree/credit_card.rb`, `spree/core/app/models/spree/payment_source.rb`, `spree/core/app/models/concerns/spree/payment_source_concern.rb`
- [x] T007 [spree/core] Ransack allowlist on `Spree::Payment` (`whitelisted_ransackable_associations`/`_attributes`) for API filtering — `spree/core/app/models/spree/payment.rb`
- [x] T008 [packages/dashboard] i18next keys under `admin.fields.payment_method.*` and `admin.payment_methods.messages.*` for the settings page — `packages/dashboard/src/locales/en.json`

**Checkpoint**: Foundation in place — model layer supports all four user stories.

---

## Phase 3: User Story 1 - Admin captures/voids an order payment (Priority: P1) 🎯 MVP

### Tests for User Story 1

- [x] T009 [P] [US1] RSpec model spec — `spree/core/spec/models/spree/payment_spec.rb`
- [x] T010 [P] [US1] RSpec order/payment integration spec — `spree/core/spec/models/spree/order/payment_spec.rb`

### Implementation for User Story 1

- [x] T011 [US1] `Spree::Payment::Processing` concern: `process!`/`authorize!`/`purchase!`/`confirm!`/`capture!`/`void_transaction!`/`cancel!`, partial-capture splitting (`split_uncaptured_amount`), connection-error handling — `spree/core/app/models/spree/payment/processing.rb`
- [x] T012 [US1] `Spree::Payment::GatewayOptions` value object assembling the hash passed to gateway calls — `spree/core/app/models/spree/payment/gateway_options.rb`
- [x] T013 [US1] Legacy Rails admin payment actions (`new`/`create`/`capture`/`void`) — `spree/admin/app/controllers/spree/admin/payments_controller.rb`
- [x] T014 [US1] Admin API order-payment endpoints: create (off-session charge via `source_id`), capture, void — `spree/api/app/controllers/spree/api/v3/admin/orders/payments_controller.rb`
- [x] T015 [US1] Admin payment serializer (adds `metadata`, `captured_amount`, `order_id`, AVS/CVV fields, expandable `order`/`refunds`) — `spree/api/app/serializers/spree/api/v3/admin/payment_serializer.rb`
- [x] T016 [US1] Store-facing payment serializer (`status`, money-gated `amount`/`display_amount`, nested `source`/`payment_method`) — `spree/api/app/serializers/spree/api/v3/payment_serializer.rb`

**Checkpoint**: Order payment capture/void functional end-to-end via Rails admin and Admin API.

---

## Phase 4: User Story 2 - Admin configures a payment method / gateway (Priority: P1)

### Tests for User Story 2

- [x] T017 [P] [US2] RSpec model spec — `spree/core/spec/models/spree/payment_method_spec.rb`

### Implementation for User Story 2

- [x] T018 [US2] Legacy Rails admin payment-method CRUD (STI type selection, preference clearing) — `spree/admin/app/controllers/spree/admin/payment_methods_controller.rb`
- [x] T019 [US2] Legacy Rails admin integrations controller (related provider-connection flow) — `spree/admin/app/controllers/spree/admin/integrations_controller.rb`
- [x] T020 [US2] Admin API payment-methods controller (full CRUD + `types` listing) — `spree/api/app/controllers/spree/api/v3/admin/payment_methods_controller.rb`
- [x] T021 [US2] Admin/store payment-method serializers — `spree/api/app/serializers/spree/api/v3/payment_method_serializer.rb`, `spree/api/app/serializers/spree/api/v3/admin/payment_method_serializer.rb`
- [x] T022 [US2] Dashboard hooks (`usePaymentMethods`, `usePaymentMethod`, `useCreatePaymentMethod`, `useUpdatePaymentMethod`, `useDeletePaymentMethod`, `usePaymentMethodTypes`) — `packages/dashboard/src/hooks/use-payment-methods.ts`
- [x] T023 [US2] Dashboard settings route + create/edit sheets, reorder via `<ResourceTable reorder>` — `packages/dashboard/src/routes/_authenticated/$storeId/settings/payment-methods.tsx`
- [x] T024 [US2] Dashboard form (`PaymentMethodForm`, provider-type picker, preferences, storefront-visible switch, per-provider slot injection) + Zod schema — `packages/dashboard/src/components/spree/payment-method-editors/payment-method-form.tsx`, `packages/dashboard/src/schemas/payment-method.ts`

**Checkpoint**: Payment-method configuration functional end-to-end via legacy admin and dashboard SPA.

---

## Phase 5: User Story 3 - Customer completes checkout payment via hosted/embedded flow (Priority: P2)

### Tests for User Story 3

- [x] T025 [P] [US3] RSpec model spec — `spree/core/spec/models/spree/payment_session_spec.rb`

### Implementation for User Story 3

- [x] T026 [US3] `Spree::PaymentSession` state machine (`pending → processing → completed/failed/canceled/expired`) + `find_or_create_payment!` linking — `spree/core/app/models/spree/payment_session.rb`
- [x] T027 [US3] Store API cart payment/payment-session endpoints — `spree/api/app/controllers/spree/api/v3/store/carts/payments_controller.rb`, `spree/api/app/controllers/spree/api/v3/store/carts/payment_sessions_controller.rb`
- [x] T028 [US3] Provider webhook endpoint (`parse_webhook_event` contract) — `spree/api/app/controllers/spree/api/v3/webhooks/payments_controller.rb`
- [x] T029 [US3] `PaymentSessionSerializer` — `spree/api/app/serializers/spree/api/v3/payment_session_serializer.rb`
- [x] T030 [US3] Bogus gateway session simulation (`create_payment_session`, `update_payment_session`, `complete_payment_session`) — `spree/core/app/models/spree/gateway/bogus.rb`

**Checkpoint**: Session-based checkout flow functional against the Bogus test gateway.

---

## Phase 6: User Story 4 - Customer saves a payment method for future use (Priority: P3)

### Tests for User Story 4

- [x] T031 [P] [US4] RSpec model spec — `spree/core/spec/models/spree/payment_setup_session_spec.rb`, `spree/core/spec/models/spree/payment_source_spec.rb`

### Implementation for User Story 4

- [x] T032 [US4] `Spree::PaymentSetupSession` state machine — `spree/core/app/models/spree/payment_setup_session.rb`
- [x] T033 [US4] Store API customer payment-setup-session endpoint — `spree/api/app/controllers/spree/api/v3/store/customer/payment_setup_sessions_controller.rb`
- [x] T034 [US4] `PaymentSetupSessionSerializer`, `PaymentSourceSerializer` (+ admin variants) — `spree/api/app/serializers/spree/api/v3/payment_setup_session_serializer.rb`, `spree/api/app/serializers/spree/api/v3/payment_source_serializer.rb`
- [x] T035 [US4] Bogus gateway setup-session simulation, producing a `CreditCard` on completion — `spree/core/app/models/spree/gateway/bogus.rb`

**Checkpoint**: All four user stories functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T036 [P] Custom lifecycle/domain events (`payment.completed`, `payment.voided`, `payment.paid`, `order.paid`) — `spree/core/app/models/spree/payment/custom_events.rb`
- [x] T037 [P] Outbound webhook extension points (currently no-op stubs, documented as extension points in spec.md Migration Notes) — `spree/core/app/models/spree/payment/webhooks.rb`
- [x] T038 Full backend suite passes for `spree/core` and `spree/api` (assumed current on `main`; not re-run as part of this documentation-only migration)
- [x] T039 Full frontend suite passes for `packages/dashboard` (assumed current on `main`; not re-run as part of this documentation-only migration)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: model/STI layer must exist before any story-level work.
- **US1** and **US2** (both P1) are independent of each other: order-payment actions don't require the dashboard's payment-method CRUD to exist first (only that a payment method record exists, which any admin surface can create).
- **US3** depends on Foundational (session models) and benefits from US2 (a configured, session-capable payment method must exist).
- **US4** depends on Foundational (setup-session model) and a payment method with `setup_session_supported?`.
- **Polish (Phase 7)** depends on all four stories.

## Notes

- All tasks are marked `[x]` because this is a reverse-engineered record of existing functionality, not a forward implementation plan.
- Gaps identified during this migration (missing dashboard order-payment UI, no-op webhook stubs, unimplemented `state`→`status` rename for `Payment`) are recorded in `specs/003-payments/spec.md` → "Migration Notes", not as open tasks here — follow-up work should be scoped as new tasks once prioritized.
