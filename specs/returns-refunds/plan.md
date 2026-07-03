# Implementation Plan: Returns & Refunds

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Models + serializers shipped; return_authorizations_controller PENDING; 6.0 replaces chain

---

## Summary

The return/refund chain: `ReturnAuthorization` (RA) → `ReturnItem` (RI) → `Reimbursement` → `Refund`. An RA authorizes specific inventory units to be returned. Return items track per-unit eligibility and exchange variant. The reimbursement groups return items and executes the chosen reimbursement type (original payment, store credit, exchange). A refund is created by the reimbursement performer and triggers the gateway refund via `perform!`. Admin serializers exist for all four models, but the v3 admin API has no `return_authorizations_controller` — the entire RA lifecycle is managed via legacy Rails admin. The 6.0 plan replaces this entire chain with first-class `Return`, `Exchange`, `Claim` models.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **State machine** | `state_machines-activerecord` on ReturnAuthorization |
| **Scope** | Models + serializers shipped; API controller PENDING; 6.0 replacement planned |

---

## Key Decisions

1. **ReturnAuthorization is the entry point.** An RA authorizes the return before any items come back. It records which order, which stock location (for restocking), and the customer's stated reason.

2. **ReturnItem holds per-unit business logic.** `return_eligibility_validator` checks whether an inventory unit is eligible for return (e.g., not already returned, order is complete). `exchange_variant_engine` determines the exchange variant for exchanges. `refund_amount_calculator` determines how much to refund per unit.

3. **Reimbursement executes via performer.** `Spree::ReimbursementPerformer.perform!(reimbursement)` iterates return items and calls the appropriate reimbursement type strategy (issue store credit, trigger gateway refund, set up exchange).

4. **`Refund#after_create :perform!`.** Refund creation immediately triggers the gateway refund. This is a synchronous operation; if the gateway call fails, the refund record is not created (rolled back in the transaction).

5. **Admin serializers exist but no API controller for RAs.** All four models have admin serializers, but `return_authorizations_controller` is missing from the v3 API. The legacy Rails admin handles RA creation. This is the primary gap.

6. **6.0 replaces the entire chain.** `6.0-returns-exchanges-claims.md` introduces first-class `Return`, `Exchange`, `Claim` models. The current RA/RI/Reimbursement chain is designed around Spree's original checkout flow and will be replaced.

---

## Constitution Check

- [x] **Prefixed IDs**: `ra_…` (RA), `ri_…` (ReturnItem), `reimb_…` (Reimbursement), `re_…` (Refund)
- [x] **Serializer Hierarchy**: Admin serializers extend Store serializers for all four models
- [ ] **API-First**: _(PARTIAL)_ Serializers exist; return_authorizations_controller MISSING
- [x] **Security**: Nested under orders; CanCanCan guards; store scoping inherited from order
- [x] **Plan Conflicts**: `6.0-returns-exchanges-claims.md` replaces this chain entirely

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/return_authorization.rb                  ← ra_ prefix, state machine
spree/core/app/models/spree/return_item.rb                           ← ri_ prefix, eligibility/exchange/refund logic
spree/core/app/models/spree/reimbursement.rb                         ← reimb_ prefix, RI-prefixed number
spree/core/app/models/spree/refund.rb                                ← re_ prefix, after_create :perform!
spree/core/app/models/spree/return_authorization_reason.rb
spree/core/app/models/spree/reimbursement_type.rb
spree/core/app/models/spree/reimbursement_performer.rb
spree/core/app/models/spree/reimbursement_tax_calculator.rb

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/return_authorization_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/reimbursement_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/refund_serializer.rb

# Backend — controllers (PARTIAL)
spree/api/app/controllers/spree/api/v3/admin/orders/refunds_controller.rb    ← exists
# MISSING: orders/return_authorizations_controller.rb
# MISSING: orders/reimbursements_controller.rb

# Frontend (PENDING)
# No hooks or SPA pages for returns
```

---

## Phase 1: Models + Serializers (✅ Complete)

- Full model chain: ReturnAuthorization → ReturnItem → Reimbursement → Refund
- Admin serializers for all four models
- Refund controller nested under orders (exists)

---

## Phase 2: v3 API for RAs (PENDING)

- `orders/return_authorizations_controller.rb`: `index`, `show`, `create`, `cancel`
- `orders/reimbursements_controller.rb`: `show`, `create`
- Integration specs + OpenAPI regen
- Type pipeline regeneration

---

## Phase 3: SPA (PENDING)

- Returns panel on order detail: create RA, accept return items, trigger reimbursement
- Hook: `use-return-authorizations.ts`, `use-refunds.ts`

---

## Phase 4: 6.0 — Return/Exchange/Claim (PENDING)

Per `6.0-returns-exchanges-claims.md`:

- `Spree::Return` replaces `ReturnAuthorization` + `ReturnItem` chain
- `Spree::Exchange` for variant swaps
- `Spree::Claim` for store-credit or refund outcomes
- Drop `Spree::Reimbursement`, `Spree::ReimbursementType`, `Spree::ReimbursementPerformer`

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| 4-model chain (RA → RI → Reimbursement → Refund) | Each stage has distinct business rules: authorization ≠ item eligibility ≠ reimbursement type ≠ gateway action | Flat "return request" model cannot represent per-unit eligibility checks or mixed reimbursement types (some items store-credit, some refund) |
| `after_create :perform!` on Refund | Gateway refund must happen in the same transaction as the refund record creation | Separate service call would require idempotency handling for retries |
