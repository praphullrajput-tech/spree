# Feature Specification: Option Types & Values

**Feature Branch**: `main` (shipped in Spree 5.4)

**Created**: 2026-06-30

**Status**: migrated

**Active Plan**: `docs/plans/5.4-option-type-enhancements.md`

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Manage Option Types (Priority: P1)

An admin operator creates and manages option types (Size, Color, Material…) that define the variant axes for products. They can create new types, add/edit/delete option values, reorder both types and values by dragging, and delete types they no longer need.

**Why this priority**: Option types are the foundation of product variants. Without them, products have no size/color/material axes. This is the baseline CRUD that everything else builds on.

**Independent Test**: Admin navigates to Products → Options, creates an option type named "Size" with values S/M/L, sees it appear in the list, then edits it to add XL, reorders the values by dragging, and deletes the type.

**Acceptance Scenarios**:

1. **Given** no option types exist, **When** admin creates an option type with `name: "size"` and `label: "Size"`, **Then** it appears in the list with the correct label and default `kind: "dropdown"`
2. **Given** an option type exists, **When** admin adds values "S", "M", "L" via the nested form, **Then** they are saved in the order entered and each has a prefixed ID (`optval_…`)
3. **Given** an option type with values, **When** admin drags value "L" above "M", **Then** positions update and the new order persists after page reload
4. **Given** an option type, **When** admin deletes it, **Then** it is removed from the list and a success toast appears
5. **Given** a form submitted with an empty `label`, **When** the API returns 422, **Then** field-level error appears inline on the label input

---

### User Story 2 — Configure Visual Presentation (Priority: P2)

An admin operator sets the rendering kind on an option type (`dropdown`, `color_swatch`, `buttons`) and optionally adds a hex color code or swatch image to individual option values. This gives storefronts the metadata they need to render swatches and button groups without guessing from option type names.

**Why this priority**: Builds on US1 (type must exist first). Without this, storefronts fall back to `dropdown` for everything — workable but visually degraded.

**Independent Test**: Admin edits the "Color" option type, changes `kind` to `color_swatch`, then sets `color_code: "#FF0000"` on the "Red" value and uploads a swatch image for "Floral". The filters API response reflects `kind: "color_swatch"` and each value has `color_code` / `image_url` populated.

**Acceptance Scenarios**:

1. **Given** an option type, **When** admin changes `kind` to `color_swatch`, **Then** a color picker appears on each option value row in the form
2. **Given** a `color_swatch` option type form, **When** admin enters `#FF0000` for a value, **Then** the picker renders a red preview swatch
3. **Given** a `color_swatch` option type form, **When** admin enters an invalid hex like `RED`, **Then** a validation error appears on the color_code field
4. **Given** an option value with `kind: color_swatch`, **When** admin uploads a swatch image, **Then** the image is stored via Active Storage and `image_url` is returned in the API response
5. **Given** both `color_code` and `image_url` present on a value, **When** the store API is called, **Then** both fields are returned — the frontend decides which to display

---

### User Story 3 — Storefront Rendering Hints (Priority: P3)

A storefront developer consumes `kind`, `color_code`, and `image_url` from the product filters API to render option type filters as swatches, buttons, or dropdowns — without any hardcoded name checks.

**Why this priority**: Dependent on US2 data being set. Pure read path — no UI changes required.

**Independent Test**: `GET /api/v3/products/filters` response for a store with a `color_swatch` option type includes `"kind": "color_swatch"` on the filter and `"color_code": "#FF0000"` / `"image_url": "…"` on each option value.

**Acceptance Scenarios**:

1. **Given** an option type with `kind: "color_swatch"`, **When** `GET /api/v3/products/filters` is called, **Then** the filter entry includes `"kind": "color_swatch"` alongside `id`, `name`, `label`
2. **Given** option values with `color_code` set, **When** the filters response is returned, **Then** each option value entry includes `"color_code": "#…"` and `"image_url": null` or a URL
3. **Given** option values where `color?` was previously used to detect color types, **When** `kind` is set to `color_swatch`, **Then** the deprecated `color?` method delegates to `kind == "color_swatch"` with a deprecation warning

---

### Edge Cases

- What happens when an option type name is duplicate? → `name` uniqueness is enforced via `Spree::UniqueName` concern (scoped to `spree_base_uniqueness_scope`)
- What if `kind` is set to an invalid value? → Model validates `inclusion: { in: KINDS }` — API returns 422 with field error
- What if `color_code` format is wrong? → Model validates hex format `/\A#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?\z/` — API returns 422
- What if an option type with variants is deleted? → Deleting option type cascades `dependent: :destroy` to option values; variants retain their option_value associations until manually updated
- What if `kind` changes from `color_swatch` to `dropdown`? → Existing `color_code` and `image` data is retained but no longer displayed by default — frontend decides
- What if both `color_code` and `image_url` are present? → Both are returned; storefront convention (Shopify-style) is `image_url` takes precedence

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `Spree::OptionType` must have a `kind` column (string, `null: false`, default `"dropdown"`) with valid values `dropdown`, `color_swatch`, `buttons`
- **FR-002**: `Spree::OptionValue` must have an optional `color_code` string column validated as 6- or 8-digit hex
- **FR-003**: `Spree::OptionValue` must support an optional `image` Active Storage attachment
- **FR-004**: Option types named `"color"` or `"colour"` at migration time must be backfilled to `kind: "color_swatch"`
- **FR-005**: Store API must expose `kind` on option types and `color_code`, `image_url` on option values
- **FR-006**: Admin API must accept `kind`, `color_code`, and `image` as writable params
- **FR-007**: The product filters endpoint (`GET /api/v3/products/filters`) must include `kind`, `color_code`, `image_url` in the option filter shape
- **FR-008**: Admin SPA must show a `kind` selector on the option type form
- **FR-009**: Admin SPA must show a color picker and image uploader on option value rows when the parent type's kind is `color_swatch` or `buttons`
- **FR-010**: Admin SPA must support drag-and-drop reordering of both option types (top-level list) and option values (nested in the edit sheet)
- **FR-011**: The deprecated `color?` method must delegate to `color_swatch?` with a `Spree::Deprecation.warn` call
- **FR-012**: Read/write symmetry: serializer exposes `label`; controller accepts `label`; model bridges to `presentation` column via `Spree::PresentationTranslatable`
- **FR-013**: All IDs in API responses must be prefixed (`opt_…` for option types, `optval_…` for option values)
- **FR-014**: `filterable` flag on option type must be exposed in admin serializer and accepted as a writable param

### Key Entities

- **OptionType**: Defines a product variant axis (e.g., "Color"). Key attributes: `name`, `presentation` (exposed as `label`), `kind`, `position`, `filterable`. Has many `option_values`, has many `products` through `product_option_types`.
- **OptionValue**: A specific value within an axis (e.g., "Red"). Key attributes: `name`, `presentation` (exposed as `label`), `position`, `color_code`, `image` (Active Storage). Belongs to `option_type`, has many `variants` through `option_value_variants`.

---

## Backend Requirements

### Data Model Changes

- **New column**: `spree_option_types.kind` — string, `null: false`, default `"dropdown"`; index on `kind`; backfill `color_swatch` for `name IN ('color', 'colour')`
- **New column**: `spree_option_values.color_code` — string, nullable; hex format validation
- **Attachment**: `has_one_attached :image` on `Spree::OptionValue` (Active Storage)
- **No FK constraints**, no `enum` — string column with model-level inclusion validation
- Migrations target `ActiveRecord::Migration[7.2]`

### API Surface

#### Store API *(read-only — option types surface via filters, not a dedicated resource)*

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/products/filters` | Includes option type filters with `kind`, `color_code`, `image_url` |

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/option_types` | List option types (supports `expand[]=option_values`) |
| GET | `/api/v3/admin/option_types/:id` | Show option type |
| POST | `/api/v3/admin/option_types` | Create option type |
| PATCH | `/api/v3/admin/option_types/:id` | Update option type (including nested option_values) |
| DELETE | `/api/v3/admin/option_types/:id` | Delete option type |

### Serializer Fields

**Store serializer** (`Spree::Api::V3::OptionTypeSerializer`):
- `id`: prefixed string (`opt_…`)
- `name`: string
- `label`: string (from `presentation` via `Spree::PresentationTranslatable`)
- `position`: number
- `kind`: string (`"dropdown"` | `"color_swatch"` | `"buttons"`)

**Store serializer** (`Spree::Api::V3::OptionValueSerializer`):
- `id`: prefixed string (`optval_…`)
- `name`: string
- `label`: string
- `position`: number
- `color_code`: string | null
- `image_url`: string | null
- `option_type_id`: prefixed string
- `option_type_name`: string
- `option_type_label`: string

**Admin serializer** (`Spree::Api::V3::Admin::OptionTypeSerializer`, extends Store):
- `filterable`: boolean
- `metadata`: object | null
- `created_at`, `updated_at`: timestamps

**Admin serializer** (`Spree::Api::V3::Admin::OptionValueSerializer`, extends Store):
- `metadata`: object | null
- `created_at`, `updated_at`: timestamps
- `option_type`: expandable association

### Authorization

- CanCanCan: `can :manage, Spree::OptionType` for admin; option types are not directly readable by store (accessed via filters aggregator)
- Ransack allowlist: `name`, `kind`, `filterable` on `Spree::OptionType`

### i18n (Rails)

- Keys in `spree/core/config/locales/en.yml` under `spree.option_types.*` and `spree.option_values.*`

---

## Frontend Requirements

### SPA Route(s)

- `packages/dashboard/src/routes/_authenticated/$storeId/products/options.tsx` — full CRUD list + create/edit sheets (no separate detail route; sheets are used)

### Resource Hook(s)

- `packages/dashboard/src/hooks/use-option-types.ts` — `useOptionTypes()`, `useOptionType(id)`, `useCreateOptionType()`, `useUpdateOptionType(id)`, `useDeleteOptionType()`; all queries include `expand: ['option_values']`

### Form Schema

- `packages/dashboard/src/schemas/option-type.ts` — Zod schema with `OptionTypeFormValues` type; nested `option_values[]` array; hex color validation; helpers `optionValueToFormRow()`, `valueToParam()`; frontend-only image state fields (`image_signed_id`, `image_cleared`, `image_url`)

### Component(s)

- Inline sheet form within `options.tsx` — no new `dashboard-ui` component required; uses existing `<ResourceTable>`, `<Sheet>`, `<Field>`, `<Input>`, `<Select>`
- `components/spree/color-picker.tsx` — inline absolute-positioned color picker (Base UI Popover workaround for nested portal bug)
- dnd-kit `DndContext` + `SortableContext` for nested option value rows in the edit sheet

### i18n Keys (TypeScript)

New keys in `packages/dashboard/src/locales/en.json` under `admin.optionTypes.*` and repeated in all 5 other locale files (ar, de, fr, pl, zh-CN):

- Page title, empty state
- Column headers: name, kind, values count, filterable
- Kind labels: `dropdown`, `color_swatch`, `buttons`
- Form labels: name, label, kind, filterable, color_code, image
- Button labels: create, save, delete, add value, reorder
- Toast messages: created, updated, deleted
- Confirm dialog: delete warning

### Drag-and-drop

- **Top-level list**: `reorder` prop on `<ResourceTable>` — calls `adminClient.optionTypes.update(id, { position })` on drop
- **Nested option value rows in sheet**: dnd-kit `DndContext` + `SortableContext` with `useFieldArray.move()` + computed `position` on drag end; `GripVerticalIcon` grip with `{...attributes} {...listeners}` from `useSortable`; `verticalListSortingStrategy`; `PointerSensor` with `activationConstraint: { distance: 5 }` + `KeyboardSensor`

### Date/time fields

None — option types have no date inputs.

---

## Success Criteria

- **SC-001**: Admin can create an option type with nested values in one form submission (no separate create-then-add-values flow)
- **SC-002**: `GET /api/v3/admin/option_types` returns paginated list with prefixed IDs (`opt_…`), `kind`, and expandable `option_values` including `color_code` and `image_url`
- **SC-003**: `GET /api/v3/products/filters` response includes `kind` on each option type filter and `color_code` + `image_url` on each option value
- **SC-004**: Drag-to-reorder persists after page reload for both option types (list) and option values (within a type)
- **SC-005**: Invalid `color_code` (non-hex) returns 422 with field-level error surfaced in the SPA form
- **SC-006**: `color?` method on `Spree::OptionType` emits a deprecation warning and delegates to `color_swatch?`

---

## Assumptions

- Option types are global (not store-scoped); they are shared across all stores in a Spree instance
- The store API does not expose a dedicated `/api/v3/option_types` resource — option type data surfaces only through the product filters endpoint and embedded in product/variant responses
- `kind` is a rendering hint only — it does not change the underlying data model or variant selection behavior
- Active Storage is configured (required for `image` attachments on option values)
- The `presentation` → `label` bridge is in place via `5.4-store-api-naming-standardization.md` (the `Spree::PresentationTranslatable` concern)
