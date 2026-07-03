---

description: "Task list for Admin Users & Team — fully shipped; 6.0 Devise drop pending"
---

# Tasks: Admin Users & Team

**Status**: Phase 1 fully shipped (invite flow, roles, SPA, E2E); Phase 2 (6.0 Devise drop) pending

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models / concerns | `spree/core/app/models/spree/` and `spree/core/app/models/concerns/spree/` |
| Migrations | `spree/core/db/migrate/` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/settings/` |
| Dashboard locales | `packages/dashboard/src/locales/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core + API + SPA ✅

### Models

- [x] T001 `spree/core/app/models/concerns/spree/admin_user_methods.rb` — `has_prefix_id :admin`; `has_many :role_users`; `has_many :roles` through `role_users`; `person_name` helper; `selected_locale` attribute; `sign_in_count`, `last_sign_in_at` tracking
- [x] T002 `spree/core/app/models/spree/legacy_admin_user.rb` — default `Spree.admin_user_class`; BCrypt auth; no Devise; validates email uniqueness
- [x] T003 `spree/core/app/models/spree/role.rb` — `has_prefix_id :role`; `name string null: false`; `has_many :role_users`; unique name per store (or global)
- [x] T004 `spree/core/app/models/spree/role_user.rb` — polymorphic `user` (`user_id`, `user_type`); polymorphic `resource` (`resource_id`, `resource_type`); `belongs_to :role`; unique index on `(role_id, user_id, user_type, resource_id, resource_type)`; store-scoped by default
- [x] T005 `spree/core/app/models/spree/invitation.rb` — `has_prefix_id :inv`; `has_secure_token :token`; `acts_as_paranoid`; `belongs_to :inviter` (polymorphic); `belongs_to :invitee` (polymorphic, optional until accepted); `belongs_to :role` (optional); `accepted_at datetime`; `expires_at datetime null: false`; validates token uniqueness

### Migrations

- [x] T006 `spree_roles` table — `name string null: false`, timestamps; unique index `name`
- [x] T007 `spree_role_users` table — `role_id string null: false`, `user_id string null: false`, `user_type string null: false`, `resource_id string`, `resource_type string`, timestamps; unique index `(role_id, user_id, user_type, resource_id, resource_type)`
- [x] T008 `spree_invitations` table — `token string null: false`, `email string null: false`, `role_id string`, `inviter_id string`, `inviter_type string`, `invitee_id string`, `invitee_type string`, `accepted_at datetime`, `expires_at datetime null: false`, `deleted_at`, timestamps; unique index `token`; index `email`

### Serializers

- [x] T009 [P] `spree/api/app/serializers/spree/api/v3/admin/admin_user_serializer.rb` — `id` (admin_…), `email`, `first_name`, `last_name`, `selected_locale`, `sign_in_count`, `last_sign_in_at`, `roles` (filtered to current store: array of `{ id (role_…), name }`), `created_at`, `updated_at`
- [x] T010 [P] `spree/api/app/serializers/spree/api/v3/admin/invitation_serializer.rb` — `id` (inv_…), `email`, `role_id` (role_…), `status` (pending/accepted/expired), `expires_at`, `accepted_at`, `created_at`

### Controllers

- [x] T011 `spree/api/app/controllers/spree/api/v3/admin/admin_users_controller.rb` — `index`, `show`, `update` (roles for current store), `destroy` (remove store role assignments; no global delete); **no `create`** — invitation-only; scoped to users with role in `current_store`
- [x] T012 `spree/api/app/controllers/spree/api/v3/admin/invitations_controller.rb` — `create` (sends invite email); `show` (by token, public); `accept` member action (sets password, creates/links account, marks `accepted_at`)

### Routes

- [x] T013 Routes: `resources :admin_users, only: [:index, :show, :update, :destroy]`; `resources :invitations, only: [:create, :show]` with `member { patch :accept }`

### Specs

- [x] T014 `spree/core/spec/models/spree/role_spec.rb` — name presence; uniqueness
- [x] T015 `spree/core/spec/models/spree/invitation_spec.rb` — token generation; expiry check; accepted_at set on accept; double-accept rejected
- [x] T016 `spree/api/spec/integration/spree/api/v3/admin/admin_users_spec.rb` — list returns only current-store members; PATCH updates roles for current store only; DELETE removes store assignments
- [x] T017 `spree/api/spec/integration/spree/api/v3/admin/invitations_spec.rb` — create sends email; accept creates account; expired token rejected with 422

### Type Pipeline

- [x] T018 `bundle exec rake typelizer:generate` — `AdminAdminUser`, `AdminInvitation` types generated
- [x] T019 `cd packages/sdk && pnpm generate:zod`
- [x] T020 `bundle exec rake rswag:specs:swaggerize`

### Frontend

- [x] T021 [US1/US2/US3] `packages/dashboard/src/routes/_authenticated/$storeId/settings/staff.tsx` — invite form (email + role picker); team list with roles + last-sign-in; pending invitations section; bulk role-update actions
- [x] T022 Add i18n keys to `packages/dashboard/src/locales/en.json` under `admin.staff.*` and `admin.invitations.*`
- [x] T023 Add same keys to all other locale files (ar, de, fr, pl, zh-CN)

### E2E

- [x] T024 `packages/dashboard/e2e/invitation-acceptance.spec.ts` — send invite → follow token URL → set password → verify lands in dashboard → verify role assigned in staff list
- [x] T025 Run `pnpm test:e2e` ✅

**Checkpoint**: invite flow end-to-end works; role updates are store-scoped; expired tokens rejected ✅

---

## Phase 2: 6.0 — Devise Drop (PENDING)

Per `6.0-platform-auth.md`:

- [ ] T026 Remove Devise dependency from `Spree::LegacyAdminUser`; own JWT stack handles all auth
- [ ] T027 Update authentication strategy in `invitations_controller#accept` to use own JWT after account creation
- [ ] T028 Update `sign_in_count` / `last_sign_in_at` tracking to own auth stack (no Devise trackable module)

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No bulk role assignment API (one-at-a-time PATCH only) | Low | Acceptable for typical team sizes; bulk needed only for large organizations — can be addressed in B2B plan |
| No role-change audit log | Low | `RoleUser` has `created_at`; no update history. Add `role_change_events` table if audit trail needed |
| Devise dependency still present in 5.x | Low | By design; T026 drops it in 6.0 |
