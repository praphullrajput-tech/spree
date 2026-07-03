# Feature Specification: Gift Cards & Batches

**Feature Branch**: `main` (fully implemented)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: N/A (no dedicated plan doc; feature fully shipped)

---

## User Scenarios & Testing

### User Story 1 — Manage Gift Cards (Priority: P1)

An admin issues gift cards individually or in bulk via batches. Each gift card has a monetary value, an optional expiry date, and a unique code. Customers redeem gift cards at checkout as a payment method. The admin can cancel active gift cards or view redemption history.

**Why this priority**: Gift cards are a high-value revenue and customer-retention tool; individual management is the baseline workflow.

**Independent Test**: Admin creates a gift card with `amount: 50.00`, `currency: "USD"`. The card is in `active` state with a unique code. Customer applies it at checkout via `POST /api/v3/cart/apply_gift_card { gift_card_code: "..." }`. Cart reflects the balance used.

**Acceptance Scenarios**:

1. **Given** no gift cards, **When** admin creates one with `amount: 50.00`, **Then** it appears with `state: "active"` and a unique code with prefixed ID (`gc_…`)
2. **Given** an active gift card with `amount: 50.00`, **When** customer uses $30 of it, **Then** `amount_used: 30.00`, state transitions to `partially_redeemed`
3. **Given** a partially-redeemed card where remaining balance = 0, **When** customer uses remaining balance, **Then** state transitions to `redeemed`
4. **Given** an active gift card, **When** admin cancels it, **Then** state transitions to `canceled` and it cannot be applied at checkout
5. **Given** a gift card with `expires_at` in the past, **When** customer attempts to apply it, **Then** 422 "Gift card has expired"

---

### User Story 2 — Bulk Issue via Batches (Priority: P1)

An admin creates a `GiftCardBatch` specifying a count, amount, prefix, and optional expiry. The system auto-generates all cards with unique prefixed codes (e.g., `HOLIDAY-ABC123`). Batch records track the issuing admin and creation context.

**Why this priority**: Promotions and corporate gifting require issuing hundreds of cards at once; individual creation does not scale.

**Independent Test**: Admin creates a batch with `prefix: "HOLIDAY"`, `codes_count: 50`, `amount: 25.00`. After creation, `GET /admin/gift_card_batches/:id/gift_cards` returns 50 gift cards, each with a code starting with `HOLIDAY-`.

**Acceptance Scenarios**:

1. **Given** a batch with `codes_count: 50`, **When** saved, **Then** 50 `GiftCard` records are generated via `after_create :generate_gift_cards`
2. **Given** a batch, **When** listing its gift cards, **Then** each code matches the batch prefix
3. **Given** `codes_count > Spree::Config[:gift_card_batch_limit]`, **When** submitted, **Then** 422 validation error
4. **Given** a batch created by an admin, **When** viewing the batch, **Then** `created_by_id` references the admin user

---

### User Story 3 — Storefront Redemption (Priority: P1)

A customer applies a gift card code at checkout. If the card's remaining balance covers the order total, the payment is satisfied in full. If partial, the remainder must be paid via another method. The cart shows the gift card amount as a payment contribution.

**Why this priority**: Gift card payment at checkout is the end-user payoff of the entire feature.

**Independent Test**: Cart with `total: 30.00`, gift card balance `50.00`. `POST /api/v3/cart/apply_gift_card` returns updated cart with `gift_card_total: 30.00` and `outstanding_balance: 0.00`.

**Acceptance Scenarios**:

1. **Given** a cart total of $30 and a gift card with $50 balance, **When** applied, **Then** order is fully covered and no additional payment is required
2. **Given** a cart total of $60 and a gift card with $50 balance, **When** applied, **Then** `outstanding_balance: 10.00` requires another payment method
3. **Given** a gift card already applied to a cart, **When** the order is placed, **Then** `amount_used` is incremented; `amount_authorized` is decremented
4. **Given** a canceled or fully-redeemed gift card, **When** applied to cart, **Then** 422 with state-specific reason

---

### Edge Cases

- What if two customers try to apply the same gift card simultaneously? → `amount_authorized` tracks concurrent holds; the second application returns insufficient balance
- What if a gift card's currency differs from the cart's currency? → Validation rejects; gift cards are currency-scoped
- What if a batch prefix collides with an existing code? → Unique code generation retries; if exhausted, creation fails with a descriptive error
- What if a partially-redeemed gift card's remaining balance is zero? → State machine transitions to `redeemed` via `partial_redeem` event logic in the model

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::GiftCard` has a state machine: `active → partially_redeemed → redeemed`; `active → canceled`
- **FR-002**: `amount_used` tracks total redemptions; `amount_authorized` tracks concurrent in-checkout holds
- **FR-003**: `Spree::GiftCardBatch` generates `codes_count` unique `GiftCard` records via `after_create`; enforces a configurable batch limit via `Spree::Config[:gift_card_batch_limit]`
- **FR-004**: Gift cards are scoped to a single store via `SingleStoreResource` concern
- **FR-005**: Currency-scoped: gift card currency must match cart currency
- **FR-006**: Admin API: full CRUD for gift cards and batches; nested cards under batch; apply/remove on orders
- **FR-007**: Store API: apply gift card to cart; remove gift card from cart
- **FR-008**: All gift card IDs prefixed `gc_…`; all batch IDs prefixed `gcb_…`
- **FR-009**: Gift cards on orders are accessible via `GET /admin/orders/:id/gift_cards`

### Key Entities

- **GiftCard** (`Spree::GiftCard`): `code`, `amount`, `currency`, `amount_used`, `amount_authorized`, `state` (active/partially_redeemed/redeemed/canceled), `expires_at`, `store_id`, `batch_id` (optional). Prefix: `gc_`.
- **GiftCardBatch** (`Spree::GiftCardBatch`): `prefix`, `codes_count`, `amount`, `currency`, `expires_at`, `store_id`, `created_by_id`. Prefix: `gcb_`. Has `many :gift_cards`.

---

## Backend Requirements

### Data Model

- **Tables**: `spree_gift_cards`, `spree_gift_card_batches`
- **State column**: `state` string (state_machines-activerecord; legacy column name `state`)
- **Money methods**: `amount`, `amount_used`, `amount_authorized` exposed via `DisplayMoney`
- **SingleStoreResource**: `store_id` FK, `ensure_store` before_validation, `for_store` scope

### API Surface

#### Store API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v3/cart/apply_gift_card` | Apply gift card code to cart |
| DELETE | `/api/v3/cart/remove_gift_card` | Remove gift card from cart |

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/gift_cards` | List gift cards (store-scoped) |
| POST | `/api/v3/admin/gift_cards` | Create gift card |
| GET | `/api/v3/admin/gift_cards/:id` | Show gift card |
| PATCH | `/api/v3/admin/gift_cards/:id` | Update gift card |
| DELETE | `/api/v3/admin/gift_cards/:id` | Delete gift card |
| POST | `/api/v3/admin/gift_cards/:id/cancel` | Cancel gift card |
| GET | `/api/v3/admin/gift_card_batches` | List batches |
| POST | `/api/v3/admin/gift_card_batches` | Create batch (auto-generates cards) |
| GET | `/api/v3/admin/gift_card_batches/:id` | Show batch |
| DELETE | `/api/v3/admin/gift_card_batches/:id` | Delete batch and its cards |
| GET | `/api/v3/admin/orders/:id/gift_cards` | List gift cards applied to an order |

### Serializer Fields

**Admin GiftCardSerializer**:
- `id` (gc_…), `code`, `amount`, `amount_used`, `amount_authorized`, `currency`, `state`, `expires_at`, `store_id`, `batch_id` (gcb_…), `created_at`, `updated_at`

**Admin GiftCardBatchSerializer**:
- `id` (gcb_…), `prefix`, `codes_count`, `amount`, `currency`, `expires_at`, `store_id`, `created_by_id`, `created_at`, `updated_at`

### Authorization

- CanCanCan: `can :manage, Spree::GiftCard` for admin; store-scoped via `SingleStoreResource`
- Ransack allowlist: `code`, `state`, `store_id`, `expires_at`, `batch_id`

### i18n (Rails)

- Keys under `spree.gift_card.*` and `spree.gift_card_batch.*`

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/promotions/gift-cards.tsx` — list gift cards and batches

### Hooks

- `packages/dashboard/src/hooks/use-gift-cards.ts` — TanStack Query wrappers for gift card and batch CRUD

### i18n Keys

Under `admin.giftCards.*` in all 6 locale files: page title, column headers (code, amount, state, expires_at), state labels, batch labels, form labels, toast messages, empty state.

---

## Success Criteria

- **SC-001**: Admin can create a gift card and a customer can apply it at checkout; cart reflects the deducted amount
- **SC-002**: GiftCardBatch generates the specified number of unique-code cards on creation
- **SC-003**: State machine transitions correctly: active → partially_redeemed → redeemed; active → canceled
- **SC-004**: Gift cards are currency-scoped; cross-currency application returns 422
- **SC-005**: Batch limit (`Spree::Config[:gift_card_batch_limit]`) is enforced on `codes_count`

---

## Assumptions

- `state` column is named `state` (not `status`) — this model predates the `6.0-normalize-state-to-status.md` plan; rename is pending in 6.0
- `amount_authorized` tracks concurrent in-checkout holds and is decremented on order completion or cart abandonment
- Gift cards are managed under the Promotions section of the admin SPA (same nav group as promotions)
