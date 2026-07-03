---

description: "Task list for Customer Groups — fully shipped"
---

# Tasks: Customer Groups

**Status**: Fully shipped

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/customers/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |

---

## Phase 1: Core + API + SPA ✅

### Models

- [x] T001 `spree/core/app/models/spree/customer_group.rb` — `has_prefix_id :cg`; `acts_as_paranoid`; `include Spree::SingleStoreResource`; `has_many :customer_group_users`; `has_many :users` through `customer_group_users` (via `Spree.user_class`); `customers_count` counter cache; validates `name` presence and uniqueness scoped to `store_id`
- [x] T002 `spree/core/app/models/spree/customer_group_user.rb` — polymorphic `user` (`user_id`, `user_type`); `belongs_to :customer_group`; unique index on `(customer_group_id, user_id, user_type)`

### Migrations

- [x] T003 `spree_customer_groups` table — `name string null: false`, `description text`, `store_id string null: false`, `customers_count integer default 0`, `deleted_at`, timestamps; index `store_id`
- [x] T004 `spree_customer_group_users` table — `customer_group_id string null: false`, `user_id string null: false`, `user_type string null: false`, timestamps; unique index `(customer_group_id, user_id, user_type)`

### Serializers

- [x] T005 [P] `spree/api/app/serializers/spree/api/v3/admin/customer_group_serializer.rb` — `id` (cg_…), `name`, `description`, `customers_count`, `store_id`, `created_at`, `updated_at`, `deleted_at`

### Controllers

- [x] T006 `spree/api/app/controllers/spree/api/v3/admin/customer_groups_controller.rb` — full CRUD; bulk customer assignment action; `scope` filtered to `current_store`; Ransack on `name`, `customers_count`

### Routes

- [x] T007 Routes: `resources :customer_groups`

### Specs

- [x] T008 `spree/core/spec/models/spree/customer_group_spec.rb` — `customers_count` counter; name uniqueness scoped to store; paranoid soft-delete; `SingleStoreResource` scoping
- [x] T009 `spree/api/spec/integration/spree/api/v3/admin/customer_groups_spec.rb` — CRUD; bulk assignment; store scoping; soft-delete excluded from default scope

### Type Pipeline

- [x] T010 `bundle exec rake typelizer:generate` — `AdminCustomerGroup` type generated
- [x] T011 `cd packages/sdk && pnpm generate:zod`
- [x] T012 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T013 [US1/US2] `packages/dashboard/src/routes/_authenticated/$storeId/customers/groups.tsx` — list + create/edit groups; inline member management via customer autocomplete `<Combobox>`; `customers_count` badge
- [x] T014 `packages/dashboard/src/hooks/use-customer-groups.ts` — TanStack Query wrappers with pagination
- [x] T015 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.customerGroups.*`
- [x] T016 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

**Checkpoint**: admin can create groups, assign customers, soft-delete groups; store scoping prevents cross-store access ✅

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No bulk member export endpoint | Low | CSV export covered by admin-spa-csv-export plan; not a gap in group management itself |
| No standalone `GET /customer_groups/:id/customers` pagination endpoint | Low | Members accessible via `expand=customers` on group show; separate paginated endpoint would be useful for large groups |
