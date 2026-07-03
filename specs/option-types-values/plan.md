# Implementation Plan: Option Types & Values

**Branch**: `main` (shipped Spree 5.4) | **Date**: 2026-04-02 | **Spec**: [spec.md](spec.md)

**Status**: Implemented

---

## Summary

Added rendering metadata to `Spree::OptionType` and `Spree::OptionValue` to close the last significant gap vs. Shopify and Saleor: storefronts previously had no API-level signal for how to render option types (dropdown vs. swatches vs. buttons), and no visual data on option values (hex color, swatch image). The implementation adds a `kind` column to OptionType and `color_code` + `image` attachment to OptionValue, exposes them in the Store API, filters endpoint, and Admin API, and wires the Admin SPA with a kind selector, color picker, image uploader, and drag-to-reorder for both types and values.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite all supported |
| **Backend testing** | RSpec + Factory Bot · rswag (integration/OpenAPI) |
| **Frontend testing** | Vitest + MSW (unit) · Playwright (E2E) |
| **Serialization** | Alba → Typelizer (auto-generates TS types) |
| **API auth** | JWT (admin SPA) · Secret key + scopes (integrations) |
| **Authorization** | CanCanCan (JWT) · scope-based (secret key) |
| **Soft delete** | Not applicable — option types are hard-deleted |
| **i18n (backend)** | `Spree.t` / `I18n.t` · `spree/core/config/locales/en.yml` |
| **i18n (frontend)** | i18next · `packages/dashboard/src/locales/[lang].json` |
| **Scope** | Full-stack (backend model + API + Admin SPA) |

---

## Key Decisions (from `docs/plans/5.4-option-type-enhancements.md`)

1. **`kind` is a rendering hint, not behavioral.** The underlying OptionType → OptionValue → Variant data model is unchanged. All three kinds use the same M2M structure.
2. **Three fixed kinds only**: `dropdown`, `color_swatch`, `buttons`. No `text_input`, `file`, etc. — those are for MetafieldDefinition, not variant axes.
3. **`dropdown` default for backward compatibility.** Existing option types continue to work unchanged.
4. **Backfill on migration**: option types named `"color"` or `"colour"` get `kind: "color_swatch"` automatically.
5. **`color_code` and `image` are optional and independent.** Both can coexist; the frontend chooses which to display (Shopify convention: image > color_code).
6. **Image uses Active Storage** (consistent with product images, category icons) — not a URL string column.
7. **`color?` deprecated, not removed.** Delegates to `color_swatch?` with `Spree::Deprecation.warn`. Removed in 6.0.
8. **No metafields for presentation data.** Dedicated columns provide an explicit API contract; metafields lack discoverable keys.

---

## Constitution Check

- [x] **API-First**: `kind`, `color_code`, `image_url` added to API before SPA consumed them
- [x] **Read/Write Symmetry**: `label` serialized and `label` accepted in `permitted_params`; model bridges to `presentation` via `Spree::PresentationTranslatable`
- [x] **Prefixed IDs**: `opt_…` for option types, `optval_…` for option values; `prefixed_id` used in serializers for `option_type_id`
- [x] **Serializer Hierarchy**: `Admin::OptionTypeSerializer` extends `V3::OptionTypeSerializer`; no timestamps in Store serializer
- [x] **Type Pipeline**: Typelizer + Zod regen run after serializer changes; changeset added for `@spree/sdk`
- [x] **Security**: CanCanCan `can :manage, Spree::OptionType` for admin; Ransack allowlist declared on model
- [x] **Namespace**: `Spree::OptionType`, `Spree::OptionValue` — inherit from `Spree.base_class`
- [x] **Plan Conflicts**: Reviewed `6.0-product-types.md` (option types become live template); `5.4-store-api-naming-standardization.md` (presentation → label bridge); no conflicts

---

## Project Structure

### Documentation

```text
specs/option-types-values/
├── spec.md              ← this feature's specification (migrated)
├── plan.md              ← this file
└── tasks.md             ← completed task list
```

### Source Code

```text
# Backend — models
spree/core/app/models/spree/option_type.rb         ← kind column, KINDS constant, color_swatch?, deprecated color?
spree/core/app/models/spree/option_value.rb        ← color_code column, has_one_attached :image

# Backend — migrations
spree/core/db/migrate/*_add_kind_to_spree_option_types.rb
spree/core/db/migrate/*_add_visual_metadata_to_spree_option_values.rb

# Backend — serializers
spree/api/app/serializers/spree/api/v3/option_type_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/option_type_serializer.rb
spree/api/app/serializers/spree/api/v3/option_value_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/option_value_serializer.rb

# Backend — controller + filters
spree/api/app/controllers/spree/api/v3/admin/option_types_controller.rb
spree/api/app/services/spree/api/v3/filters_aggregator.rb   ← kind, color_code, image_url added

# Backend — specs
spree/core/spec/models/spree/option_type_spec.rb
spree/api/spec/integration/spree/api/v3/admin/option_types_spec.rb

# Backend — factory
spree/core/lib/spree/testing_support/factories/options_factory.rb

# Type pipeline (auto-generated — do not edit)
packages/sdk/src/types/generated/
packages/admin-sdk/src/types/generated/
packages/sdk/src/zod/generated/

# Frontend
packages/dashboard/src/routes/_authenticated/$storeId/products/options.tsx
packages/dashboard/src/hooks/use-option-types.ts
packages/dashboard/src/schemas/option-type.ts
packages/dashboard/src/tables/option-types.tsx         ← table column definitions
packages/dashboard/src/components/spree/color-picker.tsx
packages/dashboard/src/locales/en.json                 ← admin.optionTypes.*
packages/dashboard/src/locales/[ar|de|fr|pl|zh-CN].json

# E2E
packages/dashboard/e2e/option-types.spec.ts
```

---

## Phase 0: Research

*Completed. Key findings:*

- Existing `color?` method checked `name.in?(['color', 'colour'])` — a hardcoded name check with no API contract
- `FiltersAggregator` returned `type: "option"` for every option type — no rendering hint
- No visual data on option values — frontends had to invent their own metafield conventions
- Competitive gap vs. Shopify (`ProductOptionValueSwatch`) and Saleor (`AttributeValue.value` + `file_url`)
- `presentation` → `label` bridge already in place via `5.4-store-api-naming-standardization.md`

---

## Phase 1: Schema + Models

Migration → model changes → factory updates → model specs

- `add_column :spree_option_types, :kind, :string, null: false, default: 'dropdown'` + index + backfill
- `add_column :spree_option_values, :color_code, :string`
- `has_one_attached :image` on `Spree::OptionValue`
- `KINDS = %w[dropdown color_swatch buttons].freeze` + `validates :kind, inclusion: { in: KINDS }`
- `color_swatch?` method; deprecated `color?` delegates via `Spree::Deprecation.warn`
- Hex format validation on `color_code`

---

## Phase 2: Serializers + API

Serializer changes → controller permitted_params → filters aggregator → integration specs → OpenAPI regen

- `OptionTypeSerializer`: add `kind`
- `OptionValueSerializer`: add `color_code`, `image_url`
- Admin serializers extend store serializers (changes inherited automatically)
- `PermittedAttributes`: add `kind`, `color_code`, `image` to option type / option value params
- `FiltersAggregator`: include `kind`, `color_code`, `image_url` in option filter shape
- Integration spec covers new fields; `rswag:specs:swaggerize` regenerates OpenAPI spec

---

## Phase 3: Type Generation Pipeline

`typelizer:generate` → `generate:zod` → integration tests → `rswag:specs:swaggerize`

- TS types updated in `packages/sdk/src/types/generated/` and `packages/admin-sdk/src/types/generated/`
- Zod schemas updated in `packages/sdk/src/zod/generated/`
- Changeset added to `@spree/sdk` and `@spree/admin-sdk`

---

## Phase 4: Admin SPA

Resource hook → form schema → route component → i18n → E2E

- `use-option-types.ts`: TanStack Query wrappers; all queries `expand: ['option_values']`
- `option-type.ts` schema: Zod with nested `option_values[]`; hex validation; `optionValueToFormRow()` helper
- `options.tsx`: `<ResourceTable>` with `reorder` prop; create/edit `<Sheet>`; nested values with dnd-kit; color picker + image uploader conditional on `kind`
- `color-picker.tsx`: inline absolute-positioned implementation (avoids Base UI Popover portal bug in nested sheet context)
- i18n keys added to all 6 locale files
- E2E spec: `option-types.spec.ts` with `Date.now()` suffix on test names

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Inline color picker (not Base UI Popover) | Base UI Popover fails to render inside Sheet portal tree | No fix available upstream; inline absolute positioning is reliable and already used in similar cases (`color-picker.tsx`) |
