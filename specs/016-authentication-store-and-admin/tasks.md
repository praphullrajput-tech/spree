---
description: "Task list for Authentication (Store + Admin) — retroactive, brownfield migration"
---

# Tasks: Authentication (Store + Admin)

**Input**: Design documents from `/specs/016-authentication-store-and-admin/`

**Prerequisites**: plan.md, spec.md

**Note**: This is a brownfield reverse-engineering pass. All tasks below describe already-shipped work, discovered by reading source, and are marked complete. No new code was written.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent from other tasks in the same phase (different files)
- **[Story]**: Which user story this task traces to (US1-US4)

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm `spree/core`, `spree/api` gems and `packages/dashboard-core`/`packages/admin-sdk` packages build/test as a baseline for this domain
- [x] T002 [P] Identify existing RSpec coverage: `spree/api/spec/controllers/concerns/spree/api/v3/api_key_authentication_spec.rb`, `spree/api/spec/controllers/spree/api/v3/scoped_authorization_spec.rb`, `spree/admin/spec/controllers/spree/admin/auth_rate_limiting_spec.rb`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T003 [spree/core] `Spree::Authentication::StrategyRegistry` — keyed registry of strategy classes (`spree/core/app/models/spree/authentication/strategy_registry.rb`), backing `Spree.store_authentication_strategies`/`Spree.admin_authentication_strategies`
- [x] T004 [spree/core] `Spree::Authentication::Strategies::BaseStrategy` — abstract `#authenticate`/`#provider` contract, `Result`-returning `success`/`failure` helpers, `find_or_create_user_from_oauth` bridge (`spree/core/app/models/spree/authentication/strategies/base_strategy.rb`)
- [x] T005 [spree/core] `Spree::Authentication::Strategies::EmailPasswordStrategy` — Devise `valid_password?` with `has_secure_password#authenticate` fallback (`spree/core/app/models/spree/authentication/strategies/email_password_strategy.rb`)
- [x] T006 [spree/core] `Spree::RefreshToken` model — polymorphic user, `has_secure_token`, `rotate!`, `create_for`, `revoke_all_for`, `cleanup_expired!` (`spree/core/app/models/spree/refresh_token.rb`)
- [x] T007 [spree/core] `Spree::ApiKey` model — publishable/secret key types, HMAC digest lookup, immutable scope vocabulary, revocation (`spree/core/app/models/spree/api_key.rb`)
- [x] T008 [spree/core] `Spree::UserIdentity` model — OAuth identity join, `find_or_create_from_oauth` (`spree/core/app/models/spree/user_identity.rb`)
- [x] T009 [spree/core] `Spree::Invitation` model — polymorphic resource/inviter/invitee, state machine, expiry, event publishing (`spree/core/app/models/spree/invitation.rb`)
- [x] T010 [spree/core] `Spree::PermissionSets::*` — `Base`, `SuperUser`, `RoleManagement`, and 10 other resource-scoped sets consumed by `Spree::Ability` (`spree/core/app/models/spree/permission_sets/`)
- [x] T011 [spree/api] `Spree::Api::V3::JwtAuthentication` concern — audience-scoped JWT issue/decode, `USER_TYPE_*`/`JWT_AUDIENCE_*` constants (`spree/api/app/controllers/concerns/spree/api/v3/jwt_authentication.rb`)
- [x] T012 [spree/api] `Spree::Api::V3::ApiKeyAuthentication` concern — publishable-key and secret-key lookup, `touch_api_key_if_needed` throttled last-used tracking (`spree/api/app/controllers/concerns/spree/api/v3/api_key_authentication.rb`)
- [x] T013 [spree/api] `Spree::Api::V3::ScopedAuthorization` concern — `scoped_resource`/`skip_scope_check!` DSL, fail-closed `MissingScopedResource` (`spree/api/app/controllers/concerns/spree/api/v3/scoped_authorization.rb`)
- [x] T014 [spree/api] `Spree::ApiKeyAbility` — CanCanCan `can :manage, :all` bypass for API-key-authenticated requests, deferring real gating to `ScopedAuthorization` (`spree/api/app/models/spree/api_key_ability.rb`)

**Checkpoint**: Foundation confirmed present — user-story-level controllers below all build on it.

---

## Phase 3: User Story 1 - Customer logs into the Store API (Priority: P1) 🎯 MVP

**Goal**: Store API customer login/refresh/logout via pluggable strategy + JWT + body-delivered refresh token.

- [x] T015 [US1] `Spree::Api::V3::Store::AuthController#create/#refresh/#logout` — strategy dispatch, JWT + refresh-token issuance, rate limiting (`spree/api/app/controllers/spree/api/v3/store/auth_controller.rb`)
- [x] T016 [US1] Rate limit config — `rate_limit_login` (5/60s), `rate_limit_refresh` (10/60s) (`spree/api/lib/spree/api/configuration.rb:19-22`)
- [x] T017 [US1] `Spree::Api::V3::BaseController` wiring — optional `authenticate_user` before_action, `current_ability`/`spree_current_user` (`spree/api/app/controllers/spree/api/v3/base_controller.rb`)

**Checkpoint**: Store login/refresh/logout independently verifiable via `spree/api/spec/controllers/...` (existing coverage).

---

## Phase 4: User Story 2 - Admin logs into the Admin API / SPA (Priority: P1)

**Goal**: Admin login with cookie-delivered refresh token, secret-key scope authorization, store-membership enforcement, SPA session management.

- [x] T018 [US2] `Spree::Api::V3::Admin::AuthController#create/#refresh/#logout` — shorter JWT TTL (5min), cookie-delivered refresh token (`spree/api/app/controllers/spree/api/v3/admin/auth_controller.rb`)
- [x] T019 [US2] `Spree::Api::V3::Admin::AuthCookies` concern — `HttpOnly` signed cookie, path-scoped, `SameSite` by environment, documented no-CSRF-token rationale (`spree/api/app/controllers/concerns/spree/api/v3/admin/auth_cookies.rb`)
- [x] T020 [US2] `Spree::Api::V3::AdminAuthentication` concern — secret-key-first-then-JWT dispatch, `current_ability` fallback to `ApiKeyAbility`, `require_store_membership!`, `set_no_store_cache` (`spree/api/app/controllers/concerns/spree/api/v3/admin_authentication.rb`)
- [x] T021 [US2] `packages/dashboard-core` `AuthProvider`/`useAuth` — in-memory token, scheduled silent refresh (~30s before 5min expiry), 401-retry via `adminClient.onUnauthorized` (`packages/dashboard-core/src/providers/auth-provider.tsx`, `src/hooks/use-auth.ts`)

**Checkpoint**: Admin SPA session lifecycle (login → silent refresh → logout) verifiable end-to-end.

---

## Phase 5: User Story 3 - Admin invites a teammate and they accept (Priority: P2)

**Goal**: Token-based staff invitation with public lookup/accept and privilege-bounded role granting.

- [x] T022 [US3] `Spree::Api::V3::Admin::InvitationAcceptancesController#lookup/#accept` — indistinguishable 404 for wrong-token/expired/missing, existing-vs-new-invitee branching, immediate session issuance on accept (`spree/api/app/controllers/spree/api/v3/admin/invitation_acceptances_controller.rb`)
- [x] T023 [US3] `Spree::Api::V3::Admin::RoleGrantGuard` concern — admin-role and privilege-escalation grant rejection (`spree/api/app/controllers/concerns/spree/api/v3/admin/role_grant_guard.rb`)
- [x] T024 [US3] `Spree::Invitation` state machine + callbacks — `accept!`, `create_role_user`, `invitation.accepted`/`invitation.created`/`invitation.resent` events (`spree/core/app/models/spree/invitation.rb`)

**Checkpoint**: Invitation flow verifiable independently of login (uses its own token, not a JWT, as the credential).

---

## Phase 6: User Story 4 - Pluggable authentication strategies and OAuth identities (Priority: P3)

**Goal**: Extensibility surface for non-password strategies.

- [x] T025 [US4] `provider` param dispatch against `StrategyRegistry` in both `Store::AuthController#determine_strategy` and `Admin::AuthController#authentication_strategy`, with `400 invalid_provider` for unregistered keys
- [x] T026 [US4] `Spree::UserIdentity.find_or_create_from_oauth`/`create_user_from_oauth` — OAuth bridge for integrator strategies (`spree/core/app/models/spree/user_identity.rb`)
- [x] T027 [US4] Dummy strategy generator scaffold for integrators (`spree/core/lib/generators/spree/authentication/dummy/dummy_generator.rb`)

**Checkpoint**: No OAuth strategy ships in core — this phase's checkpoint is "infrastructure present," not "OAuth login works out of the box" (documented gap, spec.md Migration Notes #3).

---

## Phase 7: Polish & Cross-Cutting Concerns (as-built, legacy parallel system)

- [x] T028 [P] `Spree::Admin::AuthRateLimiting` concern (legacy `spree/admin`) — per-IP AND per-normalized-email rate limiting for Devise session/password-reset, stricter than API v3's IP-only scheme (`spree/admin/spec/controllers/spree/admin/auth_rate_limiting_spec.rb` exercises `UserSessionsController`/`UserPasswordsController`)
- [x] T029 Document the rate-limiting asymmetry between API v3 and legacy `spree/admin` in spec.md Migration Notes (no code change — flagged for a future hardening decision)
- [x] T030 Verify existing RSpec suites pass for touched gems: `cd spree/core && bundle exec rspec`, `cd spree/api && bundle exec rspec` (baseline, no changes made by this migration)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: strategy registry + models + core concerns must exist before any controller can be documented.
- **User Stories (Phases 3-6)**: US1 (Store login) and US2 (Admin login) are independently testable and share only the Foundational layer, not each other. US3 (invitations) depends on US2's session-issuance code path (`auth_response`) being in place but not vice versa. US4 (strategy extensibility) is orthogonal to all three — it describes the dispatch mechanism US1/US2 already use.
- **Polish (Phase 7)**: documents the legacy parallel system and the cross-cutting rate-limit gap; no dependency on Phases 3-6 beyond being aware of them for the comparison.

## Notes

- All tasks marked `[x]` reflect code already present in the repository as of this migration pass — no implementation work was performed.
- Per constitution Principle IV, no new tests were added; existing coverage is cited where located. The one identified gap (no committed second strategy exercising `StrategyRegistry` end-to-end) is noted in spec.md rather than backfilled here, since backfilling it would be new work outside this migration's non-destructive scope.
