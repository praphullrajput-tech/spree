# Implementation Plan: Admin API Auth & Authorization

**Branch**: `029-admin-api-auth-authorization` | **Date**: 2026-08-25 | **Spec**: `specs/029-admin-api-auth-authorization/spec.md`

**Input**: Feature specification from `specs/029-admin-api-auth-authorization/spec.md`

**Note**: This plan is reverse-engineered (brownfield migration) — it documents the as-built design rather than proposing new work. No `research.md`/`data-model.md`/`contracts/`/`quickstart.md` were generated; the shipped code and `docs/plans/5.5-admin-api-key-scopes.md` serve as the equivalent artifacts.

## Summary

The Admin API supports two mutually exclusive authorization mechanisms behind one controller hierarchy: secret API keys (`sk_...`) are authorized by a fixed `read_<resource>`/`write_<resource>` scope vocabulary checked in `Spree::Api::V3::ScopedAuthorization`, while JWT-authenticated admin users are authorized by CanCanCan (`Spree::Ability` + `Spree::PermissionSets::*`), unchanged from the pre-existing admin authorization model. `Spree::Api::V3::AdminAuthentication#authenticate_admin!` resolves which credential is present (secret key checked first, JWT as fallback) and `#current_ability` picks the corresponding authorization strategy — a permissive `Spree::ApiKeyAbility` for keys (since `ScopedAuthorization` is their real gate) or the real `Spree::Ability` for JWT users. Every admin controller declares its scope via `scoped_resource :name` (class macro) or opts out via `skip_scope_check!`; a controller doing neither fails closed with `ScopedAuthorization::MissingScopedResource`.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/api`) — backend only, no frontend changes in this feature.

**Primary Dependencies**: CanCanCan (`Spree::Ability`, `Spree::PermissionSets::*`), Alba (serializers, for `/me` and `/api_keys/current` responses), `ActiveSupport::Concern` for `ScopedAuthorization`/`AdminAuthentication`/`RoleGrantGuard`.

**Storage**: PostgreSQL/MySQL/SQLite via ActiveRecord — `spree_api_keys.scopes` is a JSON-family column (`jsonb` on Postgres, `json` elsewhere), guarded per this repo's cross-DB convention; no foreign key constraints.

**Testing**: RSpec — controller specs (`spree/api/spec/controllers/spree/api/v3/{scoped_authorization_spec.rb, admin/api_keys_controller_spec.rb}`, `spree/api/spec/controllers/concerns/spree/api/v3/api_key_authentication_spec.rb`) covering scope-satisfied/scope-denied/alias-expansion cases per controller.

**Target Platform**: Rails engine gem (`spree/api`) consumed by a Spree host app; both server-to-server integrations (secret keys) and the admin SPA (JWT) are clients of the same controllers.

**Project Type**: Monorepo — backend only (`spree/api`, `spree/core`). No `packages/*` changes; this is Module Impact "No" for all frontend packages per spec.md.

**Performance Goals**: Scope check is an O(1) array/set membership test per request (`Array#include?` over a small fixed list) — negligible overhead versus the CanCanCan path it replaces for key-authenticated requests.

**Constraints**: Scopes are immutable post-creation (model-level validation) — this is a deliberate security constraint, not a technical limitation to be "fixed" later. `ScopedAuthorization` must fail closed (raise), never fail open (silently allow), when a controller doesn't declare a scope.

**Scale/Scope**: ~25+ `Admin::*Controller` classes, each declaring one `scoped_resource` (or inheriting one, or opting out) — see spec.md Migration Notes item 5 for coverage-verification caveat.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (`Spree::ApiKey`) and `spree/api` (controllers/concerns) only. No cross-module reach — the SPA consumes `/me`'s permission list read-only, via the standard Admin API, not by reaching into Rails models. Pass.
- **II. Admin API Is the Only Frontend Data Source**: N/A — this feature is entirely inside `spree/api`; the one frontend-adjacent surface (`/me` permissions for SPA UX) is already API-mediated. Pass.
- **III. Read/Write Field Symmetry**: N/A for authorization mechanics (no serializer/permitted_params field renames introduced by this feature). The `/me` and `/api_keys/current` response shapes are read-only descriptive endpoints, not resources with a write counterpart. Pass.
- **IV. Test-Backed**: RSpec controller specs cover scope-satisfied / scope-denied / `read_all`/`write_all` alias paths per `docs/plans/5.5-admin-api-key-scopes.md`'s migration-path step 7; `scoped_authorization_spec.rb` and `api_key_authentication_spec.rb` are the existing test-backing for the shared concern logic. Pass.
- **V. Translations and Prefixed IDs**: N/A — no new user-visible strings (error messages here are API error codes, not i18n-routed UI copy) and `Spree::ApiKey` already uses `has_prefix_id :key`. Pass.
- **VI. `docs/plans/` for Architectural Changes**: Already covered — `docs/plans/5.5-admin-api-key-scopes.md` is the architectural record for this feature; this migration documents its as-built state rather than proposing a new plan. Two divergences from that plan doc were found and are flagged in spec.md's Migration Notes (shipped `current_ability` is more permissive than specified; storage mechanism differs) but are not being changed as part of this migration — they're recorded for a future owner to reconcile. Pass, with a noted follow-up.

Any violation must appear in Complexity Tracking below with justification. None found.

## Project Structure

### Documentation (this feature)

```text
specs/029-admin-api-auth-authorization/
├── plan.md              # This file
├── spec.md              # Feature specification (migrated)
└── tasks.md             # Task checklist (migrated, all items already shipped)
```

No `research.md`, `data-model.md`, `contracts/`, or `quickstart.md` — this is a reverse-engineered spec for already-built code; those Phase 0/1 artifacts have no forward-looking content to produce. `docs/plans/5.5-admin-api-key-scopes.md` serves as the original design record.

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/
└── app/models/spree/api_key.rb                              # SCOPES, has_scope?, immutability + known-scope validations

# spree/api — Admin API v3 authorization mechanics
spree/api/
├── app/controllers/concerns/spree/api/v3/
│   ├── admin_authentication.rb                               # authenticate_admin!, current_ability (secret-key-first, JWT-fallback)
│   ├── scoped_authorization.rb                                # scoped_resource macro, authorize_api_key_scope!, MissingScopedResource
│   └── admin/
│       ├── role_grant_guard.rb                                # RoleGrantGuard — API-key exemption + permission-set-closure bound
│       └── auth_cookies.rb                                    # admin refresh-token cookie delivery (shared with 016, not this feature's focus)
├── app/models/spree/api_key_ability.rb                        # ApiKeyAbility — can :manage, :all substituted for current_ability
├── app/controllers/spree/api/v3/admin/
│   ├── me_controller.rb                                       # JWT-half of "describe current principal" + permission serialization
│   ├── api_keys_controller.rb                                 # secret-key-half (#current action, skip_scope_check! only: :current)
│   └── [~25 other Admin::*Controller classes]                 # each declares scoped_resource :name or skip_scope_check!
└── spec/controllers/spree/api/v3/
    ├── scoped_authorization_spec.rb
    ├── admin/api_keys_controller_spec.rb
    └── concerns/spree/api/v3/api_key_authentication_spec.rb
```

**Structure Decision**: Backend-only, entirely within `spree/api` (controllers/concerns) with one supporting model in `spree/core` (`Spree::ApiKey`). No `packages/*` changes — the admin SPA is a read-only consumer of `/me`'s permission list via the standard Admin API and required no changes for this feature.

## Complexity Tracking

> No constitution violations identified — table intentionally omitted.
