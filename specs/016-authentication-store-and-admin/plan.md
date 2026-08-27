# Implementation Plan: Authentication (Store + Admin)

**Branch**: `016-authentication-store-and-admin` | **Date**: 2026-08-25 | **Spec**: `specs/016-authentication-store-and-admin/spec.md`

**Input**: Feature specification from `/specs/016-authentication-store-and-admin/spec.md`

**Note**: This is a brownfield reverse-engineering pass (`/speckit.brownfield.migrate`). The plan below documents the architecture as built, not a forward design — "tasks" in `tasks.md` are retroactive and marked complete.

## Summary

Authentication is split into a pluggable strategy layer (`spree/core`) and two parallel API v3 auth surfaces (`spree/api`): Store (customer, publishable-key-or-JWT) and Admin (secret-key-or-JWT). Both auth controllers resolve a `provider` param against a `StrategyRegistry`, dispatch to a `BaseStrategy` subclass (only `EmailPasswordStrategy` ships), and on success issue a short-lived JWT (audience-scoped: `store_api` vs `admin_api`, 1h vs 5min) plus an opaque `Spree::RefreshToken` — delivered as a JSON field for Store, as an `HttpOnly` signed cookie for Admin. Admin API requests additionally support `Spree::ApiKey` secret keys authorized by a fixed `read_*`/`write_*` scope vocabulary (`ScopedAuthorization`) instead of CanCanCan. Staff onboarding runs through `Spree::Invitation` (token-based, publicly reachable lookup/accept endpoints) gated by `RoleGrantGuard` so a caller can't grant roles beyond their own privilege. The Admin SPA (`packages/dashboard-core`) consumes this via an `AuthProvider` that keeps the access token in memory only and silently refreshes off the cookie. The legacy `spree/admin` Devise flow runs a separate, stricter (IP+email) rate-limiting scheme and is not touched by this migration.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines, backend) and TypeScript (React SPA, frontend) — this feature spans both.

**Primary Dependencies**: Backend: `jwt` gem (HS256), `state_machines-activerecord` (`Invitation#status`), CanCanCan (`Spree::Ability`, `Spree::ApiKeyAbility`), `has_secure_token` (Rails, for `RefreshToken`/`Invitation`), `rate_limit` DSL (Rack-attack-style, via `Rails.cache`), Devise (legacy `spree/admin` only). Frontend: `@spree/admin-sdk` (`adminClient.auth.*`), React context (`AuthProvider`/`useAuth`), i18next (`switchLocale`).

**Storage**: PostgreSQL/MySQL/SQLite via ActiveRecord, no FK constraints. Relevant tables: `spree_refresh_tokens`, `spree_api_keys`, `spree_invitations`, `spree_user_identities`, `spree_roles`, `spree_role_users`.

**Testing**: RSpec + Factory Bot (`spree/api/spec/controllers/concerns/spree/api/v3/{api_key_authentication_spec.rb, scoped_authorization_spec.rb}`, `spree/admin/spec/controllers/spree/admin/auth_rate_limiting_spec.rb`); no Vitest/Playwright coverage located specifically for the auth flow in this pass (see Migration Notes gap in spec.md item 3 re: strategy extensibility not having a test double committed).

**Target Platform**: Rails engine gems (`spree_core`, `spree_api`, `spree_admin`) consumed by a Spree host app; `packages/dashboard-core`/`packages/dashboard` React SPA served standalone.

**Project Type**: Monorepo, both backend and frontend — `spree/core` (strategy/model layer), `spree/api` (both auth controllers + shared concerns), `spree/admin` (legacy Devise flow, untouched), `packages/dashboard-core` (`AuthProvider`), `packages/admin-sdk` (client + generated types).

**Performance Goals**: N/A — no stated throughput targets; existing rate limits (5 login attempts / 60s, 10 refreshes / 60s, both per API-key-or-IP) are the only quantified behavior.

**Constraints**: No FK constraints (repo-wide convention); admin JWT TTL fixed at 5 minutes (shorter blast radius than the 1h store default) by explicit design comment in `AuthController#jwt_expiration`; secret-key scopes are immutable post-creation (`ApiKey#scopes_immutable`).

**Scale/Scope**: 2 auth controllers (Store, Admin) + 1 invitation-acceptance controller + 6 shared concerns (`JwtAuthentication`, `ApiKeyAuthentication`, `ScopedAuthorization`, `AdminAuthentication`, `Admin::AuthCookies`, `Admin::RoleGrantGuard`) + 5 core models (`RefreshToken`, `ApiKey`, `Invitation`, `UserIdentity`, `Role`/`RoleUser`) + 2 strategy classes + 1 registry + ~13 `PermissionSets::*` classes + 1 SPA auth provider/hook pair. No migrations, endpoints, or UI added by this migration pass (documentation only).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (models/strategies), `spree/api` (controllers/concerns), `spree/admin` (legacy, pre-existing, unmodified), `packages/dashboard-core` (`AuthProvider`), `packages/admin-sdk` (client methods/types). All coupling is within-gem/package or via documented extension points (`Spree::Authentication::StrategyRegistry`, `Spree::Dependencies`-style config lookups, `adminClient` singleton). No gem reaches across a boundary directly. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: Confirmed — `AuthProvider` calls only `adminClient.auth.*`, never touches Rails models or server-rendered HTML. **Pass.**
- **III. Read/Write Field Symmetry**: N/A for this migration (no serializer changes made); existing read fields (`token`, `refresh_token`, `user`) have no corresponding "write" shape since auth endpoints aren't CRUD resources. **Pass (N/A).**
- **IV. Test-Backed**: Existing RSpec coverage enumerated above under Testing. This migration adds no new code, so no new tests are required — tasks.md cites existing specs as already satisfying this principle. Gap noted in spec.md Migration Notes: no committed example of a second (non-email) strategy to exercise `StrategyRegistry`'s extensibility end-to-end. **Pass, with a documented coverage gap.**
- **V. Translations and Prefixed IDs**: `Spree::Invitation`, `Spree::ApiKey`, `Spree::RefreshToken`, `Spree::UserIdentity` all use `has_prefix_id` (`inv_`, `key_`, `rt_`, `uid_`). No new user-visible strings added by this migration. **Pass.**
- **VI. `docs/plans/` for Architectural Changes**: This area is already governed by `docs/plans/5.5-admin-api-key-scopes.md` (secret-key scopes) and `docs/plans/5.5-admin-auth-cookie-refresh.md` (cookie-based refresh flow), both shipped. This migration documents their as-built state; it does not introduce new architecture requiring a new plan entry. **Pass.**

Any violation must appear in Complexity Tracking below with justification.

## Project Structure

### Documentation (this feature)

```text
specs/016-authentication-store-and-admin/
├── plan.md              # This file
├── spec.md              # Feature specification (migrated)
└── tasks.md             # Retroactive, all tasks marked complete
```

### Source Code (repository root)

```text
# spree/core — strategy layer, auth-adjacent models
spree/core/
├── app/models/spree/authentication/strategy_registry.rb
├── app/models/spree/authentication/strategies/base_strategy.rb
├── app/models/spree/authentication/strategies/email_password_strategy.rb
├── app/models/spree/refresh_token.rb
├── app/models/spree/api_key.rb
├── app/models/spree/invitation.rb
├── app/models/spree/user_identity.rb
├── app/models/spree/role.rb
├── app/models/spree/role_user.rb
├── app/models/spree/permission_sets/{base,super_user,role_management,...}.rb
└── lib/generators/spree/authentication/dummy/dummy_generator.rb

# spree/api — Store & Admin auth controllers + shared concerns
spree/api/
├── app/controllers/spree/api/v3/base_controller.rb
├── app/controllers/spree/api/v3/store/auth_controller.rb
├── app/controllers/spree/api/v3/admin/auth_controller.rb
├── app/controllers/spree/api/v3/admin/invitation_acceptances_controller.rb
├── app/controllers/concerns/spree/api/v3/jwt_authentication.rb
├── app/controllers/concerns/spree/api/v3/api_key_authentication.rb
├── app/controllers/concerns/spree/api/v3/scoped_authorization.rb
├── app/controllers/concerns/spree/api/v3/admin_authentication.rb
├── app/controllers/concerns/spree/api/v3/admin/auth_cookies.rb
├── app/controllers/concerns/spree/api/v3/admin/role_grant_guard.rb
├── app/models/spree/api_key_ability.rb
├── lib/spree/api/configuration.rb                       # jwt_expiration, admin_jwt_expiration, rate_limit_*, refresh_token_expiry
└── spec/controllers/spree/api/v3/{scoped_authorization_spec.rb, concerns/spree/api/v3/api_key_authentication_spec.rb}

# spree/admin — legacy Devise flow (untouched, parallel system)
spree/admin/
├── app/controllers/spree/admin/{user_sessions_controller.rb, user_passwords_controller.rb}
├── app/controllers/concerns/spree/admin/auth_rate_limiting.rb
└── spec/controllers/spree/admin/auth_rate_limiting_spec.rb

# packages/dashboard-core — SPA auth context/hook
packages/dashboard-core/src/
├── providers/auth-provider.tsx
├── hooks/use-auth.ts
└── client.ts                                            # adminClient singleton

# packages/admin-sdk — generated + hand-written auth client surface
packages/admin-sdk/src/
├── admin-client.ts                                       # adminClient.auth.{login,refresh,logout,acceptInvitation}
└── types/generated/{AdminUser,Invitation}.ts
```

**Structure Decision**: Full-stack feature spanning `spree/core` (strategy/model layer) + `spree/api` (both v3 auth surfaces and their shared concerns) + `packages/dashboard-core`/`packages/admin-sdk` (SPA consumption). `spree/admin`'s Devise-based flow is a parallel, pre-existing system in the same domain — included in the Module Impact table for completeness and because its rate-limiting inconsistency with API v3 is a documented gap, but no code there is part of this migration's scope.

## Complexity Tracking

> No constitution violations identified — table intentionally omitted.
