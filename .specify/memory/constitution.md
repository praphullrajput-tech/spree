# Spree Commerce Constitution

## Core Principles

### I. Dual-Language Monorepo
Ruby code (models, APIs, business logic) lives exclusively in `spree/` engines. TypeScript code (SPA, SDKs, CLI tools) lives exclusively in `packages/`. The Admin SPA communicates with Ruby only via the Admin API v3 — never by importing models, rendering server HTML, or sharing files across the language boundary.

### II. API-First (NON-NEGOTIABLE)
The Admin SPA has **one data source**: the Admin API v3 in `spree/api`. If a needed endpoint or attribute is missing, add it to the API **first**, regenerate types, then consume it from the SPA. The Store API serves customers; the Admin API serves back-office operators. The same v3 controllers handle both — only auth, serializers, and enabled actions differ.

### III. Read/Write Symmetry (NON-NEGOTIABLE)
Whatever a serializer exposes (`label`, `status`, `customer_note`) is exactly what `permitted_params` must accept on write. No field-name mismatches between read and write. When the DB column has a legacy name, define reader + writer aliases on the **model** and permit the public name in the controller. The model owns the bridge — never the client or the controller.

### IV. Prefixed IDs (NON-NEGOTIABLE)
Always return prefixed IDs in API responses (e.g., `prod_86Rf07xd4z`). Never expose raw integer IDs. Use `object.association&.prefixed_id` in serializers for association IDs. Controllers use `find_by_prefix_id!`, which is automatic in `ResourceController`. Accept prefixed IDs in all request params.

### V. Three-Package Dashboard Split
- `@spree/dashboard-ui` — design system primitives + headless compounds. Data arrives via props only; never imports providers or hooks.
- `@spree/dashboard-core` — registries, providers, generic infra hooks, `defineDashboardPlugin`. The extension API.
- `@spree/dashboard` — routes, resource hooks (`use-orders`, `use-products`, …), Zod schemas, locales, app shell.

Never import a `packages/dashboard` route hook from `dashboard-ui` or `dashboard-core`. Plugin authors depend only on `dashboard-core` and `dashboard-ui`.

### VI. Serializer Hierarchy
Store serializers are customer-facing: no timestamps, no cost prices, no internal state, no admin-only relations. Admin serializers always extend the Store serializer and add `created_at`, `updated_at`, `deleted_at`, cost data, internal flags, and audit fields. Store serializers live in `spree/api/app/serializers/spree/api/v3/`; Admin serializers in `spree/api/app/serializers/spree/api/v3/admin/`.

### VII. Type Generation Pipeline (NON-NEGOTIABLE)
After any serializer change, run the full pipeline before committing:
1. `cd spree/api && bundle exec rake typelizer:generate` — TS types from serializers → `packages/sdk/src/types/generated/` and `packages/admin-sdk/src/types/generated/`
2. `cd packages/sdk && pnpm generate:zod` — Zod schemas from TS types → `packages/sdk/src/zod/generated/`
3. `bundle exec rspec spec/integration/` — integration tests
4. `bundle exec rake rswag:specs:swaggerize` — regenerate OpenAPI spec

The Lefthook pre-commit hook handles steps 1–2 automatically when serializer files are staged. Steps 3–4 must run before pushing.

### VIII. Security Constraints
Every controller action must have a CanCanCan check (`authorize!` for single-resource actions; `accessible_by(current_ability, :show)` for listings). Always fetch resources through store scope (`current_store.products`, not `Spree::Product`). Never reference user model classes directly — use `Spree.user_class` / `Spree.admin_user_class`. Declare Ransack allowlists on **models** via `whitelisted_ransackable_attributes`, `whitelisted_ransackable_associations`, and `whitelisted_ransackable_scopes`.

### IX. Naming & Namespace Conventions
- Ruby: all classes in `Spree::` namespace; `snake_case` filenames; `spree/product.rb` → `Spree::Product`
- TypeScript/TSX: `kebab-case` filenames — `use-products.ts`, `payment-methods.tsx`
- Models inherit from `Spree.base_class` (never `ApplicationRecord` directly)
- Use string columns, not enums; state machine column: `status` (legacy uses `state`)
- Uniqueness validations always scoped: `scope: spree_base_uniqueness_scope`
- JSON columns: guard with `respond_to?(:jsonb)` for cross-DB portability (PostgreSQL/MySQL/SQLite)

### X. Architecture Plan Gate
Significant architectural changes require a plan document in `docs/plans/` using `docs/plans/_template.md` before implementation. Check existing plans for conflicts. "Constraints on Current Work" sections in active plans apply to ALL work, even when not implementing that plan directly. Refer to `CLAUDE.md` for the current list of active plans.

## Module Boundaries

| Code type | Location |
|-----------|----------|
| Models, services, business logic | `spree/core/app/` |
| Store + Admin REST APIs, serializers | `spree/api/app/` |
| Legacy Rails admin (reference only — do not extend) | `spree/admin/` |
| React SPA admin (all new admin UI work) | `packages/dashboard/src/` |
| Design system (headless components, tokens) | `packages/dashboard-ui/src/` |
| Framework registries, providers, plugin API | `packages/dashboard-core/src/` |
| Store API TypeScript client | `packages/sdk/src/` |
| Admin API TypeScript client | `packages/admin-sdk/src/` |
| Architecture + feature plans | `docs/plans/` |

## Quality Gates

All must pass before merging:

**Backend (Ruby):**
- `cd spree/<engine> && bundle exec rspec` — no failing specs
- `bundle exec i18n-tasks normalize` — no missing/unused keys after locale additions
- After API changes: `bundle exec rake rswag:specs:swaggerize` — OpenAPI spec current

**Frontend (TypeScript):**
- `pnpm lint` (Biome) — zero errors
- `pnpm typecheck` — zero TypeScript errors
- `pnpm test` (Vitest) — all unit tests pass
- `cd packages/dashboard && pnpm test:e2e` — E2E suite passes for UI features
- All new user-visible strings present in **every** locale file under `packages/dashboard/src/locales/` and `packages/dashboard-core/src/locales/`

## Governance

This constitution is derived from `CLAUDE.md`, the authoritative project reference. In case of conflict, `CLAUDE.md` takes precedence. Amendments here must be reflected in `CLAUDE.md`. All feature specs, plans, and tasks must comply with these principles before implementation begins.

**Version**: 1.0.0 | **Ratified**: 2026-06-30 | **Last Amended**: 2026-06-30
