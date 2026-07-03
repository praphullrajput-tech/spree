---

description: "Task list for Customers & Addresses — fully shipped in 5.5; 6.0 User→Customer rename pending"
---

# Tasks: Customers & Addresses

**Status**: Phase 1 (5.5 Admin API + SPA) fully shipped; Phase 2 (6.0 rename + GDPR) pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models / concerns | `spree/core/app/models/spree/` and `spree/core/app/models/concerns/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Nested controllers | `spree/api/app/controllers/spree/api/v3/admin/customers/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/customers/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: 5.5 — Admin API + SPA ✅

### Models

- [x] T001 `spree/core/app/models/concerns/spree/user_methods.rb` — `has_prefix_id :cus`; `belongs_to :store`; `has_many :orders`; `has_many :addresses`; `has_many :store_credits`; `has_many :customer_groups` via join; `has_many :credit_cards`; computed: `orders_count`, `total_spent`, `last_order_completed_at`; `tags`, `internal_notes`, `marketing_opt_in`
- [x] T002 `spree/core/app/models/spree/legacy_user.rb` — default `Spree.user_class`; BCrypt auth; no Devise; validates email uniqueness scoped to `store_id`
- [x] T003 `spree/core/app/models/spree/address.rb` — `has_prefix_id :addr`; paranoid; `include Spree::Metafields`; `belongs_to :country`; `belongs_to :state` (optional); country-configurable zipcode and state validation; `default_billing`, `default_shipping` flags; `label` string

### Serializers

- [x] T004 [P] `spree/api/app/serializers/spree/api/v3/admin/customer_serializer.rb` — `id` (cus_…), `email`, `first_name`, `last_name`, `phone`, `login`, `sign_in_count`, `last_sign_in_at`, `orders_count`, `total_spent`, `last_order_completed_at`, `tags`, `internal_notes`, `marketing_opt_in`, `customer_group_ids`, `created_at`, `updated_at`, `deleted_at`
- [x] T005 [P] `spree/api/app/serializers/spree/api/v3/admin/address_serializer.rb` — `id` (addr_…), `customer_id` (cus_…), `first_name`, `last_name`, `address1`, `address2`, `city`, `state_id`, `state_name`, `country_id`, `zipcode`, `phone`, `label`, `default_billing`, `default_shipping`, `metadata`, `created_at`, `updated_at`, `deleted_at`

### Controllers

- [x] T006 `spree/api/app/controllers/spree/api/v3/admin/customers_controller.rb` — full CRUD; `skip_password_validation` flag on create; Ransack on email/name/tags; `collection_includes`: addresses, customer_groups
- [x] T007 `spree/api/app/controllers/spree/api/v3/admin/customers/addresses_controller.rb` — `index`, `show`, `create`, `update`, `destroy`; scoped to `customer.addresses`; auto-manages `default_billing`/`default_shipping` flags on create/update

### Routes

- [x] T008 Routes: `resources :customers` with nested `resources :addresses`

### Specs

- [x] T009 `spree/core/spec/models/spree/user_spec.rb` — `orders_count` counter; email uniqueness scoped to store; address default flag management
- [x] T010 `spree/core/spec/models/spree/address_spec.rb` — zipcode optional for specific countries; state required for US/AU/CA; `default_billing` propagation
- [x] T011 `spree/api/spec/integration/spree/api/v3/admin/customers_spec.rb` — CRUD; `skip_password_validation`; store scoping; Ransack search
- [x] T012 `spree/api/spec/integration/spree/api/v3/admin/customers/addresses_spec.rb` — create address; default flag auto-management; country validation

### Type Pipeline

- [x] T013 `bundle exec rake typelizer:generate` — `AdminCustomer`, `AdminAddress` types generated
- [x] T014 `cd packages/sdk && pnpm generate:zod`
- [x] T015 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T016 [US1/US3] `packages/dashboard/src/routes/_authenticated/$storeId/customers/index.tsx` — list with bulk group assignment, tag management, CSV export toolbar; Ransack search by email/name/tags
- [x] T017 [US1/US2] `packages/dashboard/src/routes/_authenticated/$storeId/customers/$customerId.tsx` — detail with addresses sub-section (create/edit/delete), orders list, store credits; `AddressFormDialog`
- [x] T018 `packages/dashboard/src/hooks/use-customers.ts` — TanStack Query wrappers: list, show, create, update, delete
- [x] T019 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.customers.*` and `admin.addresses.*`
- [x] T020 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

**Checkpoint**: admin can list/create/edit/delete customers; address management with default flags; store scoping prevents cross-store access ✅

---

## Phase 2: 6.0 — User→Customer Rename + GDPR (PENDING)

Per `6.0-platform-auth.md` and `5.4-6.0-eu-legal-compliance.md`:

- [ ] T021 Rename `Spree::User` → `Spree::Customer` model; table `spree_users` → `spree_customers`; constant alias `Spree::User = Spree::Customer` for backward compat
- [ ] T022 Update `Spree.user_class` → `Spree.customer_class`; update all `Spree.user_class` references in core
- [ ] T023 Update prefix: `cus_` → `cust_`; migrate existing IDs
- [ ] T024 Drop Devise dependency; own JWT stack handles authentication
- [ ] T025 GDPR: `GET /api/v3/admin/customers/:id/data_export` — full customer data export (orders, addresses, metafields)
- [ ] T026 GDPR: `POST /api/v3/admin/customers/:id/anonymize` — anonymize PII on deleted customer
- [ ] T027 Add `consent_updated_at` timestamp for marketing opt-in tracking

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No Store API exposure for customer read (customer-facing profile page) | Low | Intentional for 5.5; Store API customer endpoints planned separately |
| GDPR endpoints (data export, anonymization) deferred | Medium | T025–T026 above per `5.4-6.0-eu-legal-compliance.md` |
| Prefix `cus_` will change to `cust_` in 6.0 | Low | By design; tracked in T023; API clients will need to handle both during migration period |
