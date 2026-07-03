# Feature Specification: Shipping Methods & Zones

**Feature Branch**: `main` (models + legacy admin shipped; v3 API + SPA PENDING)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `6.0-fulfillment-and-delivery.md`, `6.0-tax-provider.md` (Zone model drop pending)

---

## User Scenarios & Testing

### User Story 1 — Configure Shipping Methods (Priority: P1)

A merchant admin creates and manages shipping methods — setting the name, calculator (flat rate, per item, etc.), associated zones, and shipping categories. Active methods with matching zones appear at checkout as rate options.

**Why this priority**: Stores cannot offer shipping without at least one active method; this is a foundational settings page blocking checkout.

**Independent Test**: Admin creates a "Standard Shipping" method with a Flat Rate calculator ($5.00), assigned to the "Domestic" zone. When a customer in that zone checks out, "Standard Shipping — $5.00" appears as an option.

**Acceptance Scenarios**:

1. **Given** no shipping methods, **When** admin creates a flat-rate method in the domestic zone, **Then** it appears at checkout for domestic addresses
2. **Given** a shipping method with `active: false`, **When** listed at checkout, **Then** it is excluded
3. **Given** a method with no matching zone for the customer's address, **When** rates are fetched, **Then** the method does not appear
4. **Given** a method assigned to a shipping category, **When** a cart contains only items without that category, **Then** the method is excluded

---

### User Story 2 — Manage Shipping Zones (Priority: P1)

Admin creates geographic zones (countries, states, or combinations) that control where each shipping method is available.

**Why this priority**: Zones are the geographic targeting layer; without zone management, merchants cannot restrict or target shipping methods by geography.

**Independent Test**: Admin creates a "Europe" zone with France, Germany, and Spain as members. Assigns a "EU Express" shipping method to the Europe zone. Customers with EU addresses see that method at checkout; US customers do not.

**Acceptance Scenarios**:

1. **Given** a zone with country members, **When** a customer address matches one of those countries, **Then** methods in that zone are offered
2. **Given** a zone with state members, **When** a customer address matches one of those states, **Then** methods in that zone are offered
3. **Given** a zone marked as `default_tax`, **When** no other zone matches a customer's address for tax purposes, **Then** this zone's tax rules apply
4. **Given** two zones, **When** admin assigns a shipping method to both, **Then** the method appears for customers in either zone

---

### User Story 3 — Configure Shipping Calculators (Priority: P1)

Admin selects and configures a calculator for each shipping method. Available calculators: FlatRate, PerItem, FlatPercentItemTotal, FlexiRate, PriceSack, DigitalDelivery.

**Acceptance Scenarios**:

1. **Given** a flat-rate calculator configured at $5.00, **When** any order ships via this method, **Then** the shipping cost is $5.00
2. **Given** a per-item calculator at $1.50/item, **When** a cart has 3 items, **Then** shipping cost is $4.50
3. **Given** a digital-delivery calculator, **When** all items in a cart are digital, **Then** shipping cost is $0.00

---

### Edge Cases

- What if a zone has no members? → Empty zone never matches; shipping methods in it never appear at checkout
- What if a shipping method has no zone? → Method never appears at checkout (zone membership is required)
- What if a shipping method is soft-deleted mid-checkout? → Existing shipments reference the method by ID; soft-delete hides it from new checkouts only
- _(6.0)_ `Spree::ShippingMethod` will be renamed `Spree::DeliveryMethod`; `Spree::Zone` will become `Spree::DeliveryZone` per `6.0-fulfillment-and-delivery.md`

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::ShippingMethod` is a paranoid (soft-delete) model; prefix `dm_` (already anticipates 6.0 DeliveryMethod rename)
- **FR-002**: `CalculatedAdjustments` concern — each method has a `calculator` association for pricing
- **FR-003**: Built-in calculators: FlatRate, PerItem, FlatPercentItemTotal, FlexiRate, PriceSack, DigitalDelivery
- **FR-004**: Methods belong to many zones via `spree_shipping_method_zones` join table
- **FR-005**: Methods belong to many shipping categories via `spree_shipping_method_categories` join table
- **FR-006**: `display_on` (legacy tri-state) — controls storefront vs admin visibility; bridged to `storefront_visible` boolean in 5.5
- **FR-007**: `Spree::Zone` groups countries/states via polymorphic `Spree::ZoneMember`; `default_tax` boolean; prefix `zone_`
- **FR-008**: `Spree::ShippingRate` stores denormalized cost on `Spree::Shipment`; prefix `dr_` (anticipates 6.0 DeliveryRate rename)
- **FR-009**: `Spree::ShippingCategory` groups line items for method eligibility; prefix `scat_`; dropped in 6.0
- **FR-010**: _(PENDING)_ Admin v3 API for shipping methods, zones, and zone members
- **FR-011**: _(PENDING)_ Admin SPA settings page for shipping methods and zones
- **FR-012**: _(6.0)_ ShippingMethod → DeliveryMethod; Zone → DeliveryZone; ShippingRate → DeliveryRate; ShippingCategory dropped per `6.0-fulfillment-and-delivery.md`
- **FR-013**: _(6.0)_ Zone model dropped per `6.0-tax-provider.md` (tax rules get direct country/state FKs); delivery zones become `Spree::DeliveryZone` in `6.0-delivery-rate-provider.md`

### Key Entities

- **ShippingMethod** (`Spree::ShippingMethod`): `name`, `active`, `display_on`, calculator, zones, shipping categories, `tax_category_id`. Prefix: `dm_`.
- **Zone** (`Spree::Zone`): `name`, `default_tax`, kind (country/state). Prefix: `zone_`.
- **ZoneMember** (`Spree::ZoneMember`): polymorphic join (Country or State). Prefix: none.
- **ShippingRate** (`Spree::ShippingRate`): denormalized cost on shipment. Prefix: `dr_`.
- **ShippingCategory** (`Spree::ShippingCategory`): eligibility grouping. Prefix: `scat_`.

---

## Backend Requirements

### Data Model

- **Table**: `spree_shipping_methods` — `name`, `admin_name`, `display_on`, `code`, `tracking_url`, `deleted_at`, timestamps
- **Table**: `spree_zones` — `name`, `description`, `default_tax`, `zone_members_count`, `kind`, timestamps
- **Table**: `spree_zone_members` — `zone_id`, `zoneable_type`, `zoneable_id`, timestamps
- **Table**: `spree_shipping_method_zones` — `shipping_method_id`, `zone_id`
- **Table**: `spree_shipping_categories` — `name`, timestamps
- **Table**: `spree_shipping_method_categories` — `shipping_method_id`, `shipping_category_id`
- **Table**: `spree_shipping_rates` — `shipment_id`, `shipping_method_id`, `selected`, `cost`, `tax_rate_id`, timestamps

### API Surface (PENDING)

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/shipping_methods` | List shipping methods |
| POST | `/api/v3/admin/shipping_methods` | Create method |
| GET | `/api/v3/admin/shipping_methods/:id` | Show method |
| PATCH | `/api/v3/admin/shipping_methods/:id` | Update method |
| DELETE | `/api/v3/admin/shipping_methods/:id` | Soft-delete method |
| GET | `/api/v3/admin/zones` | List zones |
| POST | `/api/v3/admin/zones` | Create zone |
| GET | `/api/v3/admin/zones/:id` | Show zone |
| PATCH | `/api/v3/admin/zones/:id` | Update zone + members |
| DELETE | `/api/v3/admin/zones/:id` | Delete zone |

### Serializer Fields (PENDING)

**Admin ShippingMethodSerializer**:
- `id` (dm_…), `name`, `admin_name`, `active` (bridged from display_on), `code`, `tracking_url`, `calculator_type`, `calculator_preferences`, `zone_ids`, `shipping_category_ids`, `created_at`, `updated_at`, `deleted_at`

**Admin ZoneSerializer**:
- `id` (zone_…), `name`, `description`, `default_tax`, `kind`, `members` (embedded array of `{ id, type, name }`), `created_at`, `updated_at`

### Authorization

- CanCanCan: `can :manage, Spree::ShippingMethod` and `can :manage, Spree::Zone`
- Store-scoped via `current_store`

---

## Frontend Requirements

### SPA Routes (PENDING)

- `packages/dashboard/src/routes/_authenticated/$storeId/settings/shipping-methods.tsx` — list + create/edit Sheet; zone + category multi-select; calculator type + preferences form
- `packages/dashboard/src/routes/_authenticated/$storeId/settings/zones.tsx` — list + create/edit Sheet; country/state member picker

### Hooks (PENDING)

- `packages/dashboard/src/hooks/use-shipping-methods.ts`
- `packages/dashboard/src/hooks/use-zones.ts`

### i18n Keys (PENDING)

Under `admin.shippingMethods.*` and `admin.zones.*` in all locale files.

---

## Success Criteria

- **SC-001**: Admin can create a flat-rate shipping method in a zone; it appears at checkout for matching addresses
- **SC-002**: Deactivating a shipping method removes it from checkout immediately
- **SC-003**: Zone members (countries/states) control geographic availability
- **SC-004**: _(PENDING)_ Admin v3 API fully replaces legacy Rails admin for shipping method + zone management
- **SC-005**: _(6.0)_ ShippingMethod renamed to DeliveryMethod; Zone to DeliveryZone per `6.0-fulfillment-and-delivery.md`

---

## Assumptions

- `display_on` tri-state (`front_end`/`back_end`/`both`) is bridged to `storefront_visible` boolean via 5.5 bridge
- `ShippingCategory` is dropped in 6.0 per `6.0-fulfillment-and-delivery.md`; new delivery providers handle eligibility differently
- Calculator preferences are stored as serialized text; schema is defined per calculator subclass
- The prefix `dm_` on `ShippingMethod` anticipates the 6.0 rename to `DeliveryMethod` (already set in the model)
