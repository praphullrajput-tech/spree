# Implementation Plan: Price Lists

**Branch**: `main` (fully shipped) | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Implemented

---

## Summary

Admin-only alternate pricing system that lets merchants define multiple price schedules (wholesale, VIP, staff, promotional) and assign them to products. Each price list has a state machine (`draft`/`active`/`inactive`/`scheduled`), a match policy (`all`/`any`), an optional date range, and a set of pluggable `PriceRule` subtypes that determine which customers qualify. Price assignment is bulk-optimised via `upsert_all`. No store API surface — pricing is applied server-side by the pricing engine, not consumed directly by storefronts.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Serialization** | Alba → Typelizer |
| **State machine** | `state_machines-activerecord`; column: `status` |
| **Bulk upsert** | `upsert_all` for price assignment (performance) |
| **Rule registry** | `Spree.pricing.rules` — pluggable STI subtypes |
| **Scope** | Admin-only (no store API) |

---

## Key Decisions

1. **Admin-only.** Price lists are a back-office concept. Storefronts receive the resolved price after the engine applies them — they never query price lists directly.
2. **State machine on `status`.** `draft → active ↔ inactive`; `scheduled` state for future-dated lists. Transitions enforced via `state_machines-activerecord`.
3. **Plugin-registry for rule types.** `Spree.pricing.rules` registry avoids hardcoding rule subtypes. Extensions register their own rule classes without core changes.
4. **`upsert_all` for bulk price assignment.** Assigning prices to hundreds of products via individual `create` calls was too slow; `upsert_all` runs a single UPSERT per batch.
5. **Foreign membership guard.** A price list must reject products from stores it doesn't own — enforced at the controller level before the upsert.
6. **`accepts_nested_attributes_for :price_rules`.** Rules are managed inline on the price list form; no separate CRUD endpoint for rules.

---

## Constitution Check

- [x] **API-First**: Admin API built before SPA consumed it
- [x] **Read/Write Symmetry**: Serializer field names match `permitted_params` names
- [x] **Prefixed IDs**: `pl_…` prefix on all price list IDs
- [x] **Serializer Hierarchy**: Admin-only serializer (no store serializer needed)
- [x] **Type Pipeline**: Typelizer + Zod regen run after serializer changes
- [x] **Security**: CanCanCan `can :manage, Spree::PriceList`; store-scoped
- [x] **Namespace**: `Spree::PriceList`, `Spree::PriceRule` — `Spree.base_class`
- [x] **Plan Conflicts**: None — price lists are self-contained

---

## Project Structure

```text
# Backend
spree/core/app/models/spree/price_list.rb               ← state machine, bulk upsert, rules
spree/core/app/models/spree/price_rule.rb               ← STI base + registry

spree/api/app/serializers/spree/api/v3/admin/price_list_serializer.rb
spree/api/app/controllers/spree/api/v3/admin/price_lists_controller.rb

spree/core/spec/models/spree/price_list_spec.rb
spree/api/spec/integration/spree/api/v3/admin/price_lists_spec.rb

# Frontend
packages/dashboard/src/routes/_authenticated/$storeId/products/price-lists/
├── index.tsx
├── new.tsx
└── $priceListId/index.tsx
packages/dashboard/src/hooks/use-price-lists.ts
packages/dashboard/src/tables/price-lists.tsx
packages/dashboard/e2e/price-lists.spec.ts
```

---

## Phase 1: Backend Foundation (✅ Complete)

- `Spree::PriceList` model — state machine, match policy, date range, store scoping, `upsert_all` for bulk price assignment, foreign membership guard
- `Spree::PriceRule` STI base — `Spree.pricing.rules` registry
- Model spec covering state machine transitions, bulk upsert, foreign membership rejection
- Factory: `:price_list` with traits for each status

---

## Phase 2: Backend API (✅ Complete)

- `Admin::PriceListSerializer` — all fields including `price_rules`, `product_ids`, counts
- `Admin::PriceListsController` — full CRUD + `activate`, `deactivate`, `prices`, `price_rule_types` actions
- Routes: `resources :price_lists` with custom member/collection actions
- Integration spec (happy path + 422)

---

## Phase 3: Type Generation Pipeline (✅ Complete)

- `typelizer:generate` → `generate:zod` → `rswag:specs:swaggerize`

---

## Phase 4: Frontend (✅ Complete)

- `use-price-lists.ts` hooks
- List, new, edit routes
- `<StoreDatePicker includeTime>` for `starts_at` / `ends_at`
- Status badge with activate/deactivate actions
- i18n in all 6 locale files
- E2E: `price-lists.spec.ts`

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Custom `activate` / `deactivate` actions (not PATCH `status`) | State machine must validate transitions; direct `status=` bypasses guard conditions | Standard `update` would allow invalid transitions (e.g., `inactive → scheduled` directly) |
| `upsert_all` for bulk price assignment | Assigning prices to 500 products via individual creates was >10s | Single `upsert_all` runs in <1s for the same batch |
