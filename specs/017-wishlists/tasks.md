# Tasks: Wishlists

**Input**: Design documents from `specs/017-wishlists/`

**Prerequisites**: plan.md, spec.md

**Note**: This feature is already implemented and shipped. Tasks below are recorded retroactively (all complete) as part of the brownfield migration — they document what exists, not new work to perform.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Backend dev stack (`spree/core`, `spree/api`) already boots as part of the standard monorepo `pnpm server:dev` flow
- [x] T002 [P] Baseline backend: `cd spree/core && bundle exec rspec` and `cd spree/api && bundle exec rspec` pass on main
- [x] T003 [P] Baseline frontend: `packages/sdk` typecheck/build/test pass on main

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 [spree/core] Migration `spree/core/db/migrate/20210921070813_create_spree_wishlists.rb` — `spree_wishlists` table (`user_id`, `store_id`, `name`, `token` unique, `is_private`, `is_default`)
- [x] T005 [spree/core] `Spree::Wishlist` model in `spree/core/app/models/spree/wishlist.rb` — `has_prefix_id :wl`, `Spree::SingleStoreResource`, `has_secure_token`, `publishes_lifecycle_events`, default-uniqueness invariant
- [x] T006 [spree/core] `Spree::WishedItem` model in `spree/core/app/models/spree/wished_item.rb` — `has_prefix_id :wi`, `publishes_lifecycle_events`, `DisplayMoney` price/total helpers, variant-uniqueness + quantity validations
- [x] T007 [spree/core] `Spree::PermittedAttributes.wishlist_attributes` / `.wished_item_attributes` allowlist in `spree/core/lib/spree/permitted_attributes.rb`
- [x] T008 [spree/api] Nested routes `resources :wishlists do resources :items, only: [:create, :update, :destroy], controller: 'wishlist_items' end` in `spree/api/config/routes.rb`
- [x] T009 [spree/api] Serializer registrations (`wishlist_serializer`, `wishlist_item_serializer`) in `spree/api/lib/spree/api/dependencies.rb`

**Checkpoint**: Foundation complete — both user stories build on this.

---

## Phase 3: User Story 1 - Create and manage wishlists (Priority: P1) 🎯 MVP

**Goal**: Authenticated customers can create, list, view, update, and delete their own wishlists, with exactly one default enforced.

**Independent Test**: `POST /api/v3/store/wishlists` as an authenticated customer, confirm prefixed ID + unique token; toggle `is_default` across two wishlists and confirm only one stays default.

### Tests for User Story 1

- [x] T010 [P] [US1] RSpec model spec `spree/core/spec/models/spree/wishlist_spec.rb` — validations, default-uniqueness callback, associations
- [x] T011 [P] [US1] Controller spec `spree/api/spec/controllers/spree/api/v3/store/wishlists_controller_spec.rb` — scope-to-current-user/store, CRUD, auth requirement
- [x] T012 [P] [US1] API integration spec `spree/api/spec/integration/spree/api/v3/store/wishlists_spec.rb` — happy-path examples for OpenAPI generation

### Implementation for User Story 1

- [x] T013 [US1] `Spree::Wishlist` model (`spree/core/app/models/spree/wishlist.rb`, depends on T004)
- [x] T014 [US1] `Spree::Api::V3::Store::WishlistsController` (`spree/api/app/controllers/spree/api/v3/store/wishlists_controller.rb`) — `scope` = `current_user.wishlists.for_store(current_store)`, `create` sets `store` explicitly
- [x] T015 [US1] `Spree::Api::V3::WishlistSerializer` (`spree/api/app/serializers/spree/api/v3/wishlist_serializer.rb`) — `name`, `token`, `is_default`, `is_private`, expandable `items`
- [x] T016 [US1] Factory `spree/core/lib/spree/testing_support/factories/wishlist_factory.rb`

**Checkpoint**: User Story 1 fully functional and independently testable.

---

## Phase 4: User Story 2 - Add/update/remove variants in a wishlist (Priority: P2)

**Goal**: Authenticated customers can add, update, and remove variant entries (with quantity) on a wishlist they own.

**Independent Test**: `POST /api/v3/store/wishlists/:wishlist_id/items` with a `variant_id`; confirm it appears under `?expand=items`; attempt a duplicate variant and confirm 422.

### Tests for User Story 2

- [x] T017 [P] [US2] Controller spec `spree/api/spec/controllers/spree/api/v3/store/wishlist_items_controller_spec.rb` — parent scoping via `set_parent`, duplicate-variant 422, quantity validation

### Implementation for User Story 2

- [x] T018 [US2] `Spree::WishedItem` model (`spree/core/app/models/spree/wished_item.rb`, depends on T013)
- [x] T019 [US2] `Spree::Api::V3::Store::WishlistItemsController` (`spree/api/app/controllers/spree/api/v3/store/wishlist_items_controller.rb`) — `set_parent` scopes through `current_user.wishlists.find_by_prefix_id!`, `parent_association = :wished_items`
- [x] T020 [US2] `Spree::Api::V3::WishlistItemSerializer` (`spree/api/app/serializers/spree/api/v3/wishlist_item_serializer.rb`) — `variant_id`, `wishlist_id`, `quantity`, nested `variant`

**Checkpoint**: Both user stories functional independently and together.

---

## Phase 5: Frontend SDK (already complete, no dashboard equivalent)

- [x] T021 [P] `packages/sdk/src/store-client.ts` — `client.wishlists.{list,get,create,update,delete}` + `client.wishlists.items.{create,update,delete}`
- [x] T022 [P] Generated types `packages/sdk/src/types/generated/{Wishlist,WishlistItem}.ts` and Zod schemas `packages/sdk/src/zod/generated/{Wishlist,WishlistItem}.ts`
- [x] T023 [P] Vitest suite `packages/sdk/tests/wishlists.test.ts`
- [x] T024 [P] SDK usage docs `docs/developer/sdk/store/wishlists.mdx` and example app `packages/sdk/examples/wishlists/`

**Note**: No `packages/dashboard`, `dashboard-ui`, `dashboard-core`, or `packages/admin-sdk` tasks exist for this feature — confirmed no Admin API endpoint, no admin route/hook, and no Playwright e2e coverage (see spec.md → Migration Notes).

---

## Dependencies & Execution Order

- Phase 2 (Foundational) blocks Phases 3 and 4.
- User Story 2 (wished items) depends on `Spree::Wishlist` (T013) existing as the parent association, but is otherwise independently testable per-item.
- Phase 5 (SDK) consumes the Phase 3/4 API surface but was implemented and shipped together with it.

## Notes

- All tasks are marked complete `[x]` — this is a documentation-only retroactive task list for an already-shipped feature, per the brownfield migration process.
- No new work is implied by this file. Gaps (no Admin API, no dashboard, no e2e) are intentionally recorded rather than back-filled — see spec.md → Migration Notes for whether/when to address them.
