# Implementation Plan: Store Credits & Gift Cards

**Branch**: `009-store-credits-and-gift-cards` | **Date**: 2026-08-24 | **Spec**: `specs/009-store-credits-and-gift-cards/spec.md`

**Input**: Feature specification from `specs/009-store-credits-and-gift-cards/spec.md`

**Note**: This is a brownfield migration plan — it documents the existing, already-shipped implementation rather than proposing new design. No new code is introduced by this plan.

## Summary

Store credits (`Spree::StoreCredit`) are per-customer, per-store monetary balances with an authorize/capture/void/credit lifecycle used by the store-credit payment method. Gift cards (`Spree::GiftCard`) are code-based, store-scoped prepaid balances with their own redemption state machine; redeeming a gift card creates a `Spree::StoreCredit` originated by that gift card. Bulk issuance of gift cards is handled by `Spree::GiftCardBatch`, synchronously below a configurable count and via `Spree::GiftCards::BulkGenerateJob` above it. Both entities are exposed through parallel Store API (guest/customer, read + cart-apply) and Admin API (full CRUD + order-apply) v3 surfaces, and partially through the `packages/dashboard` admin SPA (gift cards fully, store credits via a customer-profile panel; the legacy Rails admin still owns store-credit CRUD).

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines) for `spree/core` and `spree/api`; TypeScript (React SPA) for `packages/dashboard`.

**Primary Dependencies**: Backend — CanCanCan, Ransack, `state_machines-activerecord` (GiftCard), Alba serializers, `Spree::SingleStoreResource`, `Spree::Metafields`, `acts_as_paranoid` (StoreCredit). Frontend — TanStack Router/Query, React Hook Form + Zod, `@spree/dashboard-core` (`ResourceTable`, `useResourceMutation`, `usePermissions`), `@spree/dashboard-ui` (`Sheet`, `CurrencySelect`, `StoreDatePicker`).

**Storage**: PostgreSQL/SQLite3 via ActiveRecord. Key tables: `spree_store_credits`, `spree_store_credit_events`, `spree_store_credit_categories`, `spree_store_credit_types`, `spree_gift_cards`, `spree_gift_card_batches`.

**Testing**: RSpec + Factory Bot (`spree/core/spec/models/spree/`, `spree/api/spec/integration/`), Vitest (colocated in `packages/dashboard`), Playwright (`packages/dashboard/e2e`) — not individually enumerated in this migration pass (see spec.md Migration Notes gap).

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`) consumed by a Spree host app; `packages/dashboard` React SPA served standalone against the Admin API.

**Project Type**: Monorepo feature spanning `spree/core`, `spree/api`, `spree/admin` (legacy), and `packages/dashboard`.

**Performance Goals**: Gift card batch generation must not block the request thread past `Spree::Config[:gift_card_batch_web_limit]` codes — enforced via `Spree::GiftCards::BulkGenerateJob` offload.

**Constraints**: Single-store scoping (`Spree::SingleStoreResource`) on both `StoreCredit` and `GiftCard` — no cross-store balance sharing. UUID/prefixed-ID identifiers throughout (`credit_...`, `gc_...`, `gcb_...`) — no raw ID exposure.

**Scale/Scope**: 2 core models + 1 batch model + 1 background job + 9 API controllers (5 admin, 4 store) + 6 serializers + 1 legacy admin controller + ~6 SPA files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core`, `spree/api`, `spree/admin` (legacy, unchanged), and `packages/dashboard`. Cross-module coupling goes through the documented `Spree::Dependencies` registry (`Spree.checkout_add_store_credit_service`, `Spree.checkout_remove_store_credit_service`, `Spree.api.admin_gift_card_serializer`, etc.) and the Admin API — no direct gem/package boundary violations observed. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: `packages/dashboard`'s gift-card page and store-credit hooks call `adminClient` exclusively (`use-gift-cards.ts`, `use-customer-store-credits.ts`) — no server-rendered HTML or direct model access from the SPA. **Pass.**
- **III. Read/Write Field Symmetry**: Admin `GiftCardsController#permitted_params` (`code, amount, expires_at, user_id, currency`) matches serializer read fields it accepts writes for; `Admin::Customers::StoreCreditsController` permits `amount, currency, category_id, memo` on create and `memo, category_id, amount` on update, matching the serializer's writable subset (no legacy-name mismatches found — e.g. no `label`/`presentation`-style aliasing needed here). **Pass**, as observed; not independently re-verified against every serializer attribute in this pass.
- **IV. Test-Backed**: RSpec model/service specs and API integration specs are assumed present per repository convention but were not enumerated line-by-line in this migration (see spec.md gap). **Not fully verified** — flagged as a follow-up, not a plan violation since this is documentation-only.
- **V. Translations and Prefixed IDs**: All IDs are prefixed (`credit_`, `gc_`, `gcb_`) via `has_prefix_id`. SPA strings (gift card sheet, table columns, toasts) go through i18next per existing `packages/dashboard/src/locales/en.json` conventions — not independently line-audited in this pass. **Pass** (structurally), **not fully verified** (content audit out of scope).
- **VI. `docs/plans/` for Architectural Changes**: No `docs/plans/*.md` is dedicated to store credits/gift cards as a feature; `6.0-normalize-state-to-status.md` names `Spree::GiftCard`'s `state` column as a pending 6.0 rename target that binds any future work here. This spec-kit migration documents existing behavior and does not introduce new architecture, so no new `docs/plans/` entry is created — but the existing plan's constraint is carried into spec.md's Migration Notes. **Pass** (nothing new to gate).

No violations requiring Complexity Tracking — this is a documentation-only migration of existing code.

## Project Structure

### Documentation (this feature)

```text
specs/009-store-credits-and-gift-cards/
├── plan.md              # This file
├── spec.md              # Feature specification (includes Migration Notes)
└── tasks.md             # Task breakdown (all marked complete — already shipped)
```

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/app/models/spree/store_credit.rb
spree/core/app/models/spree/store_credit_event.rb
spree/core/app/models/spree/store_credit_category.rb
spree/core/app/models/spree/store_credit_type.rb
spree/core/app/models/spree/order/store_credit.rb          # concern: add/remove/total_applied_store_credit etc.
spree/core/app/models/spree/order/gift_card.rb              # concern: apply_gift_card / remove_gift_card
spree/core/app/models/spree/gift_card.rb
spree/core/app/models/spree/gift_card_batch.rb
spree/core/app/jobs/spree/gift_cards/bulk_generate_job.rb

# spree/api — Store & Admin REST API v3
spree/api/app/controllers/spree/api/v3/admin/gift_cards_controller.rb
spree/api/app/controllers/spree/api/v3/admin/gift_card_batches_controller.rb
spree/api/app/controllers/spree/api/v3/admin/store_credit_categories_controller.rb
spree/api/app/controllers/spree/api/v3/admin/customers/store_credits_controller.rb
spree/api/app/controllers/spree/api/v3/admin/orders/gift_cards_controller.rb
spree/api/app/controllers/spree/api/v3/admin/orders/store_credits_controller.rb
spree/api/app/controllers/spree/api/v3/store/carts/gift_cards_controller.rb
spree/api/app/controllers/spree/api/v3/store/carts/store_credits_controller.rb
spree/api/app/controllers/spree/api/v3/store/customer/gift_cards_controller.rb
spree/api/app/controllers/spree/api/v3/store/customer/store_credits_controller.rb
spree/api/app/serializers/spree/api/v3/gift_card_serializer.rb
spree/api/app/serializers/spree/api/v3/gift_card_batch_serializer.rb
spree/api/app/serializers/spree/api/v3/store_credit_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/gift_card_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/gift_card_batch_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/store_credit_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/store_credit_category_serializer.rb

# spree/admin — legacy Rails admin (store-credit CRUD not yet ported to SPA)
spree/admin/app/controllers/spree/admin/store_credits_controller.rb

# packages/dashboard — admin SPA routes/forms
packages/dashboard/src/routes/_authenticated/$storeId/promotions/gift-cards.tsx
packages/dashboard/src/tables/gift-cards.tsx
packages/dashboard/src/schemas/gift-card.ts
packages/dashboard/src/schemas/store-credit.ts
packages/dashboard/src/hooks/use-gift-cards.ts
packages/dashboard/src/hooks/use-customer-store-credits.ts
packages/dashboard/src/hooks/use-store-credit-categories.ts

# packages/sdk / packages/admin-sdk — generated clients
packages/admin-sdk/src/types/generated/   # AdminGiftCard, AdminGiftCardBatch, AdminStoreCredit types
```

**Structure Decision**: Full-stack feature already implemented across `spree/core` (2 models + 1 batch model + 1 job + 2 order concerns), `spree/api` (9 controllers, 7 serializers), `spree/admin` (1 legacy controller retained for store-credit CRUD), and `packages/dashboard` (1 route, 1 table, 2 schemas, 3 hooks). No `dashboard-ui`/`dashboard-core` changes were needed — existing primitives sufficed.

## Complexity Tracking

*No violations — not applicable.*
