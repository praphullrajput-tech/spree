# Feature Specification: Payment Methods

**Feature Branch**: `main` (fully shipped; 6.0 cleanup pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `5.6-6.0-single-store-promotions-payment-methods.md`, `5.5-6.0-display-on-to-boolean.md`

---

## User Scenarios & Testing

### User Story 1 — Configure Payment Methods for a Store (Priority: P1)

A merchant admin adds, edits, and removes payment methods for their store. Built-in methods: Check and Store Credit. External gateways (Stripe, PayPal, Braintree) register themselves as STI subclasses via `Spree.payment_methods`. Each method carries a serialized preferences JSON blob (API key, webhook secret, etc.) rendered via `preference_schema` for dynamic form generation.

**Why this priority**: Stores cannot accept payments without at least one active payment method. This is a foundational settings page.

**Independent Test**: Admin creates a "Check" payment method with `name: "Check Payment"`. It appears in the payment methods list with a prefixed ID (`pm_…`) and is available at checkout.

**Acceptance Scenarios**:

1. **Given** no payment methods, **When** admin creates a Check method, **Then** it appears with `pm_…` ID and is active
2. **Given** a payment method with `active: false`, **When** listed, **Then** it is excluded from checkout options
3. **Given** a gateway method, **When** admin fills in API keys via the dynamic preferences form, **Then** preferences are persisted as encrypted JSON
4. **Given** a payment method belonging to Store A, **When** Store B admin lists payment methods, **Then** Store A's method is not returned
5. **Given** a `display_on` value, **When** reading the API, **Then** `storefront_visible` boolean is returned (5.5 bridge; 6.0 column rename pending)

---

### User Story 2 — Reorder Payment Methods (Priority: P2)

Admin reorders payment methods via drag-and-drop. The `position` column (via `acts_as_list`) determines checkout display order.

**Why this priority**: Checkout UX depends on payment method ordering; preferred methods (card) should appear before secondary ones (bank transfer).

**Independent Test**: Admin drags "Stripe" above "Check" in the settings list. After reorder, `position` of Stripe is 1 and Check is 2. Checkout renders in the same order.

**Acceptance Scenarios**:

1. **Given** two payment methods, **When** admin drags the second above the first, **Then** positions are swapped
2. **Given** reordered methods, **When** checkout renders, **Then** methods appear in updated position order

---

### User Story 3 — List Available Gateway Types (Priority: P2)

Admin sees which gateway types are registered in `Spree.payment_methods` (the allowlist). Only registered STI types can be created.

**Acceptance Scenarios**:

1. **Given** a registered gateway type, **When** admin hits `GET /api/v3/admin/payment_methods/types`, **Then** it appears in the picker
2. **Given** an unregistered subclass, **When** admin tries to create it, **Then** 422 is returned

---

### Edge Cases

- What if a payment method is deleted mid-checkout? → Payment method FK on existing payments is nullable; existing payments reference the method by ID but it is soft-deleted
- What if preferences contain invalid gateway credentials? → Validation happens at gateway level during `authorize` — not at save time; stored and validated lazily
- What if two stores share a payment method? → Not possible since 5.6 migration; each method belongs to exactly one store via `store_id`

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::PaymentMethod` is an STI base; subclasses registered via `Spree.payment_methods` allowlist
- **FR-002**: Built-in types: `Spree::PaymentMethod::Check`, `Spree::PaymentMethod::StoreCredit`
- **FR-003**: Each method has a `preferences` JSON column + `preference_schema` attribute for dynamic form rendering
- **FR-004**: `acts_as_list` on `position` column; drag-to-reorder in Admin SPA → `PATCH /reposition`
- **FR-005**: `active` boolean controls checkout availability
- **FR-006**: `display_on` (legacy tri-state) bridged to `storefront_visible` boolean in 5.5; 6.0 renames column
- **FR-007**: `include Spree::SingleStoreResource` — belongs_to `:store`; 5.6 migration from multi-store join table; `spree_payment_methods_stores` join table survives in 5.6, dropped in 6.0
- **FR-008**: All IDs prefixed `pm_…`
- **FR-009**: `include Spree::Metafields` and `include Spree::Metadata`
- **FR-010**: Admin API: full CRUD + `GET /types` action

### Key Entities

- **PaymentMethod** (`Spree::PaymentMethod`): STI base. `name`, `active`, `position`, `display_on` (legacy), `preferences` JSON, `store_id`. Prefix: `pm_`.
- **Check** (`Spree::PaymentMethod::Check`): No preferences.
- **StoreCredit** (`Spree::PaymentMethod::StoreCredit`): No external credentials; redeems from user's store credit balance.

---

## Backend Requirements

### Data Model

- **Table**: `spree_payment_methods` — `type` (STI), `name`, `active`, `position`, `display_on`, `preferences text`, `store_id`, timestamps, `deleted_at`
- **Join table** (5.6 legacy): `spree_payment_methods_stores` — survives 5.6; dropped in 6.0

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/payment_methods` | List methods (store-scoped) |
| POST | `/api/v3/admin/payment_methods` | Create method |
| GET | `/api/v3/admin/payment_methods/:id` | Show method |
| PATCH | `/api/v3/admin/payment_methods/:id` | Update method |
| DELETE | `/api/v3/admin/payment_methods/:id` | Soft-delete method |
| GET | `/api/v3/admin/payment_methods/types` | List registered STI types |
| POST | `/api/v3/admin/payment_methods/:id/reposition` | Update position |

### Serializer Fields

**Admin PaymentMethodSerializer**:
- `id` (pm_…), `name`, `type`, `active`, `position`, `storefront_visible` (bridged from `display_on`), `preference_schema`, `store_id`, `created_at`, `updated_at`, `deleted_at`

### Authorization

- CanCanCan: `can :manage, Spree::PaymentMethod`
- Ransack allowlist: `name`, `active`, `type`, `position`, `created_at`

### i18n (Rails)

- Payment method type labels: `spree.payment_methods.*` per STI key

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/settings/payment-methods.tsx` — list with drag-to-reorder + create/edit Sheet; preferences form rendered dynamically from `preference_schema`

### Hooks

- `packages/dashboard/src/hooks/use-payment-methods.ts` — TanStack Query wrappers for CRUD + types + reposition

### Drag-and-Drop Ordering

- `acts_as_list` → drag-to-reorder; `verticalListSortingStrategy` + `PointerSensor` + `KeyboardSensor`
- On drag end: `POST /admin/payment_methods/:id/reposition { position: <new> }`
- Reference: same pattern as `settings/payment-methods.tsx` (mentioned in CLAUDE.md)

### i18n Keys

Under `admin.paymentMethods.*` in all locale files: page title, column headers, active badge, type labels, form labels, toast messages, empty state.

---

## Success Criteria

- **SC-001**: Admin can create a Check payment method; it appears at checkout
- **SC-002**: Reordering methods persists `position` and checkout reflects new order
- **SC-003**: Gateway credentials in `preferences` are persisted; `preference_schema` drives dynamic form
- **SC-004**: Store B cannot see or modify Store A's payment methods
- **SC-005**: _(6.0)_ `spree_payment_methods_stores` join table dropped; `store_id` column is `null: false`

---

## Assumptions

- External gateway STI subclasses (e.g., Stripe) are registered via extensions, not in core
- `preference_schema` is a computed attribute on the model describing field types for the SPA form renderer
- `display_on` tri-state is bridged via `storefront_visible` accessor until 6.0 column rename
