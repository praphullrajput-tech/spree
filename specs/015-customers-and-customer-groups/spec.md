# Feature Specification: Customers & Customer Groups

**Feature Branch**: `015-customers-and-customer-groups`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — `Spree.user_class` (`Spree::LegacyUser`), `Spree::CustomerGroup`, `Spree::CustomerGroupUser`, `Spree::Promotion::Rules::CustomerGroup`, `Spree::PriceRules::CustomerGroupRule`, the Admin API v3 `CustomersController`/`CustomerGroupsController` + serializers, and the `packages/dashboard` customers admin UI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin creates and edits a customer (Priority: P1)

A store admin creates a new customer account from the admin dashboard (email, name, phone, marketing opt-in) without setting a password upfront, and can later edit that customer's profile, addresses, tags, and internal note.

**Why this priority**: Customer records are the base entity every other capability in this feature (groups, store credit, orders, addresses) attaches to.

**Independent Test**: `POST /api/v3/admin/customers` with `{ email, first_name, last_name }` and no password; confirm the customer is created with `skip_password_validation` set (so Devise's presence validation doesn't block account creation) and can be found via `GET /api/v3/admin/customers/:id`.

**Acceptance Scenarios**:

1. **Given** no existing customer with that email, **When** an admin submits the create form without a password, **Then** the customer is created (claims a password later via reset) and returned with a `cust`-style prefixed ID (`Spree.user_class`'s configured prefix).
2. **Given** an existing customer, **When** an admin updates `first_name`/`phone`/`internal_note`/`tags`/`metadata`, **Then** `PATCH /api/v3/admin/customers/:id` persists the change and the serializer reflects it on reload.
3. **Given** a customer with associated orders, **When** an admin attempts to delete them, **Then** the request fails with a `customer_has_orders` (422) error rather than raising unhandled.

---

### User Story 2 - Admin segments customers into Customer Groups (Priority: P1)

A store admin creates named, store-scoped Customer Groups (e.g. "VIP", "Wholesale") and assigns customers to them, individually or in bulk, so groups can be targeted by promotions and price lists.

**Why this priority**: Customer Groups are the segmentation primitive that promotions (`Promotion::Rules::CustomerGroup`) and price lists (`PriceRules::CustomerGroupRule`) both depend on — without groups those eligibility rules have nothing to reference.

**Independent Test**: `POST /api/v3/admin/customer_groups` with `{ name }`; then `POST /api/v3/admin/customers/bulk_add_to_groups` with `{ ids: [...customer_ids], customer_group_ids: [...] }`; verify `customers_count` on the group reflects the new members and the operation is idempotent (re-running it adds no duplicates).

**Acceptance Scenarios**:

1. **Given** a store with no groups, **When** an admin creates a group named "VIP", **Then** `Spree::CustomerGroup` validates uniqueness of `name` scoped to `store_id` (soft-delete aware) and the group belongs to `current_store`.
2. **Given** a set of customer IDs and group IDs, **When** an admin calls the bulk-add endpoint, **Then** `Spree::CustomerGroupUser` rows are inserted via `upsert_all(on_duplicate: :skip)`, affected customers are touched, and the response returns `customer_count`/`customer_group_count`.
3. **Given** customers already in a group, **When** the same bulk-add is repeated, **Then** no duplicate `CustomerGroupUser` rows are created and the reported added count for that repeat is 0 for those customers.
4. **Given** a group and a set of customer IDs, **When** an admin calls `bulk_remove_from_groups`, **Then** the matching `CustomerGroupUser` rows are deleted and affected customers are touched.

---

### User Story 3 - Promotions and price lists target eligible customer groups (Priority: P2)

A promotion rule or price-list rule is configured with one or more Customer Groups; the rule is only eligible/applicable for orders placed by a signed-in customer who belongs to at least one of the configured groups.

**Why this priority**: This is the payoff for segmentation — groups only have business value once promotions/pricing can key off them.

**Independent Test**: Configure `Spree::Promotion::Rules::CustomerGroup#preferred_customer_group_ids` with a group's ID; place an order as a user in that group and confirm `eligible?` returns true; place an order as a guest (`user_id` blank) and confirm it returns false.

**Acceptance Scenarios**:

1. **Given** a promotion rule with `preferred_customer_group_ids` set, **When** the order's user belongs to none of those groups, **Then** `eligible?` returns false.
2. **Given** a promotion rule with `preferred_customer_group_ids` empty, **When** any signed-in user's order is evaluated, **Then** `eligible?` returns false (empty preference means "no groups configured," not "any group").
3. **Given** a price rule (`PriceRules::CustomerGroupRule`) with empty `preferred_customer_group_ids`, **When** any signed-in user's context is evaluated, **Then** `applicable?` returns true (empty preference means "unrestricted" for pricing, the inverse convention from the promotion rule).
4. **Given** a preference value written with a prefixed ID (`cg_...`), **When** the model persists it, **Then** `parse_on_set: normalize_id_preference` decodes it to the raw ID before storage so eligibility lookups (raw `customer_group_id` comparisons) succeed.

---

### User Story 4 - Admin manages a customer's addresses, payment sources, and store credit from their profile (Priority: P2)

From a single customer detail page, an admin views/edits billing and shipping addresses, the customer's saved credit cards (read/delete only), their store credit balance, and their order history.

**Why this priority**: Consolidates the customer 360° view admins need for support and account management — the profile page is the primary daily-use surface for this feature.

**Independent Test**: `GET /api/v3/admin/customers/:id?expand=addresses,store_credits,customer_groups` returns nested addresses, store credits, and group chips in one call; `POST/PATCH/DELETE /api/v3/admin/customers/:id/addresses(/:address_id)` manage the address book.

**Acceptance Scenarios**:

1. **Given** a customer with a saved billing address, **When** an admin views the profile, **Then** `default_billing_address_id`/`default_shipping_address_id` on the serializer resolve to the customer's `bill_address`/`ship_address` prefixed IDs.
2. **Given** a customer's address is referenced by a completed order's `bill_address`, **When** an admin attempts to delete/reassign it, **Then** `address_not_deprecated_in_completed_order` blocks the change.
3. **Given** a customer with saved credit cards, **When** an admin views the profile, **Then** `credit_cards` are listed read-only (`index`, `show`, `destroy` only — no create/update via admin) since cards are tokenized through the payment gateway, not typed in.
4. **Given** a customer with available store credit, **When** viewed via `expand=store_credits`, **Then** the admin store credit serializer is nested inline.

---

### User Story 5 - Admin searches, filters, and exports the customer list (Priority: P3)

A store admin searches customers by name/email, filters by marketing opt-in / location / dates / tags, and exports the filtered (or full) list to CSV, delivered by email.

**Why this priority**: Operational/reporting workflow — valuable but not required for the core create/segment/target loop above.

**Independent Test**: `GET /api/v3/admin/customers?search=jane` resolves via Ransack alias to `email_cont OR first_name_cont OR last_name_cont`; the dashboard's export button (shared `ExportsController` infra) triggers a CSV export scoped to the current filter set.

**Acceptance Scenarios**:

1. **Given** a `search` param, **When** the customers index is queried, **Then** results include matches on email, first name, or last name (`Ransack` alias).
2. **Given** an active filter set (e.g. tags, marketing opt-in), **When** an admin clicks Export, **Then** they are prompted to export filtered vs. all records, and a CSV is generated and emailed rather than downloaded synchronously.

---

### Edge Cases

- What happens when an admin bulk-adds customer IDs that don't belong to `current_store`'s scope? The controller re-scopes both `user_ids` and `group_ids` (`scope.where(id: user_ids)`, `CustomerGroup.for_store(current_store)`) before dispatch, so out-of-store IDs are silently dropped rather than erroring.
- How does the system handle a `CustomerGroup` with the same name in a different store? Uniqueness is scoped to `store_id`, so the same name is valid across stores (single-owner customer groups, not shared).
- What happens to a `CustomerGroupUser` row when its `CustomerGroup` is soft-deleted (`acts_as_paranoid`)? The group `has_many :customer_group_users, dependent: :destroy` — membership rows are hard-destroyed alongside a group destroy/soft-delete cascade.
- What happens when both a promotion rule and a price rule reference the same group but the group is deleted? Both rules resolve `Spree::CustomerGroup.where(id: preferred_customer_group_ids)`, which returns an empty relation for deleted IDs — eligibility silently degrades to "no match" rather than erroring.
- A user with no groups configured on a promotion rule (`preferred_customer_group_ids.empty?`) is explicitly ineligible (`eligible?` returns false), while the equivalent empty state on a price rule is explicitly eligible (`applicable?` returns true) — these two rule types intentionally invert the empty-preference default.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow admins to create, view, update, and destroy customer accounts (`Spree.user_class`) without requiring a password at creation time.
- **FR-002**: System MUST prevent destroying a customer who has associated orders, surfacing a specific `customer_has_orders` error code instead of an unhandled exception.
- **FR-003**: System MUST allow admins to create, update, and soft-delete store-scoped `Spree::CustomerGroup` records with a unique `name` per store (uniqueness validated only against non-deleted rows).
- **FR-004**: System MUST support bulk add/remove of customers to/from one or more customer groups in a single request, idempotently (no duplicate membership rows), scoped to the current store on both sides (customers and groups).
- **FR-005**: System MUST expose `customer_group_ids`/`customers_count` on the customer group and customer serializers so the admin UI can render membership without N+1 queries (`collection_includes` preloads `customer_groups`).
- **FR-006**: System MUST let promotion rules (`Promotion::Rules::CustomerGroup`) and price-list rules (`PriceRules::CustomerGroupRule`) reference customer groups by prefixed ID, decoding to raw IDs on write via `normalize_id_preference`, and evaluate eligibility/applicability by intersecting the order/context user's group memberships with the rule's configured group IDs.
- **FR-007**: System MUST manage a customer's address book (billing/shipping default + full address list) via nested Admin API endpoints, and MUST prevent modifying/deleting an address still referenced by a completed order's bill/ship address.
- **FR-008**: System MUST expose a customer's saved credit cards read-only through the admin customer surface (list/show/destroy — no create/update, since cards originate from gateway tokenization).
- **FR-009**: System MUST support tagging customers and attaching an internal (rich-text) note, both bulk-editable (`bulk_add_tags`/`bulk_remove_tags`) and singly editable.
- **FR-010**: System MUST support searching customers by a combined email/first-name/last-name Ransack alias and filtering by marketing opt-in, tags, and date fields.
- **FR-011**: System MUST support metadata (JSON) and custom fields (metafields) on customer records (`concerns: :custom_fieldable` route concern).

### Key Entities *(include if feature involves data)*

- **Spree::LegacyUser** (the default `Spree.user_class` implementation): A storefront customer account — email, name, phone, marketing opt-in, addresses (`bill_address`/`ship_address` + address book via `Spree::UserAddress`), payment sources (`Spree::UserPaymentSource`: credit cards, payment setup sessions), orders, tags, metadata, internal note, and (as of this migration) plain-text password auth via `bcrypt` rather than Devise.
- **Spree::CustomerGroup**: A named, store-scoped segment (`belongs_to :store`) with many customers through `CustomerGroupUser`. Soft-deletable, prefixed ID `cg_...`. Provides bulk `add_customers`/`remove_customers` methods.
- **Spree::CustomerGroupUser**: The join model between a `CustomerGroup` and a polymorphic `user` (so it can point at whatever model `Spree.user_class` resolves to), unique per `(customer_group_id, user_id, user_type)`.
- **Spree::Promotion::Rules::CustomerGroup**: A `PromotionRule` subclass storing `preferred_customer_group_ids`; eligible only for orders whose user belongs to one of the configured groups (empty preference ⇒ ineligible).
- **Spree::PriceRules::CustomerGroupRule**: A `Spree::PriceRule` subclass storing `preferred_customer_group_ids` (existence-checked scoped to the rule's own store); applicable when the context user belongs to one of the configured groups (empty preference ⇒ applicable/unrestricted).

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::LegacyUser` (+ `Spree::UserMethods`, `Spree::UserAddress`, `Spree::UserPaymentSource` concerns), `Spree::CustomerGroup`, `Spree::CustomerGroupUser`, `Spree::Promotion::Rules::CustomerGroup`, `Spree::PriceRules::CustomerGroupRule` |
| `spree/api` (Store/Admin API v3) | Yes | Admin: `Spree::Api::V3::Admin::CustomersController` (+ nested `addresses`/`credit_cards`/`store_credits` controllers), `Spree::Api::V3::Admin::CustomerGroupsController`; Store: `Spree::Api::V3::Store::CustomersController` (`customers/me`); serializers `V3::CustomerSerializer`, `V3::Admin::CustomerSerializer`, `V3::Admin::CustomerGroupSerializer` |
| `packages/dashboard` (admin SPA) | Yes | `routes/.../customers/index.tsx`, `.../customers/$customerId.tsx`, `.../customers/groups.tsx`; `hooks/use-customers.ts`, `hooks/use-customer-groups.ts`; `schemas/customer.ts`, `schemas/customer-group.ts`; `tables/customers.tsx`, `tables/customer-groups.tsx`; promotion/price-list rule editors `components/spree/promotion-editors/rule-customer-group.tsx`, `components/spree/price-list-editors/rule-customer-group.tsx` (and `rule-customer.tsx`) |
| `packages/dashboard-ui` / `dashboard-core` | No | Uses existing primitives (`ResourceTable`, `ResourceMultiAutocomplete`, `AddressFormDialog`, `MetadataCard`, `TagCombobox`) — no new shared primitives added for this feature |
| `packages/sdk` / `packages/admin-sdk` | Yes | Generated types (`Customer`, `CustomerGroup`) and hand-written resource methods (`adminClient.customers.*`, `adminClient.customerGroups.*`, `adminClient.customers.bulkAddToGroups`/`bulkRemoveFromGroups`/`bulkAddTags`/`bulkRemoveTags`) |
| `docs/plans/` | Yes | See Migration Notes — `6.0-platform-auth.md` names the customer-facing user model as a `User→Customer` rename target |

### API Contract *(include if feature touches spree/api)*

- **Endpoints**:
  - `GET/POST /api/v3/admin/customers`, `GET/PATCH/DELETE /api/v3/admin/customers/:id`
  - `POST /api/v3/admin/customers/bulk_add_to_groups`, `POST .../bulk_remove_from_groups`, `POST .../bulk_add_tags`, `POST .../bulk_remove_tags`
  - `GET/POST/PATCH/DELETE /api/v3/admin/customers/:customer_id/addresses(/:id)`
  - `GET /api/v3/admin/customers/:customer_id/credit_cards(/:id)`, `DELETE .../credit_cards/:id`
  - `GET/POST/PATCH/DELETE /api/v3/admin/customers/:customer_id/store_credits(/:id)`
  - `GET/POST /api/v3/admin/customer_groups`, `GET/PATCH/DELETE /api/v3/admin/customer_groups/:id`
  - `POST /api/v3/customers` (store-facing create), `GET/PATCH /api/v3/store/customers/me`
- **Serializer fields (read)**: Store `CustomerSerializer` — `email, first_name, last_name, full_name, phone, accepts_email_marketing, available_store_credit_total, display_available_store_credit_total, default_billing_address, default_shipping_address, addresses`. Admin `CustomerSerializer` extends it with `login, metadata, last_sign_in_at, current_sign_in_at, sign_in_count, failed_attempts, last_sign_in_ip, current_sign_in_ip, tags, internal_note_html, default_billing_address_id, default_shipping_address_id, orders_count, total_spent, display_total_spent, last_order_completed_at, customer_group_ids, created_at, updated_at` plus expandable `addresses, orders, store_credits, customer_groups`. `Admin::CustomerGroupSerializer` — `name, description, customers_count, created_at, updated_at`, expandable `customers`.
- **Auth**: Admin endpoints use JWT + CanCanCan (`ResourceController`/`authorize!`/`authorize_resource!`) or secret-key scopes (`scoped_resource :customers`); Store API `customers/me` uses JWT (logged-in customer); `POST /api/v3/customers` (self-registration) uses the publishable key.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can create a customer without a password and the account is immediately usable (viewable/editable) in a single API round trip.
- **SC-002**: Bulk group assignment for N customers × M groups completes in a single request and is idempotent — repeating the same bulk-add request never creates duplicate membership rows.
- **SC-003**: 100% of promotion/price-list eligibility checks against a customer group compare raw `customer_group_id` values (never prefixed IDs), regardless of whether the rule was configured via the API with prefixed or raw IDs.
- **SC-004**: Customer list search-by-name-or-email and group/tag/date filters return correct results without requiring the admin to know which underlying column matched.

## Assumptions

- "Customers & Customer Groups" is treated as one feature area because groups exist purely to segment customers and have no independent value outside that relationship (`CustomerGroup` requires `store`, `Customer` requires no group).
- Payment sources (credit cards) and store credit are treated as supporting sub-panels of the customer profile for this spec, not independent features — deeper payment-source and store-credit lifecycle behavior is covered by other specs (e.g. `009-store-credits-and-gift-cards`).
- The promotion-rule and price-rule `CustomerGroup` integrations are included here (rather than in the promotions/price-list specs) because their entire behavior is "read customer group membership," which is this feature's data, not promotion/pricing logic.
- CSV export of customers is assumed to reuse the same generic `ExportsController` infrastructure documented for other resources (per `5.5-admin-spa-csv-export.md`) rather than a customer-specific export path — this was not independently re-verified against the exports controller source.

## Migration Notes

- **Pending rename**: `docs/plans/6.0-platform-auth.md` targets replacing `Spree::LegacyUser` (`Spree.user_class`) with a first-class `Spree::Customer` model (`has_secure_password`, prefix `cust_`, `Spree.user_class` → `Spree.customer_class` deprecation alias, `Spree::UserMethods` → `Spree::CustomerMethods`). As of this migration, **Customer is not a distinct model** — it is the existing `Spree::LegacyUser`/`Spree.user_class` default, addressed as "Customer" only at the API/serializer/dashboard naming layer (`CustomerSerializer`, `Admin::CustomersController`, `adminClient.customers`). The rename is model/table-configurable already (`Spree.user_class` can point at any model), so the API-level "Customer" naming used throughout this feature was already forward-compatible before the rename plan existed.
- **No dedicated `docs/plans/*.md` file governs Customer Groups specifically** — they appear only inside `6.0-platform-auth.md`'s broader auth/rename scope and are otherwise undocumented as an architectural plan; this spec reconstructs the contract from model/controller/serializer source directly.
- **Gap**: RSpec file paths were not individually enumerated during this migration — `spree/core/spec/models/spree/customer_group{,_user}_spec.rb` and `spree/api/spec/integration/**customer**` are assumed to exist per repo convention but were not verified line-by-line.
- **Gap**: The exact CSV export implementation (email delivery job, `ExportsController` wiring) referenced in `docs/user/customers/exporting-customers.mdx` was not read at the source level for this feature — it's assumed shared with other resources' export flow, not customer-specific, per `5.5-admin-spa-csv-export.md`.
- **Gap**: Storefront (non-admin, non-SPA) customer registration/self-service UI, if any exists outside `packages/dashboard` and the Store API, was not investigated.
- **Gap**: `Spree::AdminUserMethods`/`Spree::LegacyAdminUser` (the separate admin/staff user model referenced in `6.0-platform-auth.md`) is out of scope for this spec — this feature covers storefront customers only, not admin/staff accounts.
