# Implementation Plan: Payments

**Branch**: `003-payments` | **Date**: 2026-08-25 | **Spec**: `specs/003-payments/spec.md`

**Input**: Feature specification from `/specs/003-payments/spec.md`

**Note**: This document is reverse-engineered (`/speckit.brownfield.migrate`) from already-shipped code. It describes the plan as it would read if written before implementation, for the purpose of bringing the existing Payments feature under spec-kit tracking. No new work is scoped by this plan.

## Summary

Payments in Spree are modeled as a `Spree::Payment` state machine (`checkout → processing → pending/completed/void/invalid`) attached to an order and a store-scoped, STI `Spree::PaymentMethod` (base, `Spree::Gateway`, `Spree::PaymentMethod::StoreCredit`). Gateways delegate authorize/purchase/capture/void/credit to a provider object; a `Spree::Gateway::Bogus` test double ships in core for specs/demos. Two session models (`Spree::PaymentSession`, `Spree::PaymentSetupSession`) decouple hosted/embedded/tokenized payment flows from order completion, driven by per-gateway overrides of a common `Spree::PaymentMethod` contract (`create_payment_session`, `parse_webhook_event`, etc.). The Admin API exposes order payment create/capture/void and full payment-method CRUD; the dashboard SPA manages payment-method configuration (not per-order actions, which remain Rails-admin-only today).

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, backend) and TypeScript (React SPA, frontend) — both sides touched.

**Primary Dependencies**: Backend: `state_machines-activerecord` (Payment/PaymentSession/PaymentSetupSession state machines), CanCanCan, Ransack, Alba serializers, `acts_as_list`/`acts_as_paranoid` (PaymentMethod, CreditCard). Frontend: TanStack Query (`use-payment-methods.ts`), React Hook Form + Zod (`payment-method.ts` schema), shadcn/ui + Base UI, `@spree/dashboard-core` slot registry (per-provider form/guide/actions injection).

**Storage**: PostgreSQL (production) / SQLite3 (backend tests) via ActiveRecord. `spree_payments`, `spree_payment_methods`, `spree_credit_cards`, `spree_payment_sources` (generic), `spree_payment_sessions`, `spree_payment_setup_sessions`, `spree_payment_capture_events`, `spree_log_entries`, `spree_state_changes` tables (inferred from associations; not independently verified against `db/`).

**Testing**: RSpec + Factory Bot — `spree/core/spec/models/spree/{payment,payment_method,payment_session,payment_setup_session,payment_source}_spec.rb`, `spree/core/spec/models/spree/order/payment_spec.rb`. No dashboard Vitest/Playwright coverage located for payment methods specifically (see spec.md Migration Notes).

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`, `spree/admin`) consumed by a Spree host app; `packages/dashboard` React SPA consuming the Admin API.

**Project Type**: Monorepo — `spree/core`, `spree/api`, `spree/admin` (legacy, order-payment actions only), `packages/dashboard`, `packages/dashboard-core` (slots), `packages/admin-sdk`/`packages/sdk` (generated types).

**Performance Goals**: Not documented in code/comments — no explicit SLA found for gateway call latency or payment throughput.

**Constraints**: No raw card numbers/CVV persisted (`CreditCard#number`/`#verification_value` are non-persisted `attr_reader`s); payments cannot be deleted via admin (`can_be_deleted?` hardcoded `false`); gateway connectivity failures must resolve to `failed`, never leave a payment ambiguous.

**Scale/Scope**: Single `Spree::Payment` model + 2 session models + STI `PaymentMethod`/`Gateway` hierarchy + 1 test gateway (`Bogus`) + 1 admin settings page; ~1,742 lines across the 12 core backend files read for this migration (see below).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (models), `spree/api` (Store + Admin controllers/serializers), `spree/admin` (legacy order-payment actions — no new admin-only features should be added here per Principle I, but existing capture/void endpoints remain the only surface), and `packages/dashboard`/`packages/dashboard-core` (payment-method settings + slot registry). Cross-module coupling goes through the Admin API and the `Spree::Dependencies`-style STI/override contract (`payment_source_class`, `create_payment_session`, etc.) — no direct gem-to-package reach-across found. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: `packages/dashboard`'s payment-method hooks (`use-payment-methods.ts`) go exclusively through `adminClient.paymentMethods.*` (Admin API), never Rails models directly. **Pass.** (N/A caveat: no dashboard UI exists yet for order-level payment capture/void — those actions are Rails-admin-only; this is a gap, not a violation, since no SPA code reaches around the API for them.)
- **III. Read/Write Field Symmetry**: `Admin::Orders::PaymentsController#permitted_params` (`:amount, :payment_method_id, :source_id`) matches what `create` accepts; `status` is a read-only computed alias of `state` in the serializer (not writable, not expected to be). `PaymentMethodsController` permits the same attributes plus dynamic `preferred_*` preference keys the serializer's `preference_schema` exposes. **Pass** — no field-name mismatches found between serializer output and controller `permitted_params`.
- **IV. Test-Backed**: RSpec model specs exist for `Payment`, `PaymentMethod`, `PaymentSession`, `PaymentSetupSession`, `PaymentSource`, and `Order::Payment` in `spree/core/spec/models/spree/`. No Vitest/Playwright specs found for `packages/dashboard`'s payment-method editor — flagged in spec.md Migration Notes as a coverage gap for future work, not fixed by this migration (migration is documentation-only).
- **V. Translations and Prefixed IDs**: Dashboard payment-method form uses `useTranslation()`/`t('admin.fields.payment_method.*')` throughout (`payment-method-form.tsx`) — no hardcoded strings found. All IDs are prefixed (`py_`, `pm_`, `card_`, `ps_`, `pss_` — see `has_prefix_id` calls in each model) and serializers return `prefixed_id` for associations. **Pass.**
- **VI. `docs/plans/` for Architectural Changes**: No new architectural change is being made by this migration (documentation-only). The one live plan (`6.0-normalize-state-to-status.md`) lists `Payment` as in-scope for a `state`→`status` column rename that does not appear implemented yet (see spec.md Migration Notes) — any future work on `Payment#state` must go through that existing plan, not a new one.

Any violation must appear in Complexity Tracking below with justification.

## Project Structure

### Documentation (this feature)

```text
specs/003-payments/
├── plan.md              # This file
├── spec.md              # Feature specification (migrated)
└── tasks.md             # Task breakdown (migrated, all marked complete)
```

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/app/models/spree/payment.rb
spree/core/app/models/spree/payment/processing.rb
spree/core/app/models/spree/payment/webhooks.rb
spree/core/app/models/spree/payment/custom_events.rb
spree/core/app/models/spree/payment/gateway_options.rb
spree/core/app/models/spree/payment_method.rb
spree/core/app/models/spree/gateway.rb
spree/core/app/models/spree/gateway/bogus.rb
spree/core/app/models/spree/credit_card.rb
spree/core/app/models/spree/payment_source.rb
spree/core/app/models/concerns/spree/payment_source_concern.rb
spree/core/app/models/spree/payment_session.rb
spree/core/app/models/spree/payment_setup_session.rb
spree/core/spec/models/spree/payment_spec.rb, payment_method_spec.rb, payment_session_spec.rb,
                          payment_setup_session_spec.rb, payment_source_spec.rb
spree/core/spec/models/spree/order/payment_spec.rb

# spree/api — Store & Admin REST API v3
spree/api/app/controllers/spree/api/v3/admin/orders/payments_controller.rb
spree/api/app/controllers/spree/api/v3/admin/payment_methods_controller.rb
spree/api/app/controllers/spree/api/v3/store/carts/payments_controller.rb
spree/api/app/controllers/spree/api/v3/store/carts/payment_sessions_controller.rb
spree/api/app/controllers/spree/api/v3/store/customer/payment_setup_sessions_controller.rb
spree/api/app/controllers/spree/api/v3/webhooks/payments_controller.rb
spree/api/app/serializers/spree/api/v3/payment_serializer.rb
spree/api/app/serializers/spree/api/v3/payment_method_serializer.rb
spree/api/app/serializers/spree/api/v3/payment_session_serializer.rb
spree/api/app/serializers/spree/api/v3/payment_setup_session_serializer.rb
spree/api/app/serializers/spree/api/v3/payment_source_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/payment_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/payment_method_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/payment_source_serializer.rb

# spree/admin — legacy Rails admin (order-level payment actions; not extended further per Principle I)
spree/admin/app/controllers/spree/admin/payments_controller.rb
spree/admin/app/controllers/spree/admin/payment_methods_controller.rb
spree/admin/app/controllers/spree/admin/integrations_controller.rb

# packages/dashboard — admin SPA routes/forms (payment method settings only)
packages/dashboard/src/routes/_authenticated/$storeId/settings/payment-methods.tsx
packages/dashboard/src/hooks/use-payment-methods.ts
packages/dashboard/src/schemas/payment-method.ts
packages/dashboard/src/components/spree/payment-method-editors/payment-method-form.tsx
packages/dashboard/src/components/spree/payment-method-editors/types.ts
packages/dashboard/src/tables/payment-methods.tsx

# packages/dashboard-core — shared registries
packages/dashboard-core (Slot registry consumed via paymentMethodFormSlot/paymentMethodGuideSlot/paymentMethodActionsSlot)

# packages/sdk / packages/admin-sdk — generated clients
packages/admin-sdk/src/types/generated/Payment.ts, PaymentMethod.ts (+ Create/UpdateParams)
packages/sdk/src/types/generated/Payment.ts
```

**Structure Decision**: Backend-and-frontend, per the Module Impact table in spec.md: `spree/core` owns the domain model and state machines; `spree/api` exposes order-payment actions (Admin) and cart/session/webhook endpoints (Store); `spree/admin` remains the only UI for per-order payment capture/void (legacy, not to be extended); `packages/dashboard` + `packages/dashboard-core` own payment-method (provider) configuration UI, with generated types in `packages/admin-sdk`/`packages/sdk`.

## Complexity Tracking

No constitution violations identified — table intentionally left empty.
