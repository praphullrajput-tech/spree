# Feature Specification: Store Configuration

**Feature Branch**: `main` (fully shipped)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `6.0-channels-catalogs-b2b.md`

---

## User Scenarios & Testing

### User Story 1 — Configure Store Settings (Priority: P1)

An admin configures the store's name, URL, locale, timezone, currency, email addresses, and unit preferences. These settings affect how the storefront behaves and how emails are sent.

**Why this priority**: Store settings are required before the store can operate; incorrect settings cause broken emails, wrong currency display, and locale issues.

**Independent Test**: Admin PATCHes `/api/v3/admin/store` with `{ name: "My Shop", mail_from_address: "no-reply@myshop.com" }`. Response reflects updated values.

**Acceptance Scenarios**:

1. **Given** a store, **When** admin updates the name and timezone, **Then** both are persisted and returned
2. **Given** a store with multiple currencies configured, **When** customer visits, **Then** they can switch between supported currencies
3. **Given** a store's email settings, **When** an order confirmation is sent, **Then** it uses `mail_from_address`
4. **Given** a store's `weight_unit` preference, **When** variant weights are displayed, **Then** they use the configured unit

---

### User Story 2 — Configure Store Markets (Priority: P2)

Admin configures which countries and currencies the store supports. Markets determine pricing and shipping availability.

**Acceptance Scenarios**:

1. **Given** a store with USD and EUR markets, **When** customer visits from Germany, **Then** EUR pricing is shown
2. **Given** a market configuration, **When** admin adds a new currency, **Then** prices in that currency are required on products

---

### Edge Cases

- There is only one store per admin session; no `POST /stores` in admin API — store is pre-created
- What if `mail_from_address` is invalid? → Validated by model; 422 returned
- Store soft-delete (`acts_as_paranoid`) is for data integrity; it should never be used in normal admin operation

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::Store` prefix `store_`; `acts_as_paranoid`; `friendly_id` for slug-based URL
- **FR-002**: Concerns: `TranslatableResource`, `Metafields`, `Metadata`, `Stores::Setup`, `Stores::Markets`, `Stores::Channels`, `UserManagement`, `OrderRouting::HasStrategyPreference`
- **FR-003**: Key preferences: `admin_locale`, `default_locale`, `supported_currencies`, `default_currency`, `timezone`, `weight_unit`, `unit_system`
- **FR-004**: Email settings: `mail_from_address`, `customer_support_email`
- **FR-005**: Admin API: `show` + `update` only (no create/delete from admin)
- **FR-006**: Single-store per session; `current_store` from `Spree::Current.store`
- **FR-007**: `Stores::Markets` concern — configures supported currencies and default currency
- **FR-008**: `Stores::Channels` concern — channel association (see `6.0-channels-catalogs-b2b.md`)

### Key Entities

- **Store** (`Spree::Store`): name, url, code, default, mail_from_address, customer_support_email, default_currency, supported_currencies, default_locale, supported_locales, timezone, weight_unit, unit_system. Prefix: `store_`.

---

## Backend Requirements

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/store` | Show current store settings |
| PATCH | `/api/v3/admin/store` | Update store settings |

### Serializer Fields

**Admin StoreSerializer**:
- `id` (store_…), `name`, `url`, `code`, `default`, `mail_from_address`, `customer_support_email`, `default_currency`, `supported_currencies`, `default_locale`, `supported_locales`, `timezone`, `weight_unit`, `unit_system`, `admin_locale`, `meta_title`, `meta_description`, `seo_robots`, `facebook`, `twitter`, `instagram`, `created_at`, `updated_at`

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/settings/store.tsx` — store settings form: name, URL, email, locale, timezone, currency, units

### i18n Keys

Under `admin.store.*` in all locale files.

---

## E2E Coverage

- `packages/dashboard/e2e/store-settings.spec.ts` — update store name → verify persisted; update timezone → verify reflected in datetime displays

---

## Success Criteria

- **SC-001**: Admin can update all store preferences; changes take effect on next request
- **SC-002**: `mail_from_address` validation prevents invalid email configuration
- **SC-003**: Supported currencies and locales are configurable from the settings page

---

## Assumptions

- Only one store is accessible per admin session; multi-store is an extension (`spree_multi_store`)
- `friendly_id` slug is used for the store's admin URL; not the same as the storefront URL
- Store preferences are stored in a serialized `preferences` column plus dedicated columns for commonly-accessed values
