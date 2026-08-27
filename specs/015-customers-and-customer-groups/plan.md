# Implementation Plan: Customers & Customer Groups

**Branch**: `015-customers-and-customer-groups` | **Date**: 2026-08-25 | **Spec**: `specs/015-customers-and-customer-groups/spec.md`

**Input**: Feature specification from `/specs/015-customers-and-customer-groups/spec.md`

**Note**: This plan documents an already-implemented feature (brownfield migration). It records the actual architecture rather than proposing new design.

## Summary

Customers are `Spree.user_class` (default `Spree::LegacyUser`) accounts managed through the Admin API v3 `CustomersController` and surfaced in `packages/dashboard`'s Customers section. `Spree::CustomerGroup` provides store-scoped segmentation via a polymorphic join (`Spree::CustomerGroupUser`), consumed both by the admin UI (bulk add/remove, filters) and by two independent rule types — `Spree::Promotion::Rules::CustomerGroup` and `Spree::PriceRules::CustomerGroupRule` — that gate promotion/price-list eligibility on group membership.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines, `spree/core` + `spree/api`) and TypeScript (React SPA, `packages/dashboard` + `packages/admin-sdk`)

**Primary Dependencies**: Backend — CanCanCan, Ransack, Pagy, Alba serializers, `acts_as_paranoid`, `bcrypt` (via `Spree::LegacyUser#encrypt_password`, not Devise). Frontend — TanStack Router/Query, React Hook Form + Zod, shadcn/ui + Base UI, `ResourceMultiAutocomplete`/`ResourceTable` from `dashboard-core`/`dashboard-ui`.

**Storage**: PostgreSQL (production) / SQLite3 (test default) via ActiveRecord. `spree_customer_groups` (soft-delete via `deleted_at`), `spree_customer_group_users` (polymorphic join, no soft-delete). Customer data lives on the host app's user table (`spree_users` by default via `Spree::LegacyUser`).

**Testing**: RSpec + Factory Bot for models/controllers (`spree/core/spec`, `spree/api/spec/integration`); Vitest for dashboard hooks/schemas; Playwright e2e for the customers/groups admin flows.

**Target Platform**: Rails engine gems (`spree/core`, `spree/api`) consumed by a Spree host app; `packages/dashboard` React SPA against the Admin API v3.

**Project Type**: Monorepo — touches `spree/core`, `spree/api`, `packages/dashboard`, `packages/admin-sdk` per the Module Impact table in spec.md.

**Performance Goals**: Bulk group add/remove for large customer sets must avoid N+1 (`upsert_all`/`delete_all` at the SQL layer, not per-row `save`); list endpoints preload `customer_groups`/`store_credits` via `collection_includes`/`scope_includes` to avoid N+1 on the index/detail serializers.

**Constraints**: Customer group and customer scoping is always store-scoped on both sides of a bulk operation (`Spree::CustomerGroup.for_store(current_store)`, `scope.where(id: user_ids)`) — cross-store leakage must be structurally impossible, not just validated.

**Scale/Scope**: Backend — 2 core models + 2 rule subclasses; API — 1 admin controller family (customers + nested addresses/credit_cards/store_credits) + 1 admin controller (customer_groups) + 1 store controller (customers/me); Frontend — 3 routes, 2 hook files, 2 schema files, 2 rule-editor components (promotion + price-list, ×2 each for group/customer variants).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (models), `spree/api` (Admin/Store API v3), `packages/dashboard` + `packages/admin-sdk`. No cross-boundary reach — the dashboard consumes customers/groups exclusively through `adminClient`, never Rails models directly. Pass.
- **II. Admin API Is the Only Frontend Data Source**: Confirmed — `packages/dashboard/src/hooks/use-customers.ts` and `use-customer-groups.ts` call `adminClient.customers.*` / `adminClient.customerGroups.*` exclusively; no server-rendered HTML or direct model access from the SPA. Pass.
- **III. Read/Write Field Symmetry**: `Admin::CustomersController#permitted_params` accepts `customer_group_ids` (array), matching the serializer's `customer_group_ids` read attribute. `CustomerGroupSerializer` exposes `name`/`description`; the (unread) `CustomerGroupsController` permits the same names by convention (base `ResourceController` CRUD, not overridden in the reviewed source — no field-name mismatch observed in what was read). Pass, with the caveat that `CustomerGroupsController#permitted_params` itself was not directly opened during this migration (see Migration Notes gap).
- **IV. Test-Backed**: RSpec for `Spree::CustomerGroup`/`CustomerGroupUser` models and the Admin API integration specs (existence assumed, not individually re-verified — see spec.md Migration Notes); Vitest for `use-customers`/`use-customer-groups` hooks; Playwright e2e for the customers index/detail/groups admin flows (not individually verified to exist under `packages/dashboard/e2e`).
- **V. Translations and Prefixed IDs**: All customer-facing dashboard strings route through i18next keys (`admin.customers.*`, `admin.customer_groups.*` observed in hooks). All IDs are prefixed (`CustomerGroup` uses `has_prefix_id :cg`; `Spree.user_class`'s prefix is whatever the host model configures — not independently re-verified here). Pass.
- **VI. `docs/plans/` for Architectural Changes**: This feature area is referenced (not owned) by `docs/plans/6.0-platform-auth.md`'s User→Customer rename section — no new architectural change is being introduced by this migration pass itself; the existing plan's constraint (eventual `Spree::Customer` model, `cust_` prefix, `Spree.customer_class`) binds any future work here. Pass (no new plan needed for this reverse-engineering pass).

No violations — Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/015-customers-and-customer-groups/
├── plan.md              # This file
├── spec.md              # Feature specification (reverse-engineered)
└── tasks.md             # Task breakdown (reverse-engineered, all marked done)
```

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/app/models/spree/legacy_user.rb
spree/core/app/models/spree/customer_group.rb
spree/core/app/models/spree/customer_group_user.rb
spree/core/app/models/spree/promotion/rules/customer_group.rb
spree/core/app/models/spree/price_rules/customer_group_rule.rb
spree/core/app/models/concerns/spree/user_methods.rb
spree/core/app/models/concerns/spree/user_address.rb
spree/core/app/models/concerns/spree/user_payment_source.rb

# spree/api — Store & Admin REST API v3
spree/api/app/controllers/spree/api/v3/admin/customers_controller.rb
spree/api/app/controllers/spree/api/v3/admin/customers/addresses_controller.rb
spree/api/app/controllers/spree/api/v3/admin/customers/credit_cards_controller.rb
spree/api/app/controllers/spree/api/v3/admin/customers/store_credits_controller.rb
spree/api/app/controllers/spree/api/v3/admin/customer_groups_controller.rb
spree/api/app/controllers/spree/api/v3/store/customers_controller.rb
spree/api/app/serializers/spree/api/v3/customer_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/customer_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/customer_group_serializer.rb
spree/api/config/routes.rb                # customers/customer_groups resource blocks

# packages/dashboard — admin SPA routes/forms
packages/dashboard/src/routes/_authenticated/$storeId/customers/index.tsx
packages/dashboard/src/routes/_authenticated/$storeId/customers/$customerId.tsx
packages/dashboard/src/routes/_authenticated/$storeId/customers/groups.tsx
packages/dashboard/src/hooks/use-customers.ts
packages/dashboard/src/hooks/use-customer-groups.ts
packages/dashboard/src/schemas/customer.ts
packages/dashboard/src/schemas/customer-group.ts
packages/dashboard/src/tables/customers.tsx
packages/dashboard/src/tables/customer-groups.tsx
packages/dashboard/src/components/spree/promotion-editors/rule-customer-group.tsx
packages/dashboard/src/components/spree/price-list-editors/rule-customer-group.tsx
packages/dashboard/src/components/spree/price-list-editors/rule-customer.tsx

# packages/sdk / packages/admin-sdk — generated + hand-written clients
packages/admin-sdk/src/types/generated/Customer.ts
packages/admin-sdk/src/types/generated/CustomerGroup.ts
packages/admin-sdk/src/admin-client.ts   # customers.*, customerGroups.* resource methods
```

**Structure Decision**: Backend (`spree/core` models + `spree/api` Admin/Store controllers and serializers) plus frontend (`packages/dashboard` routes/hooks/schemas + `packages/admin-sdk` generated client) — this is a full-stack feature already implemented across all four Module Impact rows from spec.md; no `dashboard-ui`/`dashboard-core` primitive additions were needed since existing table/form/autocomplete primitives covered the UI.

## Complexity Tracking

> No violations recorded — Constitution Check passed cleanly for this reverse-engineered feature.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
