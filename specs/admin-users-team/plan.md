# Implementation Plan: Admin Users & Team

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped; 6.0 Devise drop pending

---

## Summary

Admin user management uses an invitation-only flow: existing admins send invitations via email; invitees follow a token link to set their password and create their account. Roles are assigned per-store via `Spree::RoleUser` (polymorphic on both user and resource). The Admin API has no POST on admin users (creation is invitation-only); PATCH updates store-scoped roles; DELETE removes store role assignments. The SPA has a staff settings page with the invite flow and role picker. An E2E test covers the full invitation lifecycle.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Database** | PostgreSQL (primary) · MySQL · SQLite |
| **Backend testing** | RSpec + Factory Bot · rswag |
| **Frontend testing** | Vitest + MSW · Playwright (E2E) |
| **Auth** | Cookie-based JWT (5.5 refresh token shipped) |
| **Scope** | Fully shipped; 6.0 Devise drop pending |

---

## Key Decisions

1. **Invitation-only account creation.** No `POST /admin_users` — accounts are created only via invitation acceptance. This closes the self-registration attack surface and ensures all admin accounts are traceable to an inviting admin.

2. **Roles are store-scoped via `RoleUser.resource`.** `RoleUser` has a polymorphic `resource` (currently `Spree::Store`). PATCH on an admin user only updates role assignments for the current store — other stores' assignments are untouched. DELETE removes only the current store's role assignments (the account itself is preserved).

3. **`RoleUser` user polymorphism for future extensibility.** Both `Spree::User` (customer) and admin user types can hold roles via the same join table. This supports the B2B `CompanyContact` role assignment planned in `6.0-channels-catalogs-b2b.md`.

4. **`has_secure_token :token` on Invitation.** Rails generates a cryptographically random token. Token is single-use (accepted at most once) and expires via `expires_at`. Soft-delete via `acts_as_paranoid` preserves audit history of invitations.

5. **`AdminUserMethods` concern keeps the model abstract.** The concern handles prefix ID, associations, and role helpers. `Spree.admin_user_class` is the indirection point — core ships `Spree::LegacyAdminUser`; hosts can swap in a Devise admin model.

---

## Constitution Check

- [x] **API-First**: Admin API precedes SPA
- [x] **Read/Write Symmetry**: `first_name`, `last_name`, `selected_locale`, `role_ids` serialized and accepted
- [x] **Prefixed IDs**: `admin_…` (admin user), `role_…` (role), `inv_…` (invitation)
- [x] **Serializer Hierarchy**: `Admin::AdminUserSerializer` (admin-only)
- [x] **Type Pipeline**: Typelizer + Zod regen done
- [x] **Security**: CanCanCan guards; only store-scoped members returned; cannot self-delete
- [x] **Namespace**: `Spree::Role`, `Spree::RoleUser`, `Spree::Invitation`, `Spree::AdminUserMethods`
- [x] **Plan Conflicts**: `6.0-platform-auth.md` governs Devise drop + own JWT stack; `5.5-admin-auth-cookie-refresh.md` governs httpOnly refresh cookie (shipped in 5.5)

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/concerns/spree/admin_user_methods.rb            ← admin_ prefix, role associations
spree/core/app/models/spree/legacy_admin_user.rb                      ← default admin user (BCrypt)
spree/core/app/models/spree/role.rb                                   ← role_ prefix
spree/core/app/models/spree/role_user.rb                              ← polymorphic user + resource join
spree/core/app/models/spree/invitation.rb                             ← inv_ prefix, has_secure_token, paranoid

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/admin_user_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/invitation_serializer.rb

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/admin_users_controller.rb   ← no POST; PATCH/DELETE store-scoped
spree/api/app/controllers/spree/api/v3/admin/invitations_controller.rb

# Frontend (✅ shipped)
packages/dashboard/src/routes/_authenticated/$storeId/settings/staff.tsx
packages/dashboard/e2e/invitation-acceptance.spec.ts
```

---

## Phase 1: Core + API + SPA (✅ Complete)

- `Role`, `RoleUser` (polymorphic), `Invitation` (has_secure_token, paranoid)
- `AdminUserMethods` concern + `LegacyAdminUser`
- Admin API: list/show/patch/delete admin users; create/accept invitations
- SPA: staff settings page; invite flow with role picker
- E2E: full invitation lifecycle (`invitation-acceptance.spec.ts`)

---

## Phase 2: 6.0 — Devise Drop (PENDING)

Per `6.0-platform-auth.md`:

- Remove Devise dependency from admin user model
- Own JWT authentication stack (strategy already built; refresh token in httpOnly cookie shipped in 5.5)
- `Spree.admin_user_class` constant preserved; internal rename may occur

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Polymorphic `RoleUser` (user + resource) | Admin users, customers, and future company contacts all need role assignments scoped to different resources | Separate join tables per user type would duplicate the role-checking logic across all contexts |
| Invitation-only creation | Prevents self-registration attacks; every admin is traceable | Open POST /admin_users would require email verification, rate limiting, and CAPTCHA — invitation flow is simpler and more secure |
