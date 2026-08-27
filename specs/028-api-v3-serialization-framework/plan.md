# Implementation Plan: API v3 Serialization Framework

**Branch**: `028-api-v3-serialization-framework` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/028-api-v3-serialization-framework/spec.md`

**Note**: This plan is reverse-engineered from an already-shipped internal framework (brownfield migration), not authored ahead of implementation.

## Summary

`Spree::Api::V3::BaseSerializer` is the shared Alba-based serialization layer every API v3 serializer inherits from: universal prefixed IDs, opt-in price gating (`money_attributes`, `hide_prices`), depth-capped dot-notation association expansion, memoized price-list resolution, and image URL normalization. `Typelizer::ProcResourceResolution` teaches the type-generation tooling to resolve lazily-wrapped (`proc { ... }`) association serializers so host-app overrides still generate correct types. A Lefthook pre-commit hook automates the first two steps of the five-step regeneration pipeline documented in `CLAUDE.md`; the remaining three (integration tests, OpenAPI regen, SDK tests) stay manual pre-push steps.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/api`) for the serializer framework; generated TypeScript in `packages/sdk`/`packages/admin-sdk` is a downstream artifact, not hand-authored here.

**Primary Dependencies**: `alba` (serialization), `typelizer` (Ruby→TypeScript type generation), `oj` (JSON rendering), `rswag`/OpenAPI tooling (spec generation from integration tests), Lefthook (pre-commit automation).

**Storage**: N/A — this is a response-shaping layer, not a persistence concern.

**Testing**: RSpec (serializer specs alongside each concrete serializer), `spree/api/spec/integration/` (happy-path + simple-422 examples that double as the OpenAPI generation source), `packages/sdk`/`packages/admin-sdk` Vitest suites (consume the generated types/Zod schemas).

**Target Platform**: Every API v3 response body, Store and Admin alike.

**Project Type**: Monorepo — `spree/api` (the framework) with downstream, generated-only touch points in `packages/sdk`/`packages/admin-sdk`.

**Performance Goals**: Memoized per-object price resolution (`price_for`/`price_in`) avoids duplicate Price List queries when the same variant appears multiple times in one response (e.g. an order with repeated line items referencing the same variant).

**Constraints**: Association expansion is hard-capped at 4 levels of `_expand_depth` to bound response size/query cost from `?expand=` chains.

**Scale/Scope**: One base class + one Typelizer patch + OpenAPI schema-generation support, inherited by every serializer across the entire API v3 surface (Store and Admin).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Entirely within `spree/api`; `packages/sdk`/`admin-sdk` only receive generated output, never hand-edit it — no boundary crossing. PASS.
- **II. Admin API Is the Only Frontend Data Source**: This framework *is* the mechanism that makes that principle enforceable — every serializer (Store and Admin) funnels through it, and generated types are what `packages/dashboard` types against.
- **III. Read/Write Field Symmetry**: This framework governs the *read* half only. It doesn't itself enforce that `permitted_params` matches — that's each concrete controller's responsibility (see `027-api-v3-resource-framework`) — but it is the reason a serializer's exposed field list is a single, generateable source of truth to check controllers against.
- **IV. Test-Backed**: RSpec serializer specs + integration tests (which double as OpenAPI generation source) + downstream SDK Vitest suites. Full chain tested, though step ordering (Lefthook-automated vs. manual) is asymmetric — see Migration Notes.
- **V. Translations and Prefixed IDs**: This framework is literally where universal prefixed-ID rendering (`object.prefixed_id`) is enforced for all API v3 resources — Principle V's prefixed-ID half is implemented here.
- **VI. `docs/plans/` for Architectural Changes**: No plan doc exists; none needed for this migration (documentation-only, stable existing infrastructure already documented in `CLAUDE.md`).

No violations. Complexity Tracking table intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/028-api-v3-serialization-framework/
├── plan.md              # This file
├── spec.md              # Reverse-engineered specification
└── tasks.md             # Reverse-engineered task list (all complete)
```

### Source Code (repository root)

```text
# spree/api — the framework itself
spree/api/
├── app/serializers/spree/api/v3/base_serializer.rb   # prefixed IDs, money_attributes, expand handling, price memoization, image_url_for
├── lib/typelizer/proc_resource_resolution.rb          # WriterContext prepend — resolves proc-wrapped associations for schema gen
└── lib/spree/api/openapi/schema_helper.rb             # OpenAPI/Swagger generation support from integration test examples

# Downstream — generated only, never hand-edited
packages/sdk/src/types/generated/          # Store API TS types (via `bundle exec rake typelizer:generate`)
packages/sdk/src/zod/generated/            # Store API Zod schemas (via `pnpm generate:zod`)
packages/admin-sdk/src/types/generated/    # Admin API TS types
# packages/admin-sdk has no separate zod generation step referenced in this pass

# Automation
lefthook.yml   # pre-commit: typelizer:generate + generate:zod on spree/api/app/serializers/**/*.rb changes, re-stages output
```

**Structure Decision**: Backend-only framework (`spree/api`), with generated-artifact touch points in `packages/sdk`/`packages/admin-sdk` that are never hand-edited. No `spree/core`, `packages/dashboard`, `dashboard-ui`, or `dashboard-core` involvement.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
</content>
