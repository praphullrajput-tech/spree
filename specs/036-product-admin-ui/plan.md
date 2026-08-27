# Implementation Plan: Product Admin UI (Dashboard SPA)

**Branch**: `036-product-admin-ui` | **Date**: 2026-08-25 | **Spec**: `specs/036-product-admin-ui/spec.md`

**Input**: Feature specification from `/specs/036-product-admin-ui/spec.md`

**Note**: This is a brownfield migration — the feature is already fully implemented and shipped. This plan documents the as-built architecture rather than proposing new design.

## Summary

The dashboard SPA's single-product detail page (`packages/dashboard/src/routes/_authenticated/$storeId/products/$productId.tsx`) composes ten form cards around one React Hook Form instance, covering general info, media gallery (drag-and-drop reorder), channel publishing/scheduling, categorization/tags, variants matrix, prices, inventory, custom fields, translations, and metadata. All data flows through `@spree/admin-sdk` via typed hooks in `packages/dashboard/src/hooks/`; no direct Rails model or HTML access. This plan documents the existing implementation for spec-kit tracking purposes only.

## Technical Context

**Language/Version**: TypeScript (React SPA, `packages/dashboard`) — frontend-only feature.

**Primary Dependencies**: TanStack Router (file-based route) + TanStack Query (`useQuery`/`useMutation` via `useResourceMutation`), React Hook Form + Zod (`productFormSchema`), `@dnd-kit/core` + `@dnd-kit/sortable` (media reorder), shadcn/ui + Base UI primitives (`Sheet`, `Field`, `Select`, `Checkbox`), `@spree/dashboard-core` (`StoreDatePicker`, `ResourceMultiAutocomplete`, `TagCombobox`, `mapSpreeErrorsToForm`, `useDirectUpload`).

**Storage**: N/A directly — consumes PostgreSQL-backed data indirectly through the Admin API v3 (`@spree/admin-sdk`); no direct DB access from the SPA.

**Testing**: Playwright e2e in `packages/dashboard/e2e/` (`products-edit.spec.ts`, `products-edit-media-variants.spec.ts`, `products-new-media.spec.ts`, `products-publishing.spec.ts`, `products-variants.spec.ts`, `products-custom-fields.spec.ts`, `products-translations.spec.ts`, `products-bulk.spec.ts`, `products-prices-inventory.spec.ts`, `products-new.spec.ts`), plus a Vitest unit test for the matrix generator (`variants-matrix.test.ts`). No RSpec — this feature doesn't touch backend code.

**Target Platform**: React SPA (`packages/dashboard`) served standalone, proxying to the Rails Admin API v3 at `/api/v3/admin/*`.

**Project Type**: Monorepo — single TypeScript package, `packages/dashboard` (routes + components + hooks + schemas only; no `dashboard-ui`/`dashboard-core` primitives added).

**Performance Goals**: N/A — standard CRUD form page; no specific perf target beyond existing dashboard baseline (no full-page reload on save, optimistic reorder for drag-and-drop).

**Constraints**: Must not reset unsaved edits on background refetch; media reorder must use drag-and-drop, never a numeric input; all strings i18next-backed.

**Scale/Scope**: One route (`$productId.tsx`), ten form-card components across `product-form-cards.tsx` + 4 sibling files (`publishing-card.tsx`, `media-edit-sheet.tsx`, `inventory-section.tsx`, `variants-section.tsx`/`variants-options-builder.tsx`/`variant-edit-sheet.tsx`/`variant-media-picker.tsx`), 5 hooks.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Single-module feature — entirely within `packages/dashboard`. No cross-boundary reach into `spree/core`/`spree/admin`. Data access goes exclusively through `@spree/admin-sdk` (`adminClient.products.*`, `adminClient.products.media.*`). PASS.
- **II. Admin API Is the Only Frontend Data Source**: Confirmed — every hook (`use-product.ts`, `use-product-media.ts`, `use-categories.ts`, `use-channels.ts`) calls `adminClient`, never Rails views or raw fetch. PASS.
- **III. Read/Write Field Symmetry**: N/A for this plan directly (no serializer changes here — see `010-products-and-variants`/`012-categories-and-taxonomy` for the API contract this UI consumes). The UI already respects symmetry: `variantToWirePayload` and the media payload builder ship exactly the field names the serializers return (`sku`, `barcode`, `weight`, `alt`, `variant_ids`, `channel_id`, `published_at`, `unpublished_at`) — no client-side renaming. PASS.
- **IV. Test-Backed**: Covered by Playwright e2e (`packages/dashboard/e2e/products-*.spec.ts`) for all user stories, plus a Vitest unit test (`variants-matrix.test.ts`) for the pure matrix-generation logic. No backend tests needed — frontend-only feature. PASS.
- **V. Translations and Prefixed IDs**: All labels/captions/toasts route through `useTranslation()`/`i18n.t()` against `admin.pages.products.*` / `admin.fields.*` keys in `packages/dashboard/src/locales/en.json`. IDs (`product.id`, `variant.id`, `channel.id`, `media.id`) are the prefixed IDs the SDK types already carry (`prod_...`, `variant_...`, etc.) — no raw IDs surfaced. PASS.
- **VI. `docs/plans/` for Architectural Changes**: Not a new architectural change — implements within the boundaries already set by `docs/plans/6.0-remove-master-variant.md` (no master-variant fields on the product form), `docs/plans/6.0-channels-catalogs-b2b.md` (channel/publication model), and `docs/plans/5.4-6.0-product-media-system.md` (media gallery data model). No new plan entry required. PASS.

No violations — Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/036-product-admin-ui/
├── plan.md              # This file
├── spec.md              # Feature specification (reverse-engineered)
└── tasks.md             # Task checklist (all marked done — brownfield migration)
```

### Source Code (repository root)

```text
# packages/dashboard — admin SPA routes/forms (the only module this feature touches)
packages/dashboard/src/
├── routes/_authenticated/$storeId/products/$productId.tsx   # Product detail route + ProductForm composition
├── components/spree/products/
│   ├── product-form-cards.tsx        # GeneralCard, MediaCard (dnd-kit reorder), PricesCard, InventoryCard,
│   │                                  # StatusCard, CategorizationCard, TaxCard, SEOCard, VariantsCard passthrough
│   ├── publishing-card.tsx           # PublishingCard, ManageChannelsSheet, PublicationEditor/Row, scheduleStatus()
│   ├── media-edit-sheet.tsx          # Per-image alt text / variant assignment editor sheet
│   ├── variant-media-picker.tsx      # Variant picker used inside MediaEditSheet
│   ├── inventory-section.tsx         # Per-variant stock_items editor
│   ├── variants-section.tsx          # Variants matrix table wrapper
│   ├── variants-options-builder.tsx  # Option-type/value builder feeding the matrix
│   ├── variants-matrix.ts            # Pure cartesian-product row generator (unit tested)
│   └── variant-edit-sheet.tsx        # Per-variant detail edit sheet
├── hooks/
│   ├── use-product.ts                # useProduct, useCreateProduct, useUpdateProduct, useDeleteProduct
│   ├── use-product-media.ts          # useProductMedia, useCreateProductMedia, useUpdateProductMedia, useDeleteProductMedia
│   ├── use-products.ts               # list/index hook (products table, out of scope here — see 034/035)
│   ├── use-categories.ts             # useCategories, categoryAutocompleteProps (consumed, owned by 012)
│   └── use-channels.ts               # useChannels (consumed, owned by 019)
├── schemas/product.ts                 # productFormSchema (Zod), ProductFormValues, VariantFormValues types
├── locales/en.json                    # admin.pages.products.*, admin.fields.product*.* keys
└── e2e/products-*.spec.ts             # Playwright coverage per user story
```

**Structure Decision**: Frontend-only, entirely within `packages/dashboard`. No `spree/api`, `spree/core`, `dashboard-ui`, or `dashboard-core` changes — this feature consumes existing Admin API endpoints and existing shared primitives without modification.

## Complexity Tracking

*No violations — table omitted.*
