# Feature Specification: Tax Rates & Categories

**Feature Branch**: `main` (tax categories fully shipped; tax rates models-only; 6.0 TaxProvider replaces system)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `6.0-tax-provider.md`

---

## User Scenarios & Testing

### User Story 1 — Manage Tax Categories (Priority: P1)

An admin creates and manages tax categories (e.g., "Physical Goods", "Digital Goods", "Food"). Categories are assigned to products and variants to determine which tax rates apply.

**Why this priority**: Tax categories are the linking mechanism between products and tax rates; without them, tax cannot be applied at checkout.

**Independent Test**: Admin POSTs to `/api/v3/admin/tax_categories` with `{ name: "Physical Goods" }`. Response has `id: "taxcat_…"`. Category is available for assignment to products.

**Acceptance Scenarios**:

1. **Given** no tax categories, **When** admin creates "Physical Goods", **Then** it appears with `taxcat_…` ID
2. **Given** a tax category, **When** soft-deleted, **Then** associated products' `tax_category_id` is nullified (not deleted)
3. **Given** a default tax category, **When** a product has no explicit category, **Then** the default is used for tax calculation

---

### User Story 2 — Configure Tax Rates (Priority: P1)

An admin creates tax rates linking a tax category to a geographic zone with a percentage or calculator-based amount. Rates can be included in price (EU-style) or added on top (US-style).

**Why this priority**: Rates determine the actual tax amount applied at checkout; without rates, no tax is collected.

**Independent Test**: Admin creates a tax rate for "Physical Goods" in the "EU" zone at 20% included in price. When a EU customer buys a Physical Goods product, 20% VAT is shown as included in the price.

**Acceptance Scenarios**:

1. **Given** a tax rate with `included_in_price: true`, **When** checkout calculates tax, **Then** tax is extracted from the price (not added on top)
2. **Given** a tax rate with `included_in_price: false`, **When** checkout calculates tax, **Then** tax is added on top
3. **Given** a `default_tax: true` zone, **When** no zone matches the customer's address, **Then** the default zone's rates apply

---

### Edge Cases

- What if a tax rate has no zone? → Rate only applies when zone is null (matches all addresses); use with care
- What if a tax category is deleted with active products? → Products' `tax_category_id` nullified; tax no longer applied to those products
- _(6.0)_ `Spree::TaxRate` + `Spree::Zone` replaced by `Spree::TaxProvider` per-market; tax rates get direct country/state FKs; Zone model dropped

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::TaxCategory` prefix `taxcat_`; `acts_as_paranoid`; validates name uniqueness; `self.default` class method
- **FR-002**: `has_many :tax_rates` (dependent: :destroy); `has_many :products` (nullify on delete); `has_many :variants` (nullify on delete)
- **FR-003**: `Spree::TaxRate` prefix `tax_`; `acts_as_paranoid`; `include CalculatedAdjustments`; `include AdjustmentSource`; `include Metafields`; `include Metadata`
- **FR-004**: TaxRate: `amount`, `included_in_price`, `show_rate_in_label`; belongs_to zone (optional), tax_category; calculator association
- **FR-005**: TaxRate scopes: `by_zone`, `potential_rates_for_zone`, `for_default_zone`, `for_tax_category`, `included_in_price`
- **FR-006**: Tax categories Admin API: fully shipped (controller + serializer + SPA + E2E)
- **FR-007**: Tax rates Admin API: _(PENDING)_ no v3 admin controller, no serializer, no SPA
- **FR-008**: _(6.0)_ Zone model dropped; TaxRate gets direct country/state FKs; `Spree::TaxProvider` replaces per `6.0-tax-provider.md`

### Key Entities

- **TaxCategory** (`Spree::TaxCategory`): name, description, is_default. Prefix: `taxcat_`.
- **TaxRate** (`Spree::TaxRate`): name, amount, included_in_price, show_rate_in_label, zone_id, tax_category_id, calculator. Prefix: `tax_`.

---

## Backend Requirements

### API Surface

#### Admin API — Tax Categories (shipped)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/tax_categories` | List tax categories |
| POST | `/api/v3/admin/tax_categories` | Create category |
| GET | `/api/v3/admin/tax_categories/:id` | Show category |
| PATCH | `/api/v3/admin/tax_categories/:id` | Update category |
| DELETE | `/api/v3/admin/tax_categories/:id` | Soft-delete category |

#### Admin API — Tax Rates (PENDING)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/tax_rates` | List tax rates |
| POST | `/api/v3/admin/tax_rates` | Create rate |
| PATCH | `/api/v3/admin/tax_rates/:id` | Update rate |
| DELETE | `/api/v3/admin/tax_rates/:id` | Soft-delete rate |

### Serializer Fields

**Admin TaxCategorySerializer**:
- `id` (taxcat_…), `name`, `description`, `is_default`, `created_at`, `updated_at`, `deleted_at`

**Admin TaxRateSerializer** _(PENDING)_:
- `id` (tax_…), `name`, `amount`, `included_in_price`, `show_rate_in_label`, `zone_id` (zone_…), `tax_category_id` (taxcat_…), `calculator_type`, `calculator_preferences`, `created_at`, `updated_at`, `deleted_at`

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/settings/tax-categories.tsx` — fully shipped; list + create/edit
- _(PENDING)_ Tax rates SPA page

### E2E Coverage

- `packages/dashboard/e2e/tax-categories.spec.ts` — create/edit/delete tax categories

---

## Success Criteria

- **SC-001**: Admin can create tax categories and assign them to products
- **SC-002**: Tax rates with `included_in_price: true` extract tax from price at checkout
- **SC-003**: Default tax zone applies rates when no zone matches the customer's address
- **SC-004**: _(PENDING)_ Tax rates manageable via v3 Admin API and SPA
- **SC-005**: _(6.0)_ TaxProvider replaces TaxRate + Zone; rates get direct country/state FKs

---

## Assumptions

- Tax calculation is triggered by `TaxRate.adjust` called during order checkout
- `CalculatedAdjustments` on TaxRate means a Calculator determines the rate amount (most use FlatRate at `amount` percent)
- `included_in_price` is a per-rate setting; EU merchants typically set all rates to `included_in_price: true`
