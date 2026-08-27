---

description: "Task list for feature migration (retrospective — feature already shipped)"
---

# Tasks: API v3 Serialization Framework

**Input**: Design documents from `/specs/028-api-v3-serialization-framework/`

**Prerequisites**: plan.md, spec.md

**Status**: migrated — all tasks below reflect code that already exists in the repository. This is a retrospective record, not pending work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent files, no dependency ordering required
- **[Story]**: US1 = a developer adding/using a serializer, US2 = the type/schema/docs regeneration pipeline

## Phase 1: Base Serializer Framework [US1]

- [x] T001 `spree/api/app/serializers/spree/api/v3/base_serializer.rb` — `Alba::Resource` + `Typelizer::DSL` inclusion, universal prefixed-ID `id` attribute
- [x] T002 [P] `money_attributes(*names)` class helper — centralizes `hide_prices`-gated attribute declaration
- [x] T003 [P] `expand?`/`nested_expands_for`/`nested_params` — dot-notation nested expansion, capped at `_expand_depth` 4
- [x] T004 `fetch_attribute` override — auto-injects nested expand params + correct `within:` visibility into child association serializers
- [x] T005 [P] `price_for`/`price_in` — memoized per (variant, quantity) Price-List-resolved and base-price helpers
- [x] T006 [P] `image_url_for` — normalizes `Spree::Asset`-wrapped vs. direct ActiveStorage attachments to one CDN URL helper

## Phase 2: Type Generation Support [US2]

- [x] T007 `spree/api/lib/typelizer/proc_resource_resolution.rb` — `Typelizer::WriterContext` prepend resolving `proc { ... }`-wrapped (lazy, host-app-overridable) association serializers to their class before schema introspection
- [x] T008 `spree/api/lib/spree/api/openapi/schema_helper.rb` — OpenAPI/Swagger spec generation support from integration test examples

## Phase 3: Pipeline Automation [US2]

- [x] T009 `lefthook.yml` pre-commit hook — on `spree/api/app/serializers/**/*.rb` changes, runs `bundle exec rake typelizer:generate` + `cd packages/sdk && pnpm generate:zod`, re-stages `packages/sdk/src/{types,zod}/generated/` and `packages/admin-sdk/src/types/generated/`
- [x] T010 Manual pre-push steps (documented in `CLAUDE.md`, not automated): `spree/api/spec/integration/` tests, `bundle exec rake rswag:specs:swaggerize` (OpenAPI regen), `packages/sdk` test suite

## Notes

- Every phase above is already implemented; nothing here is scheduled work.
- Per spec.md's Migration Notes: only steps 1-2 of the 5-step pipeline are Lefthook-automated; steps 3-5 remain a manual developer responsibility pre-push. This is treated as an intentional design choice (integration tests need a full Rails boot), not a gap.
- Whether every existing concrete serializer actually inherits from `BaseSerializer` was not exhaustively re-verified across the full `spree/api/app/serializers/` tree in this pass.
</content>
