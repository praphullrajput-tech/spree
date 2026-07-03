---

description: "Completed task list for Option Types & Values (Spree 5.4)"
---

# Tasks: Option Types & Values

**Input**: `specs/option-types-values/plan.md`, `specs/option-types-values/spec.md`

**Status**: All tasks complete (migrated feature)

**Tests**: RSpec (model + integration), Playwright E2E

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Store serializers | `spree/api/app/serializers/spree/api/v3/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Filters service | `spree/api/app/services/spree/api/v3/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Factory | `spree/core/lib/spree/testing_support/factories/options_factory.rb` |
| TS generated types | `packages/sdk/src/types/generated/` (do not edit) |
| TS Zod schemas | `packages/sdk/src/zod/generated/` (do not edit) |
| Admin SDK types | `packages/admin-sdk/src/types/generated/` (do not edit) |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/products/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard schemas | `packages/dashboard/src/schemas/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Backend Foundation ✅

**Purpose**: Schema, model, authorization — prerequisite for all API and frontend work.

- [x] T001 Create migration `spree/core/db/migrate/*_add_kind_to_spree_option_types.rb` — add `kind string null: false default: 'dropdown'`, add index, backfill `color_swatch` for `name IN ('color', 'colour')` in `reversible { dir.up }`
- [x] T002 Create migration `spree/core/db/migrate/*_add_visual_metadata_to_spree_option_values.rb` — add `color_code string` (nullable)
- [x] T003 [P] Update model `spree/core/app/models/spree/option_type.rb` — add `KINDS = %w[dropdown color_swatch buttons].freeze`, `validates :kind, inclusion: { in: KINDS }`, `color_swatch?` method, deprecated `color?` delegating via `Spree::Deprecation.warn`, `color_swatches` scope
- [x] T004 [P] Update model `spree/core/app/models/spree/option_value.rb` — add `has_one_attached :image`, `validates :color_code, format: { with: /\A#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?\z/ }, allow_blank: true`
- [x] T005 Update factory `spree/core/lib/spree/testing_support/factories/options_factory.rb` — add `:color_swatch` and `:buttons` traits to OptionType factory; add `color_code` field to OptionValue factory
- [x] T006 Verify CanCanCan abilities in `spree/core/app/models/spree/ability.rb` — `can :manage, Spree::OptionType` for admin role
- [x] T007 Write/extend model spec `spree/core/spec/models/spree/option_type_spec.rb` — cover `kind` validation, `KINDS` constant, `color_swatch?`, deprecated `color?` emits deprecation warning, `color_swatches` scope, `option_values=` custom writer scenarios

**Checkpoint**: `bundle exec rspec spec/models/spree/option_type_spec.rb` passes ✅

---

## Phase 2: Backend API — User Stories 1 & 2 ✅

**Goal**: Expose `kind`, `color_code`, `image_url` in both admin API and store filters

- [x] T008 [P] [US1/US2] Update Store serializer `spree/api/app/serializers/spree/api/v3/option_type_serializer.rb` — add `kind` to attributes
- [x] T009 [P] [US1/US2] Update Admin serializer `spree/api/app/serializers/spree/api/v3/admin/option_type_serializer.rb` — verify `kind` inherited from Store; confirm `filterable`, `metadata`, `created_at`, `updated_at` present
- [x] T010 [P] [US1/US2] Update Store serializer `spree/api/app/serializers/spree/api/v3/option_value_serializer.rb` — add `color_code` attribute; add `image_url` computed attribute (Active Storage URL or nil)
- [x] T011 [P] [US1/US2] Update Admin serializer `spree/api/app/serializers/spree/api/v3/admin/option_value_serializer.rb` — verify `color_code`, `image_url` inherited from Store
- [x] T012 [US1/US2] Update Admin controller `spree/api/app/controllers/spree/api/v3/admin/option_types_controller.rb` — add `kind` to `permitted_params` for option type; add `color_code`, `image` to nested `option_values_attributes` permitted params
- [x] T013 [US3] Update `spree/api/app/services/spree/api/v3/filters_aggregator.rb` — include `kind` in option type filter hash; include `color_code` and `image_url` in option value data hash
- [x] T014 [US1] Update integration spec `spree/api/spec/integration/spree/api/v3/admin/option_types_spec.rb` — add `kind` to create/update request bodies and response examples; add `color_code` to nested option value examples
- [x] T015 Run `bundle exec rake rswag:specs:swaggerize` (from `spree/api`) — OpenAPI spec updated with new fields

**Checkpoint**: `bundle exec rspec spec/integration/spree/api/v3/admin/option_types_spec.rb` passes ✅

---

## Phase 3: Type Generation Pipeline ✅

**Purpose**: Propagate serializer changes to TypeScript before any frontend work.

- [x] T016 Run `cd spree/api && bundle exec rake typelizer:generate` — `packages/sdk/src/types/generated/` and `packages/admin-sdk/src/types/generated/` updated with `kind` on OptionType; `color_code`, `image_url` on OptionValue
- [x] T017 Run `cd packages/sdk && pnpm generate:zod` — `packages/sdk/src/zod/generated/` updated
- [x] T018 Run `pnpm typecheck` — zero TypeScript errors

**Checkpoint**: `pnpm typecheck` passes ✅

---

## Phase 4: Frontend — User Stories 1 & 2 ✅

**Goal**: Admin can create/edit option types with kind selector, color picker, image upload, and drag-to-reorder

- [x] T019 [P] [US1/US2] Create/update resource hook `packages/dashboard/src/hooks/use-option-types.ts` — TanStack Query wrappers for list, show, create, update, delete; all queries include `expand: ['option_values']`
- [x] T020 [P] [US1/US2] Create/update form schema `packages/dashboard/src/schemas/option-type.ts` — Zod schema for OptionTypeFormValues with nested `option_values[]`; hex regex validation on `color_code`; frontend-only image state fields (`image_signed_id`, `image_cleared`, `image_url`); helpers `optionValueToFormRow()`, `valueToParam()`
- [x] T021 [US1] Create/update list route `packages/dashboard/src/routes/_authenticated/$storeId/products/options.tsx` — `<ResourceTable>` with `reorder` prop (calls `update(id, { position })` on drop); table columns: name, kind badge, values count, filterable badge
- [x] T022 [US1/US2] Add create/edit `<Sheet>` within `options.tsx` — RHF + `zodResolver`; `mapSpreeErrorsToForm` in submit handler; nested option values with `useFieldArray`; dnd-kit `DndContext` + `SortableContext` + `verticalListSortingStrategy` for value row reorder; `GripVerticalIcon` per row with `useSortable`; `PointerSensor(activationConstraint: { distance: 5 })` + `KeyboardSensor`
- [x] T023 [US2] Implement `packages/dashboard/src/components/spree/color-picker.tsx` — inline absolute-positioned picker (avoids Base UI Popover portal bug inside Sheet); `document.pointerdown` click-outside listener; Escape-to-close; renders only when parent kind is `color_swatch` or `buttons`
- [x] T024 [US2] Wire image upload on option value rows — Direct Upload via Active Storage; show image preview + clear button; enabled when parent kind is `color_swatch` or `buttons`
- [x] T025 [US1/US2] Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.optionTypes.*` — page title, empty state, column headers (name, kind, values, filterable), kind labels (dropdown/color_swatch/buttons), form labels/placeholders/help, toast messages, delete confirm
- [x] T026 [US1/US2] Add same i18n keys to **all other locale files**: `ar.json`, `de.json`, `fr.json`, `pl.json`, `zh-CN.json`

**Checkpoint**: `pnpm typecheck && pnpm lint` pass; option type CRUD works end-to-end in browser ✅

---

## Phase 5: E2E Coverage ✅

- [x] T027 Write E2E spec `packages/dashboard/e2e/option-types.spec.ts` — `Date.now()` suffix on test data; drive through visible UI only; covers: create option type → add values → reorder → set kind to color_swatch → set color_code → verify in list → delete
- [x] T028 Run `cd packages/dashboard && pnpm test:e2e` — suite passes ✅

---

## Phase 6: Polish ✅

- [x] T029 [P] Run `bundle exec i18n-tasks normalize` (from `spree/`) — no missing or unused backend keys
- [x] T030 [P] Run `pnpm lint` — zero Biome errors
- [x] T031 [P] Run `pnpm test` — all Vitest tests pass
- [x] T032 Verify `color?` emits `Spree::Deprecation.warn` — tested in `option_type_spec.rb`
- [x] T033 Verify no raw integer IDs in integration test snapshots — all IDs prefixed `opt_…` / `optval_…`
- [x] T034 Verify read/write symmetry — serializer exposes `label`, controller permits `label`, model bridges to `presentation`

---

## ⚠️ Gaps Identified

These are items that are absent or incomplete in the existing implementation:

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| **No model spec for `Spree::OptionValue`** — `color_code` hex validation is untested at model level; only OptionType has a dedicated spec | Medium | Add `spree/core/spec/models/spree/option_value_spec.rb` covering: `color_code` hex validation (valid, invalid, blank), `image` attachment presence, uniqueness of `name` per option type |
| **No store-side `/api/v3/option_types` resource** — option types are only accessible to customers via the filters aggregator; there is no dedicated read endpoint for option types in the Store API | Low | Acceptable by design (option types are admin-managed); document in spec as explicit assumption. Consider adding if storefront developers need to pre-fetch option type rendering metadata outside of the filter context. |

---

## Dependencies & Execution Order

- Phase 1 (Foundation) → Phase 2 (API) → Phase 3 (Type Pipeline) → Phase 4 (Frontend) → Phase 5 (E2E) → Phase 6 (Polish)
- Within Phase 2: models and serializers before controllers; controllers before integration specs; integration specs before `rswag:specs:swaggerize`
- Within Phase 4: hook + schema (T019/T020) before route components (T021/T022); route components before i18n extraction (T025/T026); i18n in all locales before E2E (T027)

### Parallel Opportunities

- T003 + T004 [P]: OptionType and OptionValue model updates
- T008 + T009 + T010 + T011 [P]: All serializer updates (once models exist)
- T019 + T020 [P]: Hook and schema (once types generated)
- T029 + T030 + T031 [P]: Polish checks

---

## Notes

- All tasks marked `[x]` — this is a migrated feature; implementation is complete on `main`
- `[P]` = safe to parallelize (different files, no inter-task dependency)
- `[USn]` = maps task to user story for traceability
- Never edit files under `*/generated/` — overwritten by the type pipeline
- Check `docs/plans/6.0-product-types.md` "Constraints" section before extending option types — they become live templates in 6.0
