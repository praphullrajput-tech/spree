# Feature Specification: Settings Pages (dashboard SPA)

**Feature Branch**: `037-settings-pages`

**Created**: 2026-08-24

**Status**: migrated

**Input**: User description: "Reverse-engineer spec-kit artifacts for the already-built admin SPA settings section under `packages/dashboard/src/routes/_authenticated/$storeId/settings/`"

## User Scenarios & Testing *(mandatory)*

Each settings page below is an already-shipped, independently-routable page under `/$storeId/settings/*` in `@spree/dashboard`. Priorities reflect how central each area is to running a store day-to-day, not build order (all are already built).

### User Story 1 - Store Details (Priority: P1)

An admin configures the store's name, default currency, supported locales, storefront access level, guest checkout, units (weight/length), and timezone.

**Why this priority**: Every store must have these configured before it can take orders; it's the landing page for `/settings` (index redirects here).

**Independent Test**: Navigate to `/$storeId/settings/store`, change the display timezone and default locale, save, and confirm the values persist on reload.

**Acceptance Scenarios**:

1. **Given** a store with no locale reconciliation issues, **When** the admin changes the store's default UI locale, **Then** `useSwitchAdminLocale`/`reconcileStoreDefaultLocale` updates the admin session locale to match.
2. **Given** invalid field values, **When** the admin submits the form, **Then** 422 errors map onto the corresponding fields via `mapSpreeErrorsToForm`.

**Route**: `routes/_authenticated/$storeId/settings/store.tsx`. **Hook**: `hooks/use-store-settings.ts` (`useStoreSettings`, `useUpdateStoreSettings`). **Schema**: `schemas/store.ts` (`storeSettingsFormSchema`, `STOREFRONT_ACCESS_LEVELS`, `UNIT_SYSTEMS`, `WEIGHT_UNITS`).

---

### User Story 2 - Staff (Users, Roles & Invitations) (Priority: P1)

An admin manages admin users: lists staff, invites new staff by email with a role, edits/deactivates existing staff, and manages roles.

**Why this priority**: Access control is foundational — a store can't safely operate without managing who has admin access.

**Independent Test**: Invite a staff member by email with a role, confirm the invitation appears in the pending list, then edit an existing staff member's role and confirm the change is reflected in the table.

**Acceptance Scenarios**:

1. **Given** a valid email and role, **When** the admin sends an invitation, **Then** the invitation appears with a relative-time indicator (`RelativeTime`) until accepted.
2. **Given** an existing staff member, **When** the admin edits their role via the sheet form, **Then** the table reflects the new role without a full page reload.

**Route**: `routes/_authenticated/$storeId/settings/staff.tsx`. **Hook**: `hooks/use-staff.ts`. Uses `AdminUser`, `Invitation`, `Role` types from `@spree/admin-sdk`.

---

### User Story 3 - Payment Methods (Priority: P1)

An admin enables/configures/reorders/disables payment methods (gateways) available at checkout, editing provider-specific preferences (API keys, display name, auto-capture, etc.).

**Why this priority**: A store cannot take payment without this being configured correctly.

**Independent Test**: Add a payment method, fill in its provider preferences via the generic `<PreferencesForm>`, save, and confirm it becomes visible/toggleable in the payment methods table.

**Acceptance Scenarios**:

1. **Given** a payment method provider with a declared `PreferenceField[]` schema, **When** the admin opens the create form, **Then** `defaultPreferences()` seeds sensible defaults (skipping `password`-type fields).
2. **Given** an existing ordering of payment methods, **When** the admin drags a row, **Then** `acts_as_list` position updates via drag-and-drop reorder (per project convention — no numeric position input).

**Route**: `routes/_authenticated/$storeId/settings/payment-methods.tsx`. **Hook**: `hooks/use-payment-methods.ts`. **Shared component**: `packages/dashboard-core/src/components/preferences-form.tsx`.

---

### User Story 4 - Markets (Priority: P2)

An admin creates/edits markets (groupings of countries/currencies/price lists for cross-border selling).

**Why this priority**: Needed for multi-region stores but not required for a single-region store to operate.

**Independent Test**: Create a market, assign it a set of countries via the market/country comboboxes, save, and confirm it lists in the markets table.

**Route**: `routes/_authenticated/$storeId/settings/markets.tsx`. **Hook**: `hooks/use-markets.ts`. **Shared components**: `packages/dashboard-core/src/components/market-combobox.tsx`, `country-combobox.tsx`.

---

### User Story 5 - Channels (Sales Channels) (Priority: P2)

An admin creates/manages sales channels (storefront, POS, marketplace, etc.) and their default status, per `docs/plans/6.0-channels-catalogs-b2b.md` / `6.0-order-routing.md`.

**Route**: `routes/_authenticated/$storeId/settings/channels.tsx`. **Hook**: `hooks/use-channels.ts`.

---

### User Story 6 - Stock Locations (Priority: P2)

An admin creates/edits warehouses/fulfillment locations, sets the default location, and manages location addresses.

**Route**: `routes/_authenticated/$storeId/settings/stock-locations.tsx`. **Hook**: `hooks/use-stock-locations.ts`.

---

### User Story 7 - Tax Categories (Priority: P2)

An admin creates/edits tax categories used to classify products for tax calculation.

**Route**: `routes/_authenticated/$storeId/settings/tax-categories.tsx`. **Hook**: `hooks/use-tax-categories.ts`.

---

### User Story 8 - Custom Field Definitions (Metafields) (Priority: P3)

An admin defines custom fields (metafield definitions) attachable to resources (products, variants, orders, etc.), per `docs/plans/5.4-6.0-custom-fields-rename.md`.

**Route**: `routes/_authenticated/$storeId/settings/custom-field-definitions.tsx`.

---

### User Story 9 - API Keys (Priority: P3)

An admin creates/revokes secret API keys with Shopify-style scopes for server-to-server integrations, per `docs/plans/5.5-admin-api-key-scopes.md`.

**Route**: `routes/_authenticated/$storeId/settings/api-keys.tsx`. **Hook**: `hooks/use-api-keys.ts`.

---

### User Story 10 - Webhooks (Priority: P3)

An admin creates/edits/deletes webhook endpoints subscribed to store events.

**Routes**: `routes/_authenticated/$storeId/settings/webhooks/index.tsx` (list/create) and `webhooks/$webhookEndpointId.tsx` (edit). **Hook**: `hooks/use-webhook-endpoints.ts`.

---

### User Story 11 - Allowed Origins (CORS) (Priority: P3)

An admin manages the list of allowed CORS origins for client-side Store API access (publishable-key clients).

**Route**: `routes/_authenticated/$storeId/settings/allowed-origins.tsx`. **Hook**: `hooks/use-allowed-origins.ts`.

---

### User Story 12 - Emails (Priority: P3)

An admin configures store branding/addresses used in transactional emails (logo, from-address, etc.).

**Route**: `routes/_authenticated/$storeId/settings/emails.tsx`.

---

### User Story 13 - Profile (Priority: P3)

The logged-in admin edits their own name, email, and password.

**Route**: `routes/_authenticated/$storeId/settings/profile.tsx`. **Hook**: `hooks/use-profile.ts`.

### Edge Cases

- What happens when a settings form's provider-specific `PreferenceField[]` schema includes a `password` field on edit — the server returns `null`/masked and the UI must not autofill or round-trip a fake value (`defaultPreferences()` explicitly skips `password` type).
- How does the Store Details page handle a store's default locale changing while other admins are mid-session (`reconcileStoreDefaultLocale`)?
- What happens when a 422 validation error targets a nested/non-field key — `mapSpreeErrorsToForm` routes it to `errors.root.message` as a banner rather than silently dropping it.
- Staff: what happens when an invitation is resent or a staff member's own role is edited (self-lockout risk)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The dashboard MUST redirect `/$storeId/settings` (index) to `/$storeId/settings/store`.
- **FR-002**: Each settings page MUST be independently routable via TanStack Router file-based routing under `/$storeId/settings/<page>`.
- **FR-003**: Each settings page MUST source all data through `@spree/admin-sdk` (Admin API) via a dedicated `use-<resource>.ts` hook — never call `adminClient` directly from route components.
- **FR-004**: Forms with provider-specific configurable preferences (payment methods, and any future preference-schema-driven resource) MUST render via the shared `<PreferencesForm>` component (`packages/dashboard-core/src/components/preferences-form.tsx`), driven by `PreferenceField[]` from `@spree/admin-sdk`.
- **FR-005**: 422 validation responses on any settings form MUST be mapped to field-level errors via `mapSpreeErrorsToForm`.
- **FR-006**: All user-visible strings on settings pages MUST go through i18next (`packages/dashboard/src/locales/en.json` and `packages/dashboard-core/src/locales/en.json`, all locales kept in sync).
- **FR-007**: Reorderable settings collections (e.g. payment methods, if list-ordered) MUST use drag-and-drop reorder, never a numeric position input, per project convention.

### Key Entities

- **Store**: name, currency, supported locales, storefront access level, guest checkout, timezone, unit system — edited on the Store Details page.
- **AdminUser / Invitation / Role**: staff accounts, pending invitations, and role definitions — edited on the Staff page.
- **PaymentMethod**: gateway configuration with provider-specific `preferences` hash validated by a `PreferenceField[]` schema.
- **Market**: named grouping of countries/currencies for cross-border selling.
- **Channel**: sales channel (storefront/POS/marketplace) with a default flag.
- **StockLocation**: warehouse/fulfillment location and its address.
- **TaxCategory**: classification used by tax calculation.
- **CustomFieldDefinition** (Metafield definition): schema for a custom field attachable to a resource type.
- **ApiKey**: secret key with scopes for server-to-server auth.
- **WebhookEndpoint**: URL + subscribed event list for outbound webhooks.
- **AllowedOrigin**: a CORS origin permitted for Store API publishable-key requests.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | No | Feature consumes existing Admin API; no core model changes in scope of this reverse-engineered spec |
| `spree/api` (Store/Admin API v3) | No (pre-existing) | Settings pages consume already-existing Admin API v3 endpoints for stores, users/invitations/roles, payment methods, markets, channels, stock locations, tax categories, custom field definitions, API keys, webhook endpoints, allowed origins |
| `packages/dashboard` (admin SPA) | Yes | 13 route files under `routes/_authenticated/$storeId/settings/` + matching `hooks/use-*.ts` + `schemas/*.ts` |
| `packages/dashboard-ui` / `dashboard-core` | Yes | Shared `<PreferencesForm>`, `<MarketCombobox>`, `<CountryCombobox>` in `dashboard-core/src/components/`; generic table/form primitives from `dashboard-ui` |
| `packages/sdk` / `packages/admin-sdk` | Yes (pre-existing, consumed) | `@spree/admin-sdk` provides `Store`, `AdminUser`, `Invitation`, `Role`, `WebhookEndpoint`, `WebhookEndpointCreateParams`, `PreferenceField` types consumed by these pages |
| `docs/plans/` | No new entry | Areas here are already covered by existing plans (`5.5-admin-api-key-scopes.md`, `5.4-6.0-custom-fields-rename.md`, `6.0-channels-catalogs-b2b.md`, etc.) |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 13 settings routes load and render without console errors against a seeded dev backend.
- **SC-002**: Every settings form round-trips a save (create/update) and reflects the server response without a full page reload.
- **SC-003**: 100% of user-visible strings on these pages resolve through i18next keys (no hardcoded English found in a grep audit of the route files).

## Assumptions

- This spec documents the settings section as it exists today (already built); it does not propose new pages.
- "Zones" (legacy `Spree::Zone`) has no SPA settings route because `docs/plans/6.0-tax-provider.md` and `6.0-delivery-rate-provider.md` are dropping the Zone model in favor of direct country/state FKs and `DeliveryZone` — no forward migration is needed for a route that's being retired.
- Legacy-admin-only areas (see Migration Notes) are out of scope for this spec; they represent gaps to close in future dashboard work, not defects in what's documented here.

## Migration Notes

Comparing `docs/user/settings/*.mdx` (end-user documentation) against the routes actually present under `packages/dashboard/src/routes/_authenticated/$storeId/settings/`:

| Doc page | SPA route? | Notes |
|---|---|---|
| `store-details.mdx` | Yes — `store.tsx` | |
| `users.mdx` | Yes — `staff.tsx` | |
| `payments.mdx` | Yes — `payment-methods.tsx` | |
| `markets.mdx` | Yes — `markets.tsx` | |
| `sales-channels.mdx` | Yes — `channels.tsx` | |
| `locations.mdx` | Yes — `stock-locations.tsx` | |
| `tax.mdx` | Yes — `tax-categories.tsx` (tax categories only) | |
| `metafields.mdx` | Yes — `custom-field-definitions.tsx` | |
| `emails.mdx` | Yes — `emails.tsx` | |
| `checkout.mdx` | **No** | Guest checkout toggle is folded into `store.tsx` (`STOREFRONT_ACCESS_LEVELS`); no dedicated checkout messaging/settings page in the SPA — **legacy-admin-only gap** |
| `shipping-methods.mdx` | **No** | No `shipping-methods` or `shipping-categories` route under settings — **legacy-admin-only gap** (tracked by `docs/plans/6.0-fulfillment-and-delivery.md` / `6.0-delivery-rate-provider.md`) |
| `zones.mdx` | **No** | No `zones` route — Zone model is being dropped per `6.0-tax-provider.md`/`6.0-delivery-rate-provider.md`; not a gap so much as a deliberate non-port |
| `policies.mdx` | **No** | No `policies` route (store policies / legal pages) — **legacy-admin-only gap** |
| `returns-configuration.mdx` | **No** | No route for RMA reasons/reimbursement types — **legacy-admin-only gap**, likely folds into `docs/plans/6.0-returns-exchanges-claims.md` when that ships |
| `marketplace.mdx` | **No** | No marketplace/vendor settings route — **legacy-admin-only gap**, related to `docs/plans/6.0-inventory-operations.md` (`Spree::Vendor`) |

No SPA-only pages were found without end-user documentation (webhooks, API keys, and allowed-origins are developer/integration-facing and are documented elsewhere, not in `docs/user/settings/`).
