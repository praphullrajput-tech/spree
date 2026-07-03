---

description: "Task list for Returns & Refunds — models + serializers shipped; API controller + SPA entirely PENDING; 6.0 replaces chain"
---

# Tasks: Returns & Refunds

**Status**: Models + serializers shipped; Admin API controller MISSING; SPA PENDING; 6.0 replaces entire chain

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/orders/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core Models ✅

### Models

- [x] T001 `spree/core/app/models/spree/return_authorization.rb` — `has_prefix_id :ra`; state machine: `authorized → canceled`; belongs_to order; has_many return_items; number generator (`RA` prefix); `memo`, `stock_location_id`
- [x] T002 `spree/core/app/models/spree/return_item.rb` — `has_prefix_id :ri`; eligibility validator; exchange variant; refund amount calculator; belongs_to return_authorization, inventory_unit; `acceptance_status`: `pending → accepted / rejected / manual_intervention_required`
- [x] T003 `spree/core/app/models/spree/reimbursement.rb` — `has_prefix_id :reimb`; groups return_items for a single reimbursement; `reimbursement_status`: `pending → reimbursed`; number generator (`RI` prefix); `perform!` orchestrates refund creation
- [x] T004 `spree/core/app/models/spree/refund.rb` — `has_prefix_id :re`; `after_create :perform!` — synchronous gateway call; belongs_to payment, reimbursement; `amount`, `transaction_id`
- [x] T005 `spree/core/app/models/spree/reimbursement_type/store_credit.rb` — reimbursement via store credit instead of gateway refund
- [x] T006 `spree/core/app/models/spree/reimbursement_type/original_payment.rb` — reimbursement back to original payment method

### Serializers

- [x] T007 `spree/api/app/serializers/spree/api/v3/admin/return_authorization_serializer.rb` — status, memo, reason_id, number, return_items, timestamps
- [x] T008 `spree/api/app/serializers/spree/api/v3/admin/return_item_serializer.rb` — acceptance_status, exchange_variant_id, pre_tax_amount, timestamps
- [x] T009 `spree/api/app/serializers/spree/api/v3/admin/reimbursement_serializer.rb` — reimbursement_status, number, return_items, refunds, timestamps
- [x] T010 `spree/api/app/serializers/spree/api/v3/admin/refund_serializer.rb` — amount, transaction_id, payment_id, timestamps

### Specs

- [x] T011 `spree/core/spec/models/spree/return_authorization_spec.rb` — state transitions; number generation; amount calculation
- [x] T012 `spree/core/spec/models/spree/return_item_spec.rb` — eligibility validator; acceptance status transitions; exchange engine
- [x] T013 `spree/core/spec/models/spree/reimbursement_spec.rb` — `perform!` orchestration; reimbursement type selection
- [x] T014 `spree/core/spec/models/spree/refund_spec.rb` — `after_create :perform!`; gateway call; failure handling

**Checkpoint**: 4-model chain + serializers shipped; legacy admin provides returns management ✅

---

## Phase 2: Admin API Controller (PENDING)

- [ ] T015 `spree/api/app/controllers/spree/api/v3/admin/return_authorizations_controller.rb` — nested under orders; index, show, create, update; action endpoints: `cancel`
- [ ] T016 `spree/api/app/controllers/spree/api/v3/admin/reimbursements_controller.rb` — nested under return_authorizations; index, show, create; action: `perform`
- [ ] T017 `spree/api/spec/integration/spree/api/v3/admin/return_authorizations_spec.rb` — CRUD; cancel action
- [ ] T018 Type pipeline: `bundle exec rake typelizer:generate` → `pnpm generate:zod` → `rswag:specs:swaggerize`

---

## Phase 3: SPA (PENDING)

- [ ] T019 Returns panel in `packages/dashboard/src/routes/_authenticated/$storeId/orders/$orderId.tsx` — list RAs, RA detail sheet with return items, accept/reject per item, trigger reimbursement
- [ ] T020 `packages/dashboard/src/hooks/use-return-authorizations.ts` — TanStack Query wrappers
- [ ] T021 Add i18n keys under `admin.return_authorizations.*`, `admin.return_items.*`, `admin.reimbursements.*` in all locale files
- [ ] T022 `packages/dashboard/e2e/returns.spec.ts` — create RA; accept items; trigger reimbursement; cancel RA
- [ ] T023 Run `pnpm test:e2e`

---

## Phase 4: 6.0 — Return/Exchange/Claim Models (PENDING)

Per `6.0-returns-exchanges-claims.md`:

- [ ] T024 Introduce `Spree::Return` (replaces `Spree::ReturnAuthorization`)
- [ ] T025 Introduce `Spree::Exchange` (dedicated exchange flow, replaces exchange on ReturnItem)
- [ ] T026 Introduce `Spree::Claim` (replaces `Spree::Reimbursement`)
- [ ] T027 Migrate/drop existing 4-model chain after data migration to new models

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No `return_authorizations_controller` in v3 Admin API | Critical | T015–T018; merchants cannot manage returns without legacy admin |
| No returns panel in admin SPA | Critical | T019–T023 is blocked on T015 |
| `after_create :perform!` on Refund is a synchronous gateway call | Medium | Risk of timeout on slow gateways; 6.0 should move to async job |
| No E2E for return flows | High | `returns.spec.ts` needed alongside T019 SPA work |
