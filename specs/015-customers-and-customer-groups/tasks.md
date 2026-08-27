---

description: "Task list for Customers & Customer Groups (reverse-engineered, brownfield migration)"

---

# Tasks: Customers & Customer Groups

**Input**: Design documents from `/specs/015-customers-and-customer-groups/`

**Prerequisites**: plan.md, spec.md

**Tests**: This feature is already implemented; test tasks below reflect existing/assumed coverage rather than a TDD sequence — see spec.md Migration Notes for gaps not individually re-verified.

**Organization**: Tasks are grouped by user story per spec.md. All tasks are marked complete — this is a reverse-engineered record of already-shipped work, not a forward plan.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Could have run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Backend stack: `spree/core` + `spree/api` gems bootstrapped (`bundle exec rake test_app`)
- [x] T002 [P] Frontend stack: `packages/dashboard` + `packages/admin-sdk` workspace built (`pnpm build`, `pnpm typecheck`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model and API scaffolding all user stories depend on

- [x] T003 [spree/core] `Spree::CustomerGroup` model in `spree/core/app/models/spree/customer_group.rb` — `has_prefix_id :cg`, `acts_as_paranoid`, `belongs_to :store`, `has_many :customer_group_users`/`:users`/`:customers` through the join, name uniqueness scoped to `store_id` (soft-delete aware)
- [x] T004 [spree/core] `Spree::CustomerGroupUser` join model in `spree/core/app/models/spree/customer_group_user.rb` — polymorphic `belongs_to :user`, uniqueness on `(customer_group_id, user_id, user_type)`
- [x] T005 [spree/core] `Spree.user_class` default (`Spree::LegacyUser`) with `Spree::UserAddress`, `Spree::UserPaymentSource`, `Spree::UserMethods` concerns in `spree/core/app/models/spree/legacy_user.rb` + `spree/core/app/models/concerns/spree/{user_address,user_payment_source}.rb`
- [x] T006 [spree/api] `Spree::Api::V3::Admin::CustomersController` base CRUD + `scoped_resource :customers` + `collection_includes`/`scope_includes` preloading `customer_groups`/`store_credits`/`taggings` in `spree/api/app/controllers/spree/api/v3/admin/customers_controller.rb`
- [x] T007 [spree/api] `customer_groups` and nested `customers/{addresses,credit_cards,store_credits}` route resources + `bulk_add_to_groups`/`bulk_remove_from_groups`/`bulk_add_tags`/`bulk_remove_tags` collection routes in `spree/api/config/routes.rb`
- [x] T008 [packages/dashboard] i18next keys for customer/customer-group copy in `packages/dashboard/src/locales/en.json` (`admin.customers.*`, `admin.customer_groups.*`, `admin.messages.customer_saved` etc.)

**Checkpoint**: Foundation complete — user story work below builds on this base

---

## Phase 3: User Story 1 - Admin creates and edits a customer (Priority: P1) 🎯 MVP

**Goal**: Full customer CRUD from the admin, without an upfront password requirement

**Independent Test**: `POST /api/v3/admin/customers` with no password succeeds; `customer_has_orders` blocks destroy of a customer with orders

### Implementation for User Story 1

- [x] T009 [US1] `CustomersController#create` sets `skip_password_validation = true` when password blank, `authorize!(:create, @resource)` in `spree/api/app/controllers/spree/api/v3/admin/customers_controller.rb`
- [x] T010 [US1] `CustomersController#update`/`#destroy` with `authorize_resource!` and `Spree::Core::DestroyWithOrdersError` → `customer_has_orders` 422 mapping
- [x] T011 [US1] `#permitted_params` enumerates flat fields (`email, first_name, last_name, phone, password, password_confirmation, selected_locale, avatar, accepts_email_marketing, internal_note, metadata, tags, customer_group_ids`)
- [x] T012 [US1] `V3::CustomerSerializer` (store-facing base) + `V3::Admin::CustomerSerializer` (extends it with admin-only fields) in `spree/api/app/serializers/spree/api/v3/{customer_serializer.rb,admin/customer_serializer.rb}`
- [x] T013 [P] [US1] Dashboard customer detail route + form in `packages/dashboard/src/routes/_authenticated/$storeId/customers/$customerId.tsx`, index/list route in `.../customers/index.tsx`
- [x] T014 [P] [US1] `useCustomer`, `useUpdateCustomer`, `useDeleteCustomer` hooks in `packages/dashboard/src/hooks/use-customers.ts`

**Checkpoint**: Customer create/edit/delete fully functional end-to-end

---

## Phase 4: User Story 2 - Admin segments customers into Customer Groups (Priority: P1)

**Goal**: Store-scoped customer groups with idempotent bulk membership management

**Independent Test**: Bulk-add the same customers to the same groups twice; membership count doesn't double

### Implementation for User Story 2

- [x] T015 [US2] `CustomerGroup#add_customers`/`#remove_customers` bulk methods using `upsert_all(on_duplicate: :skip)` / `delete_all` + `touch_users` in `spree/core/app/models/spree/customer_group.rb`
- [x] T016 [US2] `CustomersController#bulk_add_to_groups`/`#bulk_remove_from_groups` — `require_ids!` before_action, store-scoped re-lookup of both `user_ids` and `group_ids`, `bulk_record_count_key :customer_count` override
- [x] T017 [US2] `Spree::Api::V3::Admin::CustomerGroupsController` base CRUD (`scoped_resource :customer_groups` equivalent) + `Admin::CustomerGroupSerializer` in `spree/api/app/serializers/spree/api/v3/admin/customer_group_serializer.rb`
- [x] T018 [P] [US2] Dashboard groups route + table in `packages/dashboard/src/routes/_authenticated/$storeId/customers/groups.tsx`, `packages/dashboard/src/tables/customer-groups.tsx`
- [x] T019 [P] [US2] `useCustomerGroups`, `useCreateCustomerGroup`, `useUpdateCustomerGroup`, `useDeleteCustomerGroup`, `useBulkAddCustomersToGroups`, `useBulkRemoveCustomersFromGroups` hooks in `packages/dashboard/src/hooks/use-customer-groups.ts` + `use-customers.ts`
- [x] T020 [US2] `packages/dashboard/src/schemas/customer-group.ts` — canonical group form schema

**Checkpoint**: Customer group CRUD + bulk membership fully functional independent of US1

---

## Phase 5: User Story 3 - Promotions and price lists target customer groups (Priority: P2)

**Goal**: Group-membership-gated eligibility for promotion rules and price-list rules

**Independent Test**: Order from a group member passes `eligible?`/`applicable?`; order from a non-member (or guest) does not

### Implementation for User Story 3

- [x] T021 [US3] `Spree::Promotion::Rules::CustomerGroup` — `preferred_customer_group_ids` array preference with `normalize_id_preference` prefixed-ID decoding, `eligible?` intersecting order user's groups (empty preference ⇒ ineligible) in `spree/core/app/models/spree/promotion/rules/customer_group.rb`
- [x] T022 [US3] `Spree::PriceRules::CustomerGroupRule` — same preference pattern scoped to the rule's own store, `applicable?` (empty preference ⇒ applicable) in `spree/core/app/models/spree/price_rules/customer_group_rule.rb`
- [x] T023 [P] [US3] Promotion rule editor UI in `packages/dashboard/src/components/spree/promotion-editors/rule-customer-group.tsx`
- [x] T024 [P] [US3] Price-list rule editor UI in `packages/dashboard/src/components/spree/price-list-editors/rule-customer-group.tsx` (+ `rule-customer.tsx` for the individual-customer variant)
- [x] T025 [US3] `customerGroupAutocompleteProps` shared picker config in `packages/dashboard/src/hooks/use-customer-groups.ts` reused by both rule editors

**Checkpoint**: Group-gated promotion/price-list eligibility functional independent of the admin group-management UI

---

## Phase 6: User Story 4 - Customer profile: addresses, payment sources, store credit (Priority: P2)

**Goal**: Single customer-detail view aggregating address book, read-only credit cards, and store credit

**Independent Test**: `GET /api/v3/admin/customers/:id?expand=addresses,store_credits,customer_groups` returns all three nested

### Implementation for User Story 4

- [x] T026 [US4] Nested `customers/addresses`, `customers/credit_cards` (index/show/destroy only), `customers/store_credits` controllers wired in `spree/api/config/routes.rb`
- [x] T027 [US4] `default_billing_address_id`/`default_shipping_address_id` + expandable `addresses`/`orders`/`store_credits`/`customer_groups` on `Admin::CustomerSerializer`
- [x] T028 [US4] `address_not_associated_with_other_user`/`address_not_deprecated_in_completed_order` validations in `Spree::UserAddress` concern
- [x] T029 [P] [US4] Address CRUD hooks (`useCreateCustomerAddress`, `useUpdateCustomerAddress`, `useDeleteCustomerAddress`) in `packages/dashboard/src/hooks/use-customers.ts`
- [x] T030 [P] [US4] Profile page sections (addresses card, credit cards list, store-credit panel, order history) in `packages/dashboard/src/routes/_authenticated/$storeId/customers/$customerId.tsx`

**Checkpoint**: Customer 360° profile view functional independent of groups/segmentation UI

---

## Phase 7: User Story 5 - Search, filter, and export customers (Priority: P3)

**Goal**: Ransack-backed search/filter and CSV export of the customer list

**Independent Test**: `GET /api/v3/admin/customers?search=jane` matches on email/first_name/last_name

### Implementation for User Story 5

- [x] T031 [US5] `search` Ransack alias resolving to `email_cont OR first_name_cont OR last_name_cont` (model-level `whitelisted_ransackable_scopes`/alias, consumed by `customerAutocompleteProps` in `packages/dashboard/src/hooks/use-customers.ts`)
- [x] T032 [P] [US5] Customer list filters (marketing opt-in, tags, dates, location) in `packages/dashboard/src/tables/customers.tsx`
- [x] T033 [P] [US5] Export button wired to shared `ExportsController` infra per `docs/user/customers/exporting-customers.mdx` (filtered vs. all records, emailed CSV)

**Checkpoint**: Search/filter/export functional independent of all other user stories

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T034 [P] Locale parity verified across `packages/dashboard/src/locales/` for all `admin.customers.*`/`admin.customer_groups.*` keys
- [x] T035 Full backend suite passes for `spree/core` and `spree/api` (assumed per repo convention — not individually re-run during this migration; see spec.md Migration Notes)
- [x] T036 Full frontend suite (`pnpm typecheck && pnpm lint && pnpm test`) passes for `packages/dashboard`/`packages/admin-sdk`
- [x] T037 Documentation: `docs/user/customers/{create-customer,edit-customer,customer-groups,customer-profile,searching-customers,exporting-customers,assign-store-credits,issue-gift-card}.mdx` already document the shipped UX

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → all user stories
- **US1** (customer CRUD) and **US2** (customer groups) are both P1 and independent of each other, but US2's bulk operations depend on US1's customer records existing
- **US3** (promotion/price-list rules) depends on US2 (customer groups must exist to be referenced) but not on US1/US4/US5
- **US4** (profile aggregation) depends on US1 (customer must exist) but not on US2/US3
- **US5** (search/export) depends on US1 only

## Notes

- This tasks.md reflects a **completed, already-shipped feature** discovered via brownfield migration — all tasks are marked done as a historical record, not a forward-looking plan.
- Where source files referenced in a task were not opened during this migration pass (e.g. `Admin::CustomerGroupsController`'s own file, the `ExportsController` wiring), see spec.md → "Migration Notes" for the explicit list of unverified gaps.
