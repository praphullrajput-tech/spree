# Feature Specification: API v3 Serialization Framework

**Feature Branch**: `028-api-v3-serialization-framework`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — `spree/api/app/serializers/spree/api/v3/base_serializer.rb`, `spree/api/lib/typelizer/proc_resource_resolution.rb`, `spree/api/lib/spree/api/openapi/schema_helper.rb`, plus the "Serializers (Alba)" and "Type Generation Pipeline" sections of the root `CLAUDE.md`.

## User Scenarios & Testing *(mandatory)*

This is an internal framework/extension-point, not a user-facing feature. The "user" is a Spree core or extension developer adding or modifying an API v3 serializer.

### User Story 1 - Add a new resource serializer that behaves consistently with the rest of the API (Priority: P1)

A developer creates `Spree::Api::V3::FooSerializer < BaseSerializer` and gets prefixed IDs, price-gating, and expand-support for free, without reimplementing any of it.

**Why this priority**: This is the entire reason `BaseSerializer` exists — a single place these cross-cutting concerns are implemented once and inherited everywhere.

**Independent Test**: Subclass `BaseSerializer`, define one association attribute, and verify (a) `id` renders as `object.prefixed_id`, (b) the association only renders when `expand?('the_association')` is true in `params[:expand]`, and (c) `?expand=foo.bar` correctly reaches two levels deep into a nested serializer.

**Acceptance Scenarios**:

1. **Given** any object responding to `prefixed_id`, **When** a `BaseSerializer` subclass serializes it, **Then** the `id` attribute renders the Stripe-style prefixed ID (e.g. `prod_86Rf07xd4z`), never the raw database ID.
2. **Given** a serializer attribute declared via `money_attributes`, **When** `params[:hide_prices]` is true (gated storefront guest), **Then** that attribute renders `null` — gating is centralized in `BaseSerializer`, not repeated per price-bearing serializer.
3. **Given** an `Alba::Association` attribute and a request with `?expand=categories`, **When** `fetch_attribute` is invoked, **Then** `nested_params` builds child params carrying any deeper `categories.foo` expand paths, capped at 4 levels of depth (`_expand_depth`), and the child serializer's `within:` visibility matches the requested key.
4. **Given** a variant object, **When** a serializer calls `price_for`/`price_in`, **Then** the result is memoized per (object, quantity) within that serializer instance to avoid duplicate price-list queries when the same variant is referenced multiple times in one render.
5. **Given** an `Spree::Asset`-backed image vs. a direct ActiveStorage attachment, **When** `image_url_for` is called, **Then** both shapes are normalized to the same CDN URL helper output.

---

### User Story 2 - Regenerate TypeScript types, Zod schemas, and OpenAPI docs after a serializer change (Priority: P1)

A developer changes what a serializer exposes and needs the TypeScript SDKs and OpenAPI spec to stay in sync without hand-editing generated files.

**Why this priority**: Serializers are the single source of truth for the API's read shape (per Constitution Principle III, read/write symmetry) — if the generated artifacts drift, `packages/sdk`/`packages/admin-sdk` silently disagree with the actual API response shape.

**Independent Test**: Change a serializer's attributes, run the full pipeline (`typelizer:generate` → `generate:zod` → integration tests → `rswag:specs:swaggerize` → SDK tests) per `CLAUDE.md`'s documented sequence, and verify the generated TS types/Zod schemas/OpenAPI spec reflect the change.

**Acceptance Scenarios**:

1. **Given** a serializer declares `typelize field: :type`, **When** `bundle exec rake typelizer:generate` runs, **Then** the corresponding TypeScript type is (re)generated under `packages/sdk/src/types/generated/` (Store) or `packages/admin-sdk/src/types/generated/` (Admin).
2. **Given** a serializer references an association via `proc { Spree.api.x_serializer }` (lazy resolution, so host-app initializer overrides are respected at render time), **When** Typelizer introspects it for schema generation, **Then** `Typelizer::ProcResourceResolution#interface_for` resolves the proc to its underlying class first — without this, schema generation would fail on lazy/overridable associations.
3. **Given** committed serializer changes under `spree/api/app/serializers/**/*.rb`, **When** the Lefthook pre-commit hook runs, **Then** steps 1-2 (typelizer + zod generation) run and re-stage the generated output automatically — the developer does not need to remember to run them manually.
4. **Given** an OpenAPI spec regeneration is needed, **When** `bundle exec rake rswag:specs:swaggerize` runs, **Then** it is generated from `spree/api/spec/integration/` tests, not hand-edited — `schema_helper.rb` supports this generation.

### Edge Cases

- What happens if an association is expanded past 4 levels deep? `nested_params` caps `_expand_depth` at 4 — deeper requested expands are silently dropped (empty nested array), not an error.
- What happens if `object` doesn't respond to `prefixed_id`? The `id` attribute renders `nil` rather than raising — defensive against serializing non-Spree-model objects.
- What happens when a price-bearing attribute is requested by an authenticated (non-gated) admin? `hide_prices` is presumably `false`/unset in that context, so `money_attributes`/`price_for`/`price_in` render normally — the gating is opt-in via the `hide_prices` param, not hardcoded to a role check inside the serializer itself.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All API v3 serializers MUST inherit from `Spree::Api::V3::BaseSerializer`, which itself includes `Alba::Resource` and `Typelizer::DSL`.
- **FR-002**: `BaseSerializer` MUST render `id` as the object's prefixed ID (`object.prefixed_id`) universally — no subclass should re-declare a raw-ID `id` attribute.
- **FR-003**: `BaseSerializer` MUST provide a `money_attributes(*names)` class helper that gates each named attribute behind `params[:hide_prices]`, so any price-bearing serializer can opt in to storefront gating with one declaration instead of per-attribute conditionals.
- **FR-004**: `BaseSerializer` MUST support dot-notation nested expansion (`expand?`, `nested_expands_for`, `nested_params`) with a hard depth cap (4 levels) to prevent unbounded/malicious expand chains.
- **FR-005**: `BaseSerializer` MUST override `fetch_attribute` so association rendering automatically receives the correct nested expand params and `within:` visibility — subclasses must not need to manually wire this per association.
- **FR-006**: `BaseSerializer` MUST provide memoized `price_for`/`price_in` helpers (Price List-resolved vs. base price) so repeated variant references in one render don't issue duplicate price queries.
- **FR-007**: `BaseSerializer` MUST normalize both `Spree::Asset`-wrapped and direct ActiveStorage image attachments to the same CDN URL output via `image_url_for`.
- **FR-008**: The type-generation pipeline MUST resolve `proc { ... }`-wrapped (lazily-resolved, host-app-overridable) association serializer references to their underlying class before Typelizer introspects them (`Typelizer::ProcResourceResolution`).
- **FR-009**: A Lefthook pre-commit hook MUST automatically regenerate TypeScript types + Zod schemas (and re-stage them) whenever `spree/api/app/serializers/**/*.rb` files are committed.
- **FR-010**: The OpenAPI spec MUST be generated from `spree/api/spec/integration/` tests via `rswag:specs:swaggerize`, never hand-edited directly.

### Key Entities

- **Spree::Api::V3::BaseSerializer**: The framework itself — prefixed IDs, price gating, nested expand handling, image URL normalization, price memoization.
- **Typelizer::ProcResourceResolution**: A `WriterContext` prepend module resolving lazy `proc`-wrapped association serializers to real classes for schema generation.
- **Spree::Api::OpenAPI::SchemaHelper**: Support code for OpenAPI/Swagger spec generation from integration test examples.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | No | Framework lives entirely in `spree/api`; models only need to respond to `prefixed_id`/`price_for`/`price_in` where applicable (already required by other features) |
| `spree/api` (Store/Admin API v3) | Yes | `BaseSerializer`, `Typelizer::ProcResourceResolution`, `OpenAPI::SchemaHelper` — all concrete serializers inherit from this |
| `packages/dashboard` (admin SPA) | No | Consumes the generated types, doesn't implement this framework |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Yes (downstream, generated) | `src/types/generated/`, `src/zod/generated/` — regenerated from this framework's output, never hand-edited |
| `docs/plans/` | No | This is stable existing infrastructure documented directly in `CLAUDE.md`, not a plan doc |

### API Contract

Not a single endpoint — this is the shared serialization layer underneath every API v3 endpoint's response body. Its "contract" is the `typelize`/`attribute`/`money_attributes` DSL surface every serializer author uses.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new serializer subclassing `BaseSerializer` gets prefixed IDs, expand support, and price gating with zero additional code.
- **SC-002**: A serializer change committed to git automatically produces up-to-date generated TypeScript types and Zod schemas via the Lefthook hook, with no manual regeneration step required for those two.
- **SC-003**: `packages/sdk`/`packages/admin-sdk` response shapes never drift from actual API output, because both are generated from the same serializer source of truth.
- **SC-004**: Expand chains are capped at 4 levels deep, preventing unbounded nested-association response payloads.

## Assumptions

- "Feature" here means the existing serialization framework as built today — a reverse-engineered specification for spec-kit tracking, not a proposed redesign.
- Steps 3-5 of the full pipeline (integration tests, `rswag:specs:swaggerize`, SDK tests) are documented in `CLAUDE.md` as needing to run "locally before pushing" — i.e. NOT automated by the Lefthook hook, unlike steps 1-2. This asymmetry is treated as intentional (integration/OpenAPI regeneration is slower and needs a full test run), not a gap.
- `hide_prices` is assumed to be set correctly upstream (by the gated-storefront-access controller concern) — this framework only consumes the flag, it doesn't determine gating eligibility itself.

## Migration Notes

- **Not a gap, but worth flagging**: only steps 1-2 of the 5-step pipeline documented in `CLAUDE.md` are automated (Lefthook pre-commit); steps 3-5 (integration tests, OpenAPI regen, SDK tests) remain a manual pre-push responsibility. If this were fully automated, it would need to run in CI rather than a local git hook (both for speed and because integration tests require a full Rails app boot).
- **Not independently verified**: whether every existing serializer actually inherits from `BaseSerializer` (vs. a stray one hand-rolling `Alba::Resource` directly) was not exhaustively checked across the whole `spree/api/app/serializers/` tree in this pass.
- **Not migrated**: no code changes were made. This is a reverse-engineered spec for existing, already-shipped behavior.
</content>
