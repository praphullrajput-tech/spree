# Implementation Plan: Order Approval & Cancellation

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: 5.5 models shipped; API controllers and SPA pending

---

## Summary

Replaces the denormalized `canceled_at` / `canceler_id` / `approved_at` / `approver_id` columns on `Spree::Order` with first-class `Spree::OrderCancellation` and `Spree::OrderApproval` models. This enables full cancellation history (cancel → resume → cancel again preserves all records), structured reasons (Shopify enum), restock/refund coupling in a single transaction, and an opt-in merchant approval gate before fulfillment. 5.5 ships the models and API alongside the existing denormalized columns (mirror pattern). 6.0 drops the denormalized columns. B2B cart-side approvals (buyer-organization internal sign-off) are deferred to 6.0 with `Spree::Company`.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Services** | `Spree::Orders::Cancel` + `Spree::Orders::Approve` — additive keyword params |
| **Actor polymorphism** | `canceled_by` and `approver` polymorphic: `AdminUser`, `User`, _(6.0)_ `CompanyContact` |
| **Backward compat** | Denormalized columns mirror latest record in 5.5; dropped in 6.0 |
| **Scope** | Models + migrations shipped; API controllers + SPA pending |

---

## Key Decisions

1. **Two separate models, not a single `OrderEvent` polymorphic one.** Cancellations and approvals have fundamentally different attributes (reason/restock/refund vs status/level/decided_at). A unified event model would require nullable columns for half the fields on every row — a denormalization that serves no query need.

2. **5.5 keeps denormalized columns.** `canceled_at`, `canceler_id`, `approved_at`, `approver_id` on `spree_orders` are mirrored from the latest record in each collection. This preserves backward compat for any external code reading those columns directly. Mirrors are updated in the same transaction as the record creation.

3. **6.0 drops denormalized columns.** `order.cancellations.order(:created_at).last.created_at` replaces `order.canceled_at`. This is a **breaking change** for direct DB consumers. The API surface (`canceled_at` in the order serializer) stays stable — it derives the value from the last record.

4. **`Spree::Orders::Cancel` is the only correct entry point.** Direct `OrderCancellation.create` bypasses the transactional guarantee (restock + refund + status update + record creation must be atomic). The service enforces this.

5. **Reasons use Shopify's enum string vocabulary.** `customer`, `declined`, `fraud`, `inventory`, `staff`, `other`, `expired` — stored as strings, not Rails enum. Industry-standard vocabulary enables cross-platform integrations without translation.

6. **Approval is opt-in per store.** `Order#requires_approval?` defaults to `false`. Merchants override it (e.g., `return order.total > 1000`) or a future per-store config flag controls it. When `false`, placed orders proceed to fulfillment immediately.

7. **Polymorphic actor (`canceled_by`, `approver`).** Replaces the legacy `canceler_id` integer FK that assumed `AdminUser`. In 5.5: accepts `AdminUser` and `User`. In 6.0: adds `CompanyContact` for B2B cart-side approvals.

8. **API controllers are pending.** The plan and models exist but the `Admin::Orders::CancellationsController` and `Admin::Orders::ApprovalsController` have not yet been built. This is the primary gap — models are spec'd; delivery surface is not.

---

## Constitution Check

- [x] **API-First**: API design fully specced (nested under orders); implementation pending
- [x] **Read/Write Symmetry**: `reason`, `note`, `restock_items`, `refund_payments`, `refund_amount` — same fields accepted as params and returned in serializer
- [x] **Prefixed IDs**: `cncl_…` for cancellations; `appr_…` for approvals
- [x] **Serializer Hierarchy**: `Admin::OrderCancellationSerializer` (admin-only — no Store serializer; cancellations are internal)
- [ ] **Type Pipeline**: PENDING — no serializers exist yet; pipeline blocked
- [x] **Security**: CanCanCan `can :manage, Spree::OrderCancellation`; actor is the logged-in admin user
- [x] **Namespace**: `Spree::OrderCancellation`, `Spree::OrderApproval` — `Spree.base_class` subclasses
- [x] **Plan Conflicts**: Reviewed `6.0-cart-order-split.md` — B2B cart-side approvals deferred to 6.0 with Cart model. Reviewed `5.5-6.0-order-cancellation-and-approval.md` — this spec faithfully reflects its content.

---

## Project Structure

```text
# Backend — models (✅ shipped 5.5)
spree/core/app/models/spree/order_cancellation.rb
spree/core/app/models/spree/order_approval.rb

# Backend — services (additive keyword params)
spree/core/app/services/spree/orders/cancel.rb                  ← extended with reason/note/restock/refund params
spree/core/app/services/spree/orders/approve.rb

# Backend — serializers (PENDING)
spree/api/app/serializers/spree/api/v3/admin/order_cancellation_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/order_approval_serializer.rb

# Backend — controllers (PENDING)
spree/api/app/controllers/spree/api/v3/admin/orders/cancellations_controller.rb
spree/api/app/controllers/spree/api/v3/admin/orders/approvals_controller.rb

# Backend — specs (✅ model specs exist)
spree/core/spec/models/spree/order_cancellation_spec.rb
spree/core/spec/models/spree/order_approval_spec.rb

# Backend — specs (PENDING)
spree/api/spec/integration/spree/api/v3/admin/orders/cancellations_spec.rb
spree/api/spec/integration/spree/api/v3/admin/orders/approvals_spec.rb

# Frontend (PENDING)
packages/dashboard/src/hooks/use-order-cancellations.ts
packages/dashboard/src/hooks/use-order-approvals.ts
# SPA UI integrated into order detail page (not a standalone route)
```

---

## Phase 1: 5.5 — Models + Service Extensions (✅ Complete)

- `Spree::OrderCancellation` model + migration (prefix `cncl_`, polymorphic `canceled_by`)
- `Spree::OrderApproval` model + migration (prefix `appr_`, polymorphic `approver`)
- `Order` associations: `has_many :cancellations`, `has_many :approvals`
- `Spree::Orders::Cancel` service extended with `reason`, `note`, `restock_items`, `refund_payments`, `refund_amount`, `notify_customer` kwargs
- Denormalized columns on `spree_orders` updated by services in the same transaction
- Model specs for both models

---

## Phase 2: API + SPA (PENDING)

- `Admin::Orders::CancellationsController` — `index`, `show`, `create`
- `Admin::Orders::ApprovalsController` — `index`, `show`, `create`
- Serializers for both models
- Type pipeline: `typelizer:generate` → `generate:zod`
- SPA: order detail cancellation panel (reason dropdown, restock/refund toggles, history timeline)
- SPA: order detail approval panel (approve/reject buttons, history timeline)
- Hooks: `use-order-cancellations.ts`, `use-order-approvals.ts`
- Integration specs + OpenAPI regen
- E2E: cancel order → verify status + stock movement; approve order → verify fulfillment unblocked

---

## Phase 3: 6.0 Cleanup (PENDING)

- Drop denormalized columns: `canceled_at`, `canceler_id`, `approved_at`, `approver_id` from `spree_orders`
- Update `Order` serializer: derive `canceled_at` from `order.cancellations.last.created_at`
- Multi-level approvals: `level` column (manager / finance / admin) made meaningful
- B2B cart-side approvals: `CompanyContact` as `approver_type`; approval model moves to `Cart` model

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Denormalized mirror columns in 5.5 | Backward compat for external code reading `spree_orders.canceled_at` directly | Removing immediately would break every integration that reads those columns; deferred drop in 6.0 is the safe migration path |
| Polymorphic `canceled_by` / `approver` | Actors can be admin users, staff, or (6.0) company contacts | Fixed FK to `AdminUser` would block B2B approvals and system-action auditing (nil actor = automated cancel) |
