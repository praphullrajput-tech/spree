---

description: "Task list for feature migration (retrospective — feature already shipped)"
---

# Tasks: Admin API Auth & Authorization

**Input**: Design documents from `/specs/029-admin-api-auth-authorization/`

**Prerequisites**: plan.md, spec.md

**Status**: migrated — all tasks below reflect code that already exists in the repository. This is a retrospective record, not pending work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent files, no dependency ordering required
- **[Story]**: US1 = secret-key scope authorization, US2 = JWT+CanCanCan authorization, US3 = new-controller declaration contract, US4 = current-principal endpoints

## Phase 1: API Key Model [US1]

- [x] T001 `spree/core/app/models/spree/api_key.rb` — `SCOPES` allowlist, `has_scope?`, immutability + known-scope validations, `has_prefix_id :key`

## Phase 2: Authentication Entry Point (shared) [US1, US2]

- [x] T002 `spree/api/app/controllers/concerns/spree/api/v3/admin_authentication.rb` — `authenticate_admin!`, secret-key-first with JWT fallback, `current_ability` resolution

## Phase 3: Secret-Key Scope Authorization [US1, US3]

- [x] T003 `spree/api/app/controllers/concerns/spree/api/v3/scoped_authorization.rb` — `scoped_resource` declaration macro, `authorize_api_key_scope!`, `MissingScopedResource` guard for controllers that forget to declare
- [x] T004 `spree/api/app/models/spree/api_key_ability.rb` — `ApiKeyAbility`, substituted as `can :manage, :all` for `current_ability` when authenticated by secret key (scope check happens separately, at the controller layer)
- [x] T005 `~25 Spree::Api::V3::Admin::*Controller` classes — each declares `scoped_resource :name` or explicit `skip_scope_check!`

## Phase 4: JWT + CanCanCan Authorization [US2]

- [x] T006 `spree/api/app/controllers/concerns/spree/api/v3/admin/role_grant_guard.rb` — `RoleGrantGuard`, API-key exemption + permission-set-closure escalation check
- [x] T007 `spree/api/app/controllers/concerns/spree/api/v3/admin/auth_cookies.rb` — admin refresh-token cookie delivery (shared infrastructure with feature 016, not this feature's primary focus)

## Phase 5: Current-Principal Endpoints [US4]

- [x] T008 [P] `spree/api/app/controllers/spree/api/v3/admin/me_controller.rb` — JWT-half: describes the current admin user + serialized permission list
- [x] T009 [P] `spree/api/app/controllers/spree/api/v3/admin/api_keys_controller.rb` — secret-key-half: `#current` action, `skip_scope_check! only: :current`

## Phase 6: Existing Test Coverage

- [x] T010 [P] `spree/api/spec/controllers/spree/api/v3/scoped_authorization_spec.rb`
- [x] T011 [P] `spree/api/spec/controllers/spree/api/v3/admin/api_keys_controller_spec.rb`
- [x] T012 [P] `spree/api/spec/controllers/concerns/spree/api/v3/api_key_authentication_spec.rb`

## Notes

- Every phase above is already implemented; nothing here is scheduled work.
- Per spec.md's Migration Notes: two divergences from `docs/plans/5.5-admin-api-key-scopes.md` were found (the shipped `current_ability` is more permissive than the plan specified; the scope-storage mechanism differs from the plan) — recorded for a future owner to reconcile, not remediated as part of this migration.
- No `packages/dashboard` changes were needed — the admin SPA only reads the `/me` permission list via the standard Admin API.
</content>
