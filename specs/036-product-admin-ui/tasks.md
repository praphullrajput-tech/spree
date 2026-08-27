---
description: "Task list for Product Admin UI (Dashboard SPA) — brownfield migration, all tasks completed"
---

# Tasks: Product Admin UI (Dashboard SPA)

**Input**: Design documents from `/specs/036-product-admin-ui/`

**Prerequisites**: plan.md, spec.md

**Tests**: Included — Playwright e2e already exists for every user story; a Vitest unit test covers the matrix generator.

**Organization**: Tasks are grouped by user story. This is a reverse-engineered (brownfield) migration — the feature already shipped, so every task below is marked complete and documents the as-built implementation rather than prescribing new work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Different files, no dependencies
- **[Story]**: Maps to spec.md user stories (US1-US4)

## Path Conventions

Single module: `packages/dashboard/src/{routes,components,hooks,schemas}/...`, e2e in `packages/dashboard/e2e/`. No backend paths — frontend-only feature.

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm dev stack: `pnpm server:dev` (backend) + `cd packages/dashboard && pnpm dev` (frontend)
- [x] T002 [P] Baseline frontend: `pnpm typecheck && pnpm lint` passes at workspace root
- [x] T003 [P] Confirm Admin API v3 product/media/channel/category endpoints already exist (consumed, not built here — see `010-products-and-variants`, `012-categories-and-taxonomy`, `019-channels-and-order-routing`)

**Checkpoint**: Dev stack up, dependent API surfaces confirmed in place.

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 [packages/dashboard] Define `ProductFormValues`/`VariantFormValues` + `productFormSchema` (Zod) in `packages/dashboard/src/schemas/product.ts`
- [x] T005 [packages/dashboard] Wire `useProduct` with full `expand` list (`default_variant`, `variants`, `option_types`, `categories`, `tax_category`, `product_publications`, `channels`, `custom_fields`) in `packages/dashboard/src/hooks/use-product.ts`
- [x] T006 [packages/dashboard] Wire `useProductMedia`/`useCreateProductMedia`/`useUpdateProductMedia`/`useDeleteProductMedia` in `packages/dashboard/src/hooks/use-product-media.ts`
- [x] T007 [packages/dashboard] Create the file-based route `packages/dashboard/src/routes/_authenticated/$storeId/products/$productId.tsx` with `productToFormValues`/`variantToWirePayload` mapping helpers
- [x] T008 [packages/dashboard] Add all `admin.pages.products.*` / `admin.fields.product*.*` i18next keys to `packages/dashboard/src/locales/en.json` (and all other shipped locale files)

**Checkpoint**: Foundation shipped — form schema, data hooks, route shell, and translation keys all in place.

---

## Phase 3: User Story 1 - Merchant edits core product details (Priority: P1) 🎯 MVP

**Goal**: Single-page edit of name/description/status/tax/SEO with a dirty-safe save cycle.

**Independent Test**: Edit Name + Status, Save, verify persisted value + no data loss from a concurrent refetch.

### Tests for User Story 1

- [x] T010 [P] [US1] Playwright e2e `packages/dashboard/e2e/products-edit.spec.ts`

### Implementation for User Story 1

- [x] T011 [US1] `GeneralCard`, `StatusCard`, `TaxCard`, `SEOCard` in `packages/dashboard/src/components/spree/products/product-form-cards.tsx`
- [x] T012 [US1] `useUpdateProduct`/`useDeleteProduct` in `packages/dashboard/src/hooks/use-product.ts`
- [x] T013 [US1] `isDirty`-guarded reset `useEffect` + post-save re-baseline in `$productId.tsx` `ProductForm`
- [x] T014 [US1] `mapSpreeErrorsToForm` wiring in `onSubmit` catch block (`$productId.tsx`)

**Checkpoint**: Core edit flow fully functional and covered by e2e.

---

## Phase 4: User Story 2 - Merchant manages product media with drag-and-drop reorder (Priority: P1)

**Goal**: Upload, edit, reorder (drag-and-drop only), and delete product media.

**Independent Test**: Drag a thumbnail to a new position; verify sequential 1-indexed `position` persists.

### Tests for User Story 2

- [x] T015 [P] [US2] Playwright e2e `packages/dashboard/e2e/products-edit-media-variants.spec.ts`
- [x] T016 [P] [US2] Playwright e2e `packages/dashboard/e2e/products-new-media.spec.ts`

### Implementation for User Story 2

- [x] T017 [US2] `MediaCard` with `DndContext`/`SortableContext` (`rectSortingStrategy`, `PointerSensor` + `KeyboardSensor`) in `packages/dashboard/src/components/spree/products/product-form-cards.tsx`
- [x] T018 [US2] `MediaEditSheet` (alt text + per-variant assignment) in `packages/dashboard/src/components/spree/products/media-edit-sheet.tsx`
- [x] T019 [US2] `variant-media-picker.tsx` for the variant-assignment picker inside `MediaEditSheet`
- [x] T020 [US2] `useDeleteProductMedia` immediate-delete path (independent of product PATCH) in `packages/dashboard/src/hooks/use-product-media.ts`
- [x] T021 [US2] Media-hydration `useEffect` bypassing the `isDirty` guard for the still-empty case (`$productId.tsx`)

**Checkpoint**: Media gallery fully functional with drag-and-drop reorder, independently testable.

---

## Phase 5: User Story 3 - Merchant controls channel publishing and scheduling (Priority: P2)

**Goal**: Assign channels and schedule per-channel publish/unpublish windows.

**Independent Test**: Toggle a channel on, set a future `published_at`, verify "Scheduled" status renders with correct caption.

### Tests for User Story 3

- [x] T022 [P] [US3] Playwright e2e `packages/dashboard/e2e/products-publishing.spec.ts`

### Implementation for User Story 3

- [x] T023 [US3] `PublishingCard` + `scheduleStatus()` in `packages/dashboard/src/components/spree/products/publishing-card.tsx`
- [x] T024 [US3] `ManageChannelsSheet` (channel toggle via `useFieldArray`) in `publishing-card.tsx`
- [x] T025 [US3] `PublicationEditor`/`PublicationRow` with `StoreDatePicker` (`includeTime`, `inline`) in `publishing-card.tsx`
- [x] T026 [US3] Default-channel seeding (`seedDefaultChannel`, `form.reset(..., { keepDirtyValues: true })`) for the New Product flow in `publishing-card.tsx`

**Checkpoint**: Publishing/scheduling fully functional and independently testable.

---

## Phase 6: User Story 4 - Merchant assigns categories, tags, and variants (Priority: P2)

**Goal**: Category/tag assignment plus an option-type-driven variants matrix.

**Independent Test**: Assign two categories + one tag, save, verify persistence; separately, build a 2x2 option matrix and verify four generated variant rows.

### Tests for User Story 4

- [x] T027 [P] [US4] Playwright e2e `packages/dashboard/e2e/products-variants.spec.ts`
- [x] T028 [P] [US4] Vitest unit test `packages/dashboard/src/components/spree/products/variants-matrix.test.ts`
- [x] T029 [P] [US4] Playwright e2e `packages/dashboard/e2e/products-custom-fields.spec.ts` (adjacent `CustomFieldsInlineCard` on the same page)
- [x] T030 [P] [US4] Playwright e2e `packages/dashboard/e2e/products-translations.spec.ts` (adjacent `ResourceTranslationsCard`)
- [x] T031 [P] [US4] Playwright e2e `packages/dashboard/e2e/products-prices-inventory.spec.ts`

### Implementation for User Story 4

- [x] T032 [US4] `CategorizationCard` (`ResourceMultiAutocomplete` + `TagCombobox`) in `packages/dashboard/src/components/spree/products/product-form-cards.tsx`
- [x] T033 [US4] `variants-options-builder.tsx` (option type/value builder)
- [x] T034 [US4] `variants-matrix.ts` (pure cartesian-product generator) + `variants-section.tsx` (table wrapper)
- [x] T035 [US4] `variant-edit-sheet.tsx` (per-variant detail sheet) + `inventory-section.tsx` (per-variant `stock_items`)
- [x] T036 [US4] `variantToWirePayload` mapping (1-indexed position, NOT-NULL defaults, always-send `prices`) in `$productId.tsx`

**Checkpoint**: All four user stories independently functional — full product edit surface complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T037 [P] Verify all locale files (not just `en.json`) carry matching `admin.pages.products.*`/`admin.fields.product*.*` keys in `packages/dashboard/src/locales/`
- [x] T038 Full frontend suite: `pnpm typecheck && pnpm lint && pnpm test` at workspace root
- [x] T039 [P] `cd packages/dashboard && pnpm test:e2e` for all `products-*.spec.ts` flows
- [x] T040 Cross-reference `docs/plans/6.0-remove-master-variant.md`, `6.0-channels-catalogs-b2b.md`, `5.4-6.0-product-media-system.md` — confirm no drift between this UI and those plans' end-states

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → User stories (Phases 3-6, all P1/P1/P2/P2 already shipped, independently testable) → **Polish (Phase 7)**
- US1 (general edit) and US2 (media) are both P1 and were built together as the MVP core edit surface.
- US3 (publishing) and US4 (categorization/variants) are P2, layered on the same form instance without blocking US1/US2.

## Notes

- This tasks.md documents a **completed brownfield migration** — all checkboxes are `[x]` by design; no outstanding work items exist for this feature slice.
- Any future net-new work on this surface (e.g., new card, new bulk-editing hook) should be tracked as new tasks in this file per `/speckit-converge`, not by unchecking these historical entries.
