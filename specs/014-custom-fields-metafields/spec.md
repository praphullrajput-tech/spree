# Feature Specification: Custom Fields / Metafields

**Feature Branch**: `014-custom-fields-metafields`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (`Spree::MetafieldDefinition`, `Spree::Metafield`, `Spree::Metafields` concern, Admin API v3 `custom_fields`/`custom_field_definitions` endpoints, `@spree/dashboard` Custom Field Definitions settings page + inline record editor) as part of the spec-kit brownfield migration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Define a reusable custom field for a resource type (Priority: P1)

A store admin wants to capture structured, merchant-specific data on a resource type (e.g. "Material" on all Products) without a code change. They create a `Spree::MetafieldDefinition` (API: `CustomFieldDefinition`) scoped to a resource type, giving it a namespace/key, a label, and a field type (short text, long text, rich text, number, boolean, or JSON).

**Why this priority**: Without a definition, no per-record value can be captured or validated — this is the foundation of the whole feature.

**Independent Test**: In Settings → Custom Field Definitions, create a definition for `Spree::Product` with key `material`, field type `short_text`. Confirm it appears in the list and is available for products.

**Acceptance Scenarios**:

1. **Given** no existing definition, **When** an admin creates one with `namespace`, `key`, `label`, `field_type`, and `resource_type`, **Then** the definition is persisted and default `metafield_type` is set from `Spree.metafields.types.first` when omitted.
2. **Given** a definition with a given `namespace` + `key` + `resource_type`, **When** a second definition is created with the same triple, **Then** validation fails on uniqueness.
3. **Given** an unrecognized `field_type` token, **When** it is submitted, **Then** a field-level error naming the valid tokens (`short_text, long_text, rich_text, number, boolean, json`) is returned instead of a raw class-name inclusion error.

---

### User Story 2 - Set and read a custom field value on a record (Priority: P1)

An admin (or an API client) sets a custom field's value on a specific record instance (e.g. this Product's `material` = "wool"). The value is validated by the field type's STI subclass and persisted as a `Spree::Metafield` (API: `CustomField`) linked to the definition and the owning resource.

**Why this priority**: This is the actual data-capture mechanism the definitions exist to serve; a definition with no way to assign values delivers no value.

**Independent Test**: Via `PATCH /api/v3/admin/products/:id` with `custom_fields: [{ custom_field_definition_id: ..., value: "wool" }]`, or via `POST .../products/:id/custom_fields`, confirm the value round-trips on `GET .../products/:id?expand=custom_fields`.

**Acceptance Scenarios**:

1. **Given** a persisted parent record and a definition, **When** a value is assigned via `custom_fields=` (nested attributes) or `set_metafield`, **Then** an existing metafield for that definition is updated and a missing one is created (upsert by `metafield_definition_id`).
2. **Given** an existing custom field, **When** its value is set to blank (nil or whitespace-only string), **Then** the metafield row is destroyed — except `false`, `0`, `[]`, `{}` which are real values and are never treated as blank.
3. **Given** a new (unpersisted) parent record, **When** `custom_fields=` is assigned before the parent is saved, **Then** the assignment is deferred and replayed via an `after_save` callback once the parent has an id.
4. **Given** a JSON-typed definition, **When** a Hash/Array is assigned as the value, **Then** it is serialized to canonical JSON text before validation.

---

### User Story 3 - Expose custom fields to Store API consumers (Priority: P2)

A storefront client requests a product/variant/category with `?expand=custom_fields` and receives the storefront-visible custom field values (`key`, `label`, `field_type`/`type`, `value`) without any admin-only fields leaking through.

**Why this priority**: Custom fields only deliver customer-facing value (e.g. product specs) once the Store API surfaces them; this is the read path for the primary use case documented in the rename plan.

**Independent Test**: `GET /api/v3/store/products/:id?expand=custom_fields` returns a `custom_fields` array; a definition with `display_on: back_end` is excluded from that array.

**Acceptance Scenarios**:

1. **Given** a definition with `display_on: both` (storefront-visible), **When** the parent product is fetched with `expand=custom_fields`, **Then** its value is included in the response.
2. **Given** a definition with `display_on: back_end`, **When** the same Store API request is made, **Then** the value is excluded (only reachable via the Admin API).

---

### User Story 4 - Manage custom fields from the admin dashboard (Priority: P2)

An admin manages custom field definitions from Settings → Custom Field Definitions (`packages/dashboard`) and edits per-record values inline on a record's detail page (`<CustomFieldsInline>` component), backed by `useCustomFields`/`useCustomFieldDefinitions` hooks calling `@spree/admin-sdk`.

**Why this priority**: The legacy Rails admin (`spree/admin/app/controllers/spree/admin/metafield_definitions_controller.rb`) is being phased out per `CLAUDE.md`; the SPA is the forward-looking surface for this workflow, gated on the Admin API CRUD endpoints existing (User Stories 1 & 2).

**Independent Test**: Create a definition in Settings, then open a Product detail page and confirm the new field appears in the inline custom fields editor and can be saved.

**Acceptance Scenarios**:

1. **Given** the Settings page, **When** an admin creates/edits/deletes a `CustomFieldDefinition`, **Then** the change is reflected via `adminClient.customFieldDefinitions` and TanStack Query cache invalidation (`customFieldDefinitionsRootKey`).
2. **Given** a record detail page for one of the six first-class parents (products, variants, orders, customers, categories, option types), **When** the admin edits a custom field value inline, **Then** `adminClient.customFields(ownerType, ownerId)` performs the create/update/delete and the value list re-fetches.
3. **Given** any other `Spree::Metafields`-including parent (not one of the six), **When** custom-field UI is needed, **Then** the generic `adminClient.customFields(ownerType, ownerId)` escape hatch is used instead of a first-class binding.

---

### Edge Cases

- What happens when a client submits a `custom_field_definition_id` that doesn't resolve to any known definition? → `ArgumentError` is converted to a field-level validation error (`custom_fields[i].custom_field_definition_id`) and surfaced as a 422, not a raw 400/500.
- What happens when two custom fields for the same `(definition, resource)` pair are submitted? → DB-enforced uniqueness on `(metafield_definition_id, resource_type, resource_id)` rejects the duplicate; the client must update, not re-create.
- How does the system handle a `field_type` write that supplies the legacy Ruby class name (`Spree::Metafields::ShortText`) instead of the token (`short_text`)? → Both forms are accepted for back-compat; only reads always emit the token.
- What happens when a plugin registers its own metafield type (e.g. `MyExt::Metafields::Color`) not in the built-in token table? → `field_type` falls through to the raw class name on both read and write until a registration API exists (post-6.0 concern).
- What happens to a resource's custom fields when the parent resource is destroyed? → `dependent: :destroy` on the `metafields`/`public_metafields` associations cascades the delete.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow admins to define custom fields per resource type via `Spree::MetafieldDefinition`, scoped by `namespace` + `key` + `resource_type` (unique together).
- **FR-002**: System MUST restrict `resource_type` to models registered in `Spree.metafields.enabled_resources` (29 models as of this migration: Variant, Order, Product, Customer, Category, OptionType, Taxon, Shipment, Payment, Refund, GiftCard, StoreCredit, Address, LineItem, Store, Promotion, ShippingMethod, TaxRate, StockItem, StockTransfer, CustomerReturn, CreditCard, PaymentMethod, PaymentSource, NewsletterSubscriber, PaymentSession, PaymentSetupSession, Asset, Taxonomy).
- **FR-003**: System MUST restrict field type to a fixed vocabulary (`short_text`, `long_text`, `rich_text`, `number`, `boolean`, `json`, mapped to `Spree::Metafields::*` STI subclasses), with typed validation per subclass (e.g. JSON validity for `Spree::Metafields::Json`).
- **FR-004**: System MUST support two visibility levels per definition via `display_on` (`both` / `back_end`) — storefront + admin visible, or admin-only. (`front_end`-only is defined in the concern but excluded from `MetafieldDefinition::DISPLAY` and never used.)
- **FR-005**: System MUST let any including model set/get/query a custom field value by namespace.key (`set_metafield`, `get_metafield`, `has_metafield?`, `with_metafield_key` scope) without requiring the caller to know the definition id upfront.
- **FR-006**: System MUST upsert custom field values by `(definition, resource)` — never allow two rows for the same pair — and treat blank values (nil/whitespace string) as a delete signal while preserving `false`/`0`/`[]`/`{}` as real values.
- **FR-007**: System MUST expose custom field values on the Store API only via `?expand=custom_fields` on Product/Variant/Category serializers, filtered to `display_on: both`, with **no dedicated Store API CRUD endpoints**.
- **FR-008**: System MUST expose full CRUD for custom field values and definitions on the Admin API (`/api/v3/admin/.../custom_fields`, `/api/v3/admin/custom_field_definitions`), gated by CanCanCan authorization against the parent resource.
- **FR-009**: System MUST NOT let API clients set the underlying STI `type` column directly — it is derived from the linked definition's `metafield_type` in a `before_validation` callback.
- **FR-010**: System MUST keep read and write field names symmetric on the Admin/Store API surface: `label` (not `name`), `field_type` (token, not raw class string on writes for new clients), `custom_field_definition_id` (aliases `metafield_definition_id`).
- **FR-011**: System MUST support all Sqids-based prefixed IDs (`cf_` for values, `cfdef_` for definitions) on read and write, while still decoding legacy `mf_`/`mfdef_`-prefixed ids.

### Key Entities

- **`Spree::MetafieldDefinition`** (API-aliased `Spree::CustomFieldDefinition`): the schema for a custom field on a given resource type — `namespace`, `key`, `name`/`label`, `metafield_type`/`field_type`, `resource_type`, `display_on`. `has_many :metafields, dependent: :destroy`.
- **`Spree::Metafield`** (API-aliased `Spree::CustomField`), STI base with subclasses `Spree::Metafields::{ShortText, LongText, RichText, Number, Boolean, Json}`: a single value instance, `belongs_to :resource, polymorphic: true, touch: true` and `belongs_to :metafield_definition`. Delegates `key`, `full_key`, `name`, `label`, `display_on` to its definition.
- **Any `Spree::Metafields`-including model** (29 today): the polymorphic `resource` side — gains `metafields`/`public_metafields`/`private_metafields` associations and the instance-level get/set/has API.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::MetafieldDefinition`, `Spree::Metafield` + STI subclasses (`app/models/spree/metafields/*.rb`), `Spree::Metafields` concern (`app/models/concerns/spree/metafields.rb`), constant aliases `Spree::CustomField`/`Spree::CustomFieldDefinition`, migration `db/migrate/20250728095629_create_spree_metafields.rb` |
| `spree/api` (Store/Admin API v3) | Yes | Store: `CustomFieldSerializer`, `?expand=custom_fields` on Product/Variant/Category serializers. Admin: `Admin::CustomFieldsController`, `Admin::CustomFieldDefinitionsController`, `Admin::CustomFieldSerializer`, `Admin::CustomFieldDefinitionSerializer`, nested `custom_fieldable` route concern on products/categories/option_types/customers/variants/orders |
| `spree/admin` (legacy Rails admin) | Yes (legacy, no new work) | `Admin::MetafieldDefinitionsController`, `Admin::MetafieldsHelper` — still live, being phased out per `CLAUDE.md`, not the target for new features |
| `packages/dashboard` (admin SPA) | Yes | Settings → Custom Field Definitions route + table (`routes/.../settings/custom-field-definitions.tsx`, `tables/custom-field-definitions.tsx`), inline editor (`components/spree/custom-fields/custom-fields-inline.tsx`), schema (`schemas/custom-field-definition.ts`), e2e specs |
| `packages/dashboard-core` | Yes | Hooks `use-custom-fields.ts` (`useCustomFields`, `useCustomFieldDefinitions`, create/update/delete mutations) |
| `packages/admin-sdk` | Yes | `customFields(ownerType, ownerId)` generic + first-class bindings on the six parents (products, variants, orders, customers, categories, option types), `customFieldDefinitions` resource, examples, tests |
| `packages/sdk` | Yes (generated) | `StoreCustomField` type, `custom_fields` expand param — generated from serializer changes, not hand-written |
| `docs/plans/` | Yes | `docs/plans/5.5-6.0-custom-fields-rename.md` (this migration's authoritative plan) and `docs/plans/5.4-metafield-translations.md` (adjacent, pending) already exist and govern this area |

### API Contract *(include if feature touches spree/api)*

- **Admin endpoints**:
  - `GET/POST /api/v3/admin/custom_field_definitions`, `GET/PATCH/DELETE /api/v3/admin/custom_field_definitions/:id` (flat, filterable by `?resource_type_eq=`)
  - `GET/POST /api/v3/admin/{products,variants,orders,customers,categories,option_types}/:parent_id/custom_fields`, `PATCH/DELETE .../custom_fields/:id` (nested via `custom_fieldable` route concern; extensible to any `Spree::Metafields`-including parent)
- **Store endpoint**: no dedicated endpoint — read-only via `?expand=custom_fields` on `products`, `variants`, `categories`
- **Serializer fields (read)**:
  - Store `CustomFieldSerializer`: `label`, `type` (token via `field_type`... legacy `type` retained alongside `field_type` per rename plan), `key`, `value`
  - Admin `CustomFieldSerializer`: adds `display_on`
  - Admin `CustomFieldDefinitionSerializer`: `label`, `field_type` (token), `display_on`, `namespace`, `key`, `resource_type`
  - Per Constitution Principle III, controller `permitted_params` mirror these exactly: `custom_field_definition_id`, `value` (values); `namespace`, `key`, `label`, `field_type`, `resource_type`, `display_on` (definitions)
- **Auth**: Admin API — secret key + scopes or JWT + CanCanCan (`authorize! :update, parent` for writes, `authorize! :show, parent` for reads); Store API — publishable key, read-only via expand

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can create a custom field definition and see it applied to a record's detail page without any code deploy.
- **SC-002**: A storefront `?expand=custom_fields` request never returns a `display_on: back_end` value.
- **SC-003**: Setting a blank value on an existing custom field always removes the row; setting `false`/`0`/empty-array/empty-object never does.
- **SC-004**: Every one of the 29 `Spree::Metafields`-including models supports the same get/set/has API with zero per-model custom code.
- **SC-005**: Legacy `mf_`/`mfdef_`-prefixed ids and current `cf_`/`cfdef_`-prefixed ids both resolve correctly via `find_by_prefix_id!`.

## Assumptions

- The Metafields → Custom Fields rename is mid-flight: 5.4/5.5 phases (API surface + constant aliases) are shipped; the 6.0 phase (model/table/column rename, `display_on` → `storefront_visible` boolean) is not yet implemented. This spec documents the system **as it exists today**, i.e. dual-named.
- The legacy Rails admin (`spree/admin/metafield_definitions_controller.rb`) is out of scope for further investment; `packages/dashboard`'s Settings page is the forward path per `CLAUDE.md`.
- Plugin-defined custom field types (outside the six built-in STI subclasses) are supported today via class-name fallback but have no registration API — that is called out as a 6.0-plus concern in the rename plan, not solved here.
- The six "first-class" SDK parents (products, variants, orders, customers, categories, option_types) reflect the SPA's current detail-page surface; the remaining 23 `Spree::Metafields` parents use the generic SDK escape hatch, per explicit design decision in the rename plan.

## Migration Notes

This feature is **currently dual-named** — the rename from "Metafields" to "Custom Fields" is a three-phase plan (`docs/plans/5.5-6.0-custom-fields-rename.md`), and this repository sits between phase 2 (5.5) and phase 3 (6.0):

| Layer | Name used today | Name used in code |
|-------|-----------------|--------------------|
| Store API wire format | `custom_fields` (expand param + response key) | N/A — API only |
| Admin API wire format | `custom_fields` / `custom_field_definitions` (endpoints, params, most serializer attrs) | N/A — API only |
| Admin API serializer internals | — | `Spree::Api::V3::CustomFieldSerializer`, `Admin::CustomFieldDefinitionSerializer` (files/classes already renamed) |
| Ruby model class names | `Spree::CustomField`, `Spree::CustomFieldDefinition` **as constant aliases only** (`app/models/spree/custom_field.rb`: `CustomField = Metafield`) | Underlying class is still `Spree::Metafield` / `Spree::MetafieldDefinition` — same object, two names, not a subclass (subclassing would break STI) |
| Table / column names | — | Still `spree_metafields`, `spree_metafield_definitions`, `metafield_definition_id`, `metafield_type`, `name`, `display_on` — untouched |
| STI subclass namespace | — | Still `Spree::Metafields::ShortText` etc. — becomes `Spree::CustomFields::ShortText` in 6.0 |
| Concern name | — | Still `Spree::Metafields` (module) — becomes `Spree::HasCustomFields` in 6.0 |
| Instance methods | — | Still `set_metafield`/`get_metafield`/`has_metafield?` — become `set_custom_field` etc. in 6.0 |
| Legacy Rails admin (`spree/admin`) | "Metafields" throughout (controller, helper, routes, views) | Not touched by the rename — legacy admin is being phased out, not migrated |
| Visibility model | `display_on` (`both`/`back_end`, string) exposed as-is on Admin API | Becomes `storefront_visible` (boolean) in 6.0; `alias_attribute`/`storefront_visible` accessor shims exist per `docs/plans/5.5-6.0-display-on-to-boolean.md` for the *shared* `Spree::DisplayOn` concern (also used by PaymentMethod/ShippingMethod) |
| `metafield_type` → `field_type` | API always emits/accepts the `field_type` token (`short_text`, etc.); legacy class-string writes still accepted for back-compat | Underlying column is still named `metafield_type` |

**Pending 6.0 work** (not yet done, tracked in the plan, out of scope for this migrated spec): rename `spree_metafields`/`spree_metafield_definitions` tables and their FK/type columns, rename the STI namespace and concern, replace `display_on` with a `storefront_visible` boolean column, drop the constant-alias shim files, drop `public_metadata` (separate but adjacent `Spree::Metadata` cleanup).

**Gap identified during this migration**: the rename plan's Phase 1 table describes an Admin API endpoint path rename as "⏳ pending" but the actual routes (`spree/api/config/routes.rb`) already use `custom_fields`/`custom_field_definitions` — the plan document is stale relative to the shipped code on this point.
