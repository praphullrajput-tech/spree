# Feature Specification: Custom Field Definitions

**Feature Branch**: `main` (5.4 API bridge ✅; 5.5 aliases + Admin CRUD ✅; 6.0 rename pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: `docs/plans/5.5-6.0-custom-fields-rename.md`

---

## User Scenarios & Testing

### User Story 1 — Manage Custom Field Definitions (Priority: P1)

An admin operator creates custom field definitions to extend any resource type (Product, Order, Customer, etc.) with typed, validated fields. They set the field's label, type (short_text, long_text, rich_text, number, boolean, json), namespace, key, and whether it appears in the storefront.

**Why this priority**: Custom field definitions are the schema layer. Without them, custom fields cannot be created on any resource.

**Independent Test**: Admin navigates to Settings → Custom Field Definitions, creates a definition with `label: "Material"`, `field_type: "short_text"`, `resource_type: "Spree::Product"`, `storefront_visible: true`. It appears in the list and the API returns it with a prefixed ID (`cfdef_…`).

**Acceptance Scenarios**:

1. **Given** no custom field definitions exist, **When** admin creates one with `label: "Material"` and `field_type: "short_text"`, **Then** it appears in the list with `field_type: "short_text"` (token, not Ruby class name) and a prefixed ID
2. **Given** a custom field definition, **When** admin sets `storefront_visible: false`, **Then** custom fields using this definition are excluded from Store API responses
3. **Given** a definition, **When** admin filters by `resource_type: "Spree::Product"`, **Then** only product definitions are returned
4. **Given** a 422 response, **When** `label` is blank, **Then** field-level error appears inline
5. **Given** a definition in use by existing custom field values, **When** admin deletes it, **Then** the definition and its child custom field values are destroyed

---

### User Story 2 — Assign Custom Field Values to Resources (Priority: P1)

An admin operator sets custom field values on individual resources (e.g., setting `material: "wool"` on a specific product). Values are typed and validated by the definition's `field_type`. Values are nested on the resource and returned via `expand=custom_fields` on the parent resource.

**Why this priority**: Definitions without values have no practical effect. Value CRUD is the user-facing payoff.

**Independent Test**: Admin opens a product, expands the Custom Fields panel, sets the "Material" field to "wool". `GET /api/v3/products/:id?expand=custom_fields` returns `custom_fields: [{ key: "product.material", label: "Material", field_type: "short_text", value: "wool" }]`.

**Acceptance Scenarios**:

1. **Given** a product and a `short_text` definition, **When** admin sets value `"wool"`, **Then** `POST /admin/products/:id/custom_fields` returns the custom field with `value: "wool"`
2. **Given** a `number` definition, **When** admin sets value `"abc"`, **Then** a 422 is returned with a type validation error
3. **Given** a custom field, **When** admin updates its value, **Then** `PATCH /admin/products/:id/custom_fields/:id` updates and returns the new value
4. **Given** `storefront_visible: false` on the definition, **When** `GET /api/v3/products/:id?expand=custom_fields` is called by a storefront, **Then** the field is excluded from the response

---

### User Story 3 — Storefront Consumes Custom Fields (Priority: P2)

A storefront developer reads custom field values on products, variants, and categories via `expand=custom_fields`. Each field value includes the semantic `field_type` token (not a Ruby class name), `key`, `label`, and `value`.

**Why this priority**: Pure read path. The API rename (5.4) from `metafields` to `custom_fields` was a breaking change for storefront consumers.

**Independent Test**: `GET /api/v3/products/:id?expand=custom_fields` returns `"custom_fields"` array (not `"metafields"`) with `field_type: "short_text"` (token) on each item.

**Acceptance Scenarios**:

1. **Given** a product with custom fields, **When** `GET /api/v3/products/:id?expand=custom_fields` is called, **Then** response key is `"custom_fields"` (not `"metafields"`)
2. **Given** a custom field with `field_type: "short_text"`, **When** the Store API returns it, **Then** `field_type` is `"short_text"` (token), not `"Spree::Metafields::ShortText"` (class string)
3. **Given** a custom field with `storefront_visible: false`, **When** the Store API is called, **Then** that field is absent from the response

---

### Edge Cases

- What if two definitions share the same `namespace`/`key` for the same resource type? → Uniqueness enforced at DB level
- What if a plugin registers a custom field type outside the standard set? → `field_type=` setter falls through to the raw value for unknown tokens (backward compat for plugin types)
- What if `field_type` is changed on an existing definition? → Existing values may become invalid; no automatic data conversion
- _(6.0 pending)_ What if `display_on` column is renamed to `storefront_visible`? → Boolean replaces enum; data migration maps `back_end → false`, others `→ true`

---

## Requirements

### Functional Requirements

- **FR-001**: `Spree::CustomFieldDefinition` is a constant alias of `Spree::MetafieldDefinition` in 5.5; full rename in 6.0
- **FR-002**: `field_type` must expose a token vocabulary (`short_text`, `long_text`, `rich_text`, `number`, `boolean`, `json`) — not raw Ruby class names
- **FR-003**: `storefront_visible` boolean accessor bridges `display_on` column in 5.5; becomes a real column in 6.0
- **FR-004**: Custom field definitions are filtered by `resource_type` on the list endpoint
- **FR-005**: Custom field values are nested under parent resources (products, orders, customers, categories, option types, variants)
- **FR-006**: Admin API: `POST /admin/products/:id/custom_fields` creates a value; `PATCH` updates; `DELETE` removes
- **FR-007**: Store API: `expand=custom_fields` returns storefront-visible values (not `expand=metafields`)
- **FR-008**: All definition IDs prefixed `cfdef_…`; all value IDs prefixed `cf_…`
- **FR-009**: Custom field values validated by their type's STI subclass logic (`Spree::Metafields::Number`, etc.)
- **FR-010**: 6 standard field types ship in core: `short_text`, `long_text`, `rich_text`, `number`, `boolean`, `json`
- **FR-011**: _(6.0 pending)_ Table renames: `spree_metafields` → `spree_custom_fields`, `spree_metafield_definitions` → `spree_custom_field_definitions`
- **FR-012**: _(6.0 pending)_ `display_on` string column → `storefront_visible` boolean column

### Key Entities

- **CustomFieldDefinition** (`Spree::MetafieldDefinition` aliased as `Spree::CustomFieldDefinition`): Schema for a typed field on a resource type. Attributes: `label` (alias for `name`), `field_type` (alias for `metafield_type`, token vocabulary), `namespace`, `key`, `resource_type`, `storefront_visible` (accessor bridging `display_on`).
- **CustomField** (`Spree::Metafield` aliased as `Spree::CustomField`): A value instance on a specific resource. STI on `type` column. Attributes: `value`, `custom_field_definition_id` (alias for `metafield_definition_id`). Key computed from definition: `namespace.key`.

---

## Backend Requirements

### Data Model

- **Models**: `Spree::CustomFieldDefinition = Spree::MetafieldDefinition` (constant alias); `Spree::CustomField = Spree::Metafield` (constant alias)
- **Tables**: `spree_metafield_definitions`, `spree_metafields` (renamed in 6.0)
- **STI**: `spree_metafields.type` column holds class names (`Spree::Metafields::ShortText`, etc.); renamed to `Spree::CustomFields::*` in 6.0
- **`display_on` column**: currently a string enum (`both`, `front_end`, `back_end`); bridged via `storefront_visible` boolean accessor; column renamed to boolean in 6.0

### API Surface

#### Store API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/products/:id?expand=custom_fields` | Product with custom field values |
| GET | `/api/v3/categories/:id?expand=custom_fields` | Category with custom field values |
| GET | `/api/v3/products/:id/variants/:id?expand=custom_fields` | Variant with custom field values |

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/custom_field_definitions` | List definitions (filter by `resource_type`) |
| POST | `/api/v3/admin/custom_field_definitions` | Create definition |
| PATCH | `/api/v3/admin/custom_field_definitions/:id` | Update definition |
| DELETE | `/api/v3/admin/custom_field_definitions/:id` | Delete definition |
| GET | `/api/v3/admin/products/:id/custom_fields` | List product custom field values |
| POST | `/api/v3/admin/products/:id/custom_fields` | Create/set a custom field value |
| PATCH | `/api/v3/admin/products/:id/custom_fields/:id` | Update custom field value |
| DELETE | `/api/v3/admin/products/:id/custom_fields/:id` | Delete custom field value |
| *(same pattern for orders, customers, categories, option_types)* | | |

### Serializer Fields

**Store serializer** (`Spree::Api::V3::CustomFieldSerializer`):
- `id`: prefixed (`cf_…`)
- `key`: string (full key: `namespace.key`)
- `label`: string
- `field_type`: string (token)
- `value`: any

**Admin serializer** (`Spree::Api::V3::Admin::CustomFieldSerializer`, extends Store):
- `display_on`: string (5.5); becomes `storefront_visible: boolean` in 6.0

**Admin definition serializer** (`Spree::Api::V3::Admin::CustomFieldDefinitionSerializer`):
- `id`: prefixed (`cfdef_…`)
- `namespace`, `key`, `label`, `field_type`, `resource_type`
- `storefront_visible`: boolean
- `created_at`, `updated_at`

### Authorization

- CanCanCan: `can :manage, Spree::MetafieldDefinition` for admin; custom field values inherit parent resource authorization

### i18n (Rails)

- Keys under `spree.metafield.*` → `spree.custom_field.*` (in 6.0)

---

## Frontend Requirements

### SPA Route

- `packages/dashboard/src/routes/_authenticated/$storeId/settings/custom-field-definitions.tsx` — list + CRUD sheet

### Hooks

- Centralized in `@spree/dashboard-core` (intentional — cross-resource feature; not a local hook)
- `components/spree/custom-fields/definition-form.tsx` — form component
- `components/spree/custom-fields/custom-fields-inline.tsx` — inline value editor for resource detail pages

### Schema

- `packages/dashboard/src/schemas/custom-field-definition.ts` — Zod schema + `FormValues` type

### i18n Keys

Under `admin.customFieldDefinitions.*` in all 6 locale files: page title, column headers (label, field_type, resource_type, storefront_visible), field_type option labels, form labels, empty state, toast messages.

---

## Success Criteria

- **SC-001**: Admin can create a `short_text` definition for `Spree::Product` and the API returns `field_type: "short_text"` (not `"Spree::Metafields::ShortText"`)
- **SC-002**: `GET /api/v3/products/:id?expand=custom_fields` returns `"custom_fields"` key with `field_type` token vocabulary
- **SC-003**: Setting `storefront_visible: false` excludes the field from Store API responses
- **SC-004**: All definition IDs prefixed `cfdef_…`; all value IDs prefixed `cf_…`
- **SC-005**: _(6.0)_ `display_on` string column fully replaced by `storefront_visible` boolean; all six STI class names updated to `Spree::CustomFields::*`

---

## Assumptions

- `Spree::CustomField` and `Spree::CustomFieldDefinition` are constant aliases in 5.5 — `Spree::CustomField.equal?(Spree::Metafield)` is `true`; no subclassing
- The hooks for custom field definitions are intentionally centralized in `@spree/dashboard-core` — this is an architectural choice, not a gap
- `public_metadata` columns are deprecated in 5.4 (emit `Spree::Deprecation.warn` on write) and dropped in 6.0
- `display_on: 'front_end'` (store-visible but not admin-visible) was already excluded from `MetafieldDefinition::DISPLAY` and is treated as equivalent to `storefront_visible: true`
