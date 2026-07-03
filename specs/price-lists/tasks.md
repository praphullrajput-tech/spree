---

description: "Completed task list for Price Lists (fully shipped)"
---

# Tasks: Price Lists

**Status**: All tasks complete (migrated feature)

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Factory | `spree/core/lib/spree/testing_support/factories/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/products/price-lists/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Backend Foundation ✅

- [x] T001 Create migration `*_create_spree_price_lists.rb` — `name string null: false`, `status string null: false`, `match_policy string null: false`, `starts_at datetime`, `ends_at datetime`, `products_count integer`, `prices_count integer`, store reference, timestamps; index on `[store_id, status]`
- [x] T002 Create migration `*_create_spree_price_rules.rb` — `type string null: false`, `value text`, `match_policy string`, `price_list_id reference`, timestamps
- [x] T003 Create model `spree/core/app/models/spree/price_list.rb` — `state_machines-activerecord` on `status` (`draft`, `active`, `inactive`, `scheduled`); `match_policy` inclusion validation (`all`/`any`); `bulk_update_prices` via `upsert_all`; `add_products` / `remove_products` with foreign membership guard; `accepts_nested_attributes_for :price_rules`; `whitelisted_ransackable_attributes`
- [x] T004 Create model `spree/core/app/models/spree/price_rule.rb` — STI base; `Spree.pricing.rules` registry; `applicable?` interface method
- [x] T005 Create factory `price_list_factory.rb` — default trait (`draft`); `:active`, `:inactive`, `:scheduled` traits; nested `:with_price_rules`
- [x] T006 Add CanCanCan ability: `can :manage, Spree::PriceList` for admin
- [x] T007 Write model spec `spree/core/spec/models/spree/price_list_spec.rb` — state machine transitions (valid + invalid), bulk upsert correctness, foreign membership rejection, date-range eligibility

**Checkpoint**: `bundle exec rspec spec/models/spree/price_list_spec.rb` passes ✅

---

## Phase 2: Backend API ✅

- [x] T008 [US1/US2] Create Admin serializer `spree/api/app/serializers/spree/api/v3/admin/price_list_serializer.rb` — all fields; `product_ids` as prefixed array; `price_rules` nested; counts
- [x] T009 [US1/US2/US3] Create Admin controller `spree/api/app/controllers/spree/api/v3/admin/price_lists_controller.rb` — full CRUD + `activate`, `deactivate`, `prices` (bulk upsert), `price_rule_types` (registry dump); store-scoped; foreign membership check before bulk assign
- [x] T010 [US1] Add routes: `resources :price_lists` with `member { patch :activate; patch :deactivate; get :prices; post :prices }` and `collection { get :price_rule_types }`
- [x] T011 [US1] Write integration spec `spree/api/spec/integration/spree/api/v3/admin/price_lists_spec.rb`
- [x] T012 Run `bundle exec rake rswag:specs:swaggerize`

**Checkpoint**: integration spec passes ✅

---

## Phase 3: Type Generation Pipeline ✅

- [x] T013 `cd spree/api && bundle exec rake typelizer:generate`
- [x] T014 `cd packages/sdk && pnpm generate:zod`
- [x] T015 `pnpm typecheck`

---

## Phase 4: Frontend ✅

- [x] T016 [P] [US1/US2] Create hook `packages/dashboard/src/hooks/use-price-lists.ts` — list, show, create, update, delete, activate, deactivate, bulkAssignPrices mutations
- [x] T017 [P] [US1] Create table `packages/dashboard/src/tables/price-lists.tsx` — columns: name, status badge, products count, starts_at, ends_at
- [x] T018 [US1] Create list route `products/price-lists/index.tsx` — `<ResourceTable>`; status filter; activate/deactivate bulk actions
- [x] T019 [US1] Create new route `products/price-lists/new.tsx` — form with name, match_policy, starts_at/ends_at (`<StoreDatePicker includeTime>`), nested price_rules
- [x] T020 [US1/US2/US3] Create edit route `products/price-lists/$priceListId/index.tsx` — form + product price assignment table + rule management
- [x] T021 [US1] Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.priceLists.*`
- [x] T022 [US1] Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

**Checkpoint**: `pnpm typecheck && pnpm lint` pass ✅

---

## Phase 5: E2E ✅

- [x] T023 Write `packages/dashboard/e2e/price-lists.spec.ts` — create → assign products → activate → verify status badge → deactivate
- [x] T024 Run `pnpm test:e2e` ✅

---

## Phase 6: Polish ✅

- [x] T025 [P] `bundle exec i18n-tasks normalize`
- [x] T026 [P] `pnpm lint && pnpm test`
- [x] T027 Verify foreign membership rejection returns 422 in integration spec
- [x] T028 Verify state machine prevents invalid transitions (e.g., `inactive → scheduled` directly)

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No store API endpoint | Low | By design — storefronts receive the resolved price from the pricing engine, not raw price lists |
| No `PriceRule` subclass specs | Medium | `price_rule.rb` base is tested implicitly via `PriceList`; dedicated subclass specs would improve coverage of rule applicability logic |
| `price_rule_types` returns raw class strings | Low | Consider token vocabulary (similar to `field_type` on `CustomFieldDefinition`) for SDK consumers to avoid coupling to Ruby class names |
