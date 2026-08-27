# Implementation Plan: API v3 Resource Framework

**Branch**: `027-api-v3-resource-framework` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-api-v3-resource-framework/spec.md`

**Note**: This is a reverse-engineered (brownfield) plan for an already-built framework. It documents the existing architecture rather than proposing new design; there is no Phase 0/1 research to perform.

## Summary

`Spree::Api::V3::ResourceController` and its `Store::ResourceController` / `Admin::ResourceController` subclasses form the shared CRUD framework underlying essentially all ~300 Store and Admin API v3 endpoints. The framework owns scoping (store + CanCanCan), pagination (Pagy), filtering/sorting (Ransack + JSON:API-style `sort=`), prefixed-ID handling, and a small set of overridable extension points (`model_class`, `serializer_class`, `scope`, `find_resource`, `permitted_params`, `collection_includes`). Concrete controllers are thin: most implement only `model_class` and `serializer_class`.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/api` gem) — backend only, no frontend changes.

**Primary Dependencies**: CanCanCan (authorization), Ransack (filtering/sorting), Pagy (pagination), `ar_lazy_preload` (association preloading), Alba (serialization, consumed via `serializer_class`), `state_machines-activerecord` (indirectly, via models this framework serves).

**Storage**: PostgreSQL (production) / SQLite3 (backend test default) via ActiveRecord — the framework itself adds no schema; it reads `Spree.base_class`-descended models via `for_store`/`accessible_by`.

**Testing**: RSpec (`spree/api/spec/controllers/spree/api/v3/resource_controller_spec.rb`, `admin/base_controller_spec.rb`, plus `spec/integration/*` for individual endpoints built on this framework).

**Target Platform**: Rails engine gem (`spree/api`) consumed by any Spree host app; serves both the Admin SPA (`packages/dashboard`, via `packages/admin-sdk`) and any Store API client (via `packages/sdk`).

**Project Type**: Monorepo — single Ruby gem (`spree/api`). No `packages/*` changes.

**Performance Goals**: N/A — framework-level; performance characteristics (query count, index usage) are the responsibility of each concrete controller's `scope_includes`/`collection_includes` overrides.

**Constraints**: Store API is publishable-key/guest-cart-token/customer-JWT only (no CanCanCan-scope auth); Admin API supports both secret-key+scopes and JWT+CanCanCan converging on the same actions. No foreign keys, no migrations — this is controller-layer code only.

**Scale/Scope**: Underlies ~300 Admin API endpoints (per `docs/plans/6.0-admin-api.md`) plus the full Store API surface.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches only `spree/api`. No cross-boundary reach — `spree/core` models are consumed strictly through their public API (`for_store`, `accessible_by`, `Spree::PermittedAttributes`, `Spree::PrefixedId`), never modified. PASS.
- **II. Admin API Is the Only Frontend Data Source**: N/A for this feature directly (it *is* part of the Admin API), but it is the mechanism that makes Principle II enforceable for every other feature — every dashboard-facing endpoint is built on this framework. PASS.
- **III. Read/Write Field Symmetry**: The framework's `permitted_params` default (`Spree::PermittedAttributes`) and `ParamsNormalizer` are the shared machinery every controller relies on to keep read/write names symmetric; the framework does not itself introduce any field-name mismatch. New controllers built on it are individually responsible for symmetry (see Migration Notes in spec.md). PASS.
- **IV. Test-Backed**: Covered by `spree/api/spec/controllers/spree/api/v3/resource_controller_spec.rb` and `spec/controllers/spree/api/v3/admin/base_controller_spec.rb` (framework-level), plus per-resource `spec/integration/*.rb` (happy-path + simple 422, per CLAUDE.md testing guidelines). PASS.
- **V. Translations and Prefixed IDs**: No user-visible strings (backend-only). Prefixed IDs are a core framework responsibility (`find_by_prefix_id!`, `decode_prefixed_id_predicates`, `ParamsNormalizer`) — enforced, not just permitted. PASS.
- **VI. `docs/plans/` for Architectural Changes**: This framework is governed by the existing `docs/plans/6.0-admin-api.md` (Admin REST API conventions, auth, endpoint list). This migrated spec references that plan rather than creating a new one, since no architectural change is being proposed. PASS.

No violations. Complexity Tracking table omitted.

## Project Structure

### Documentation (this feature)

```text
specs/027-api-v3-resource-framework/
├── plan.md              # This file
├── spec.md              # Feature specification (already written)
└── tasks.md             # Task breakdown (already written)
```

### Source Code (repository root)

```text
# spree/api — Store & Admin REST API v3 framework
spree/api/app/controllers/spree/api/v3/
├── base_controller.rb                      # Auth-agnostic infra: rate limiting, locale/currency, security headers, JWT/API-key auth
├── resource_controller.rb                  # CRUD actions, scope, pagination, ransack, prefixed IDs, permitted_params
├── store/
│   ├── base_controller.rb                  # Store API auth (publishable key) + channel/storefront-gating wiring
│   └── resource_controller.rb              # authenticate_request! -> authenticate_api_key!
└── admin/
    ├── base_controller.rb                  # Admin API auth (JWT/secret key) wiring
    └── resource_controller.rb              # authenticate_request! -> authenticate_admin!, render_result_error, decode_ids helpers

spree/api/app/controllers/concerns/spree/api/v3/
├── params_normalizer.rb                    # Prefixed-ID + nested-attributes write-param normalization
├── bulk_operations.rb                      # Shared bulk tag add/remove actions (opt-in mixin)
├── channel_resolution.rb                   # Resolves Spree::Current.channel from X-Spree-Channel header
├── storefront_gating.rb                    # login_required / prices_hidden posture enforcement (Store API)
├── locale_and_currency.rb                  # Locale/currency/market resolution from headers/params
├── rate_limit_headers.rb                   # X-RateLimit-* response headers
├── security_headers.rb                     # X-Content-Type-Options, X-Frame-Options, etc.
├── jwt_authentication.rb, api_key_authentication.rb, admin_authentication.rb  # Credential-specific auth
├── scoped_authorization.rb                 # Secret-API-key scope enforcement (Admin API)
├── error_handler.rb, resource_serializer.rb, idempotent.rb, http_caching.rb, order_lock.rb, cart_resolvable.rb
└── admin/subclassed_resource.rb            # STI create/update flow (PaymentMethod, PromotionAction, PromotionRule)

spree/api/spec/controllers/spree/api/v3/
├── resource_controller_spec.rb             # Base framework behavior
└── admin/base_controller_spec.rb           # Admin auth wiring behavior
```

**Structure Decision**: Backend-only, single gem (`spree/api`). No `spree/core` model changes, no `packages/*` changes — this plan documents the existing controller-layer framework in place, consumed unchanged by every downstream endpoint.

## Complexity Tracking

*No Constitution Check violations — table not needed.*
