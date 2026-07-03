# Feature Specification: Admin Users & Team

**Feature Branch**: `main` (fully shipped; 6.0 Devise drop pending)

**Created**: 2026-06-30

**Status**: migrated

**Active Plans**: `6.0-platform-auth.md`, `5.5-admin-auth-cookie-refresh.md`

---

## User Scenarios & Testing

### User Story 1 — Invite Team Members (Priority: P1)

A store owner invites colleagues to the admin dashboard via email. The invite flow: owner sends an invitation → invitee receives email with a token link → invitee sets their password and account name → invitee lands in the dashboard with assigned roles.

**Why this priority**: New staff cannot access the admin without an invitation; this is the only entry point for new admin users.

**Independent Test**: Admin POSTs to `/api/v3/admin/invitations` with `{ email: "jane@example.com", role_id: "role_…" }`. Jane receives an email. She follows the link, sets a password, and lands on the dashboard. Admin lists `/api/v3/admin/admin_users` and Jane appears.

**Acceptance Scenarios**:

1. **Given** an email not yet in the system, **When** admin sends an invite, **Then** an `Invitation` (`inv_…`) is created and email is sent
2. **Given** an invitation token, **When** invitee submits name + password, **Then** account is created and invitation is marked accepted
3. **Given** an expired invitation, **When** invitee tries to use the token, **Then** 422 is returned with expiry message
4. **Given** an already-accepted invitation, **When** token is used again, **Then** 422 is returned

---

### User Story 2 — Manage Team Roles (Priority: P1)

Admin assigns roles to team members per store. Roles control CanCanCan permissions. Default roles: `admin`, `customer_support`, `fulfillment`.

**Why this priority**: Role-based access prevents support agents from accessing financial data or modifying store configuration.

**Independent Test**: Admin PATCHes `/api/v3/admin/admin_users/:id` with `{ role_ids: ["role_…"] }`. The target user's roles for the current store are updated. Old roles for that store are replaced.

**Acceptance Scenarios**:

1. **Given** a team member with `customer_support` role, **When** they access order pages, **Then** financial tabs are hidden per CanCanCan
2. **Given** a team member, **When** admin updates their roles, **Then** only roles for the current store are affected (roles on other stores are unchanged)
3. **Given** a team member, **When** removed from the team (`DELETE`), **Then** their role assignments for the current store are removed (global account preserved)

---

### User Story 3 — View & Filter Team Members (Priority: P2)

Admin lists all team members for the current store with their roles, last sign-in, and invitation status.

**Acceptance Scenarios**:

1. **Given** team members with different roles, **When** listing, **Then** each shows their current roles for this store
2. **Given** a pending (not yet accepted) invitation, **When** listed, **Then** it appears with `status: pending`
3. **Given** a revoked team member, **When** listing with default scope, **Then** they are excluded

---

### Edge Cases

- What if the invited email already has an account? → Invitation links to the existing account; no duplicate user created
- What if admin deletes their own account? → Guarded at controller level; cannot self-delete
- _(6.0)_ Devise dropped per `6.0-platform-auth.md`; authentication moves to own JWT stack; `AdminUserMethods` concern remains

---

## Requirements

### Functional Requirements

- **FR-001**: AdminUser model via `Spree.admin_user_class`; default `Spree::LegacyAdminUser`; prefix `admin_`
- **FR-002**: `Spree::Role` — `name`, prefix `role_`; many-to-many with admin users via `Spree::RoleUser`
- **FR-003**: `Spree::RoleUser` — polymorphic `user` (AdminUser or User), polymorphic `resource` (Store, Vendor, etc.); store-scoped by default
- **FR-004**: `Spree::Invitation` — prefix `inv_`; `has_secure_token :token`; paranoid soft-delete; `accepted_at`, `expires_at`; `belongs_to :inviter` + `belongs_to :invitee` (polymorphic)
- **FR-005**: `admin_users_controller` — no POST (invitation-only); PATCH updates roles for current store; DELETE removes store role assignments
- **FR-006**: `invitations_controller` — POST creates invitation + sends email; GET shows invitation by token; PATCH accepts invitation (sets password, creates user)
- **FR-007**: All admin user IDs prefixed `admin_`; role IDs `role_`; invitation IDs `inv_`
- **FR-008**: E2E test: `packages/dashboard/e2e/invitation-acceptance.spec.ts` covers full invite lifecycle
- **FR-009**: _(6.0)_ Devise dropped; authentication via own JWT stack per `6.0-platform-auth.md`

### Key Entities

- **AdminUser** (`Spree::LegacyAdminUser` or custom): email, first/last name, `selected_locale`. Prefix: `admin_`.
- **Role** (`Spree::Role`): `name`. Prefix: `role_`.
- **RoleUser** (`Spree::RoleUser`): polymorphic user + polymorphic resource (Store). No prefix.
- **Invitation** (`Spree::Invitation`): token, `inviter`, `invitee` (polymorphic), `role_id`, `accepted_at`, `expires_at`. Prefix: `inv_`.

---

## Backend Requirements

### Data Model

- **Table**: `spree_roles` — `name string null: false`, timestamps
- **Table**: `spree_role_users` — `role_id string null: false`, `user_id string null: false`, `user_type string null: false`, `resource_id string`, `resource_type string`, timestamps; unique index on `(role_id, user_id, user_type, resource_id, resource_type)`
- **Table**: `spree_invitations` — `token string null: false`, `email string null: false`, `role_id string`, `inviter_id`, `inviter_type`, `invitee_id`, `invitee_type`, `accepted_at datetime`, `expires_at datetime null: false`, `deleted_at`, timestamps

### API Surface

#### Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/admin_users` | List team members for store |
| GET | `/api/v3/admin/admin_users/:id` | Show team member |
| PATCH | `/api/v3/admin/admin_users/:id` | Update roles for current store |
| DELETE | `/api/v3/admin/admin_users/:id` | Remove from current store |
| GET | `/api/v3/admin/roles` | List available roles |
| POST | `/api/v3/admin/invitations` | Send invitation |
| GET | `/api/v3/admin/invitations/:token` | Show invitation by token |
| PATCH | `/api/v3/admin/invitations/:token/accept` | Accept invitation + set password |

### Serializer Fields

**Admin AdminUserSerializer**:
- `id` (admin_…), `email`, `first_name`, `last_name`, `selected_locale`, `sign_in_count`, `last_sign_in_at`, `roles` (array of `{ id, name }` filtered to current store), `created_at`, `updated_at`

**Admin InvitationSerializer**:
- `id` (inv_…), `email`, `role_id`, `status` (pending/accepted/expired), `expires_at`, `accepted_at`, `created_at`

### Authorization

- CanCanCan: `can :manage, Spree.admin_user_class`; `can :manage, Spree::Invitation`
- Store-scoped: only members with roles on current store are returned

---

## Frontend Requirements

### SPA Routes

- `packages/dashboard/src/routes/_authenticated/$storeId/settings/staff.tsx` — invite flow, role picker, team list with bulk actions

### i18n Keys

Under `admin.staff.*` and `admin.invitations.*` in all locale files.

---

## E2E Coverage

- `packages/dashboard/e2e/invitation-acceptance.spec.ts` — full invite lifecycle: send invite → follow token → set password → verify lands in dashboard → verify role assigned

---

## Success Criteria

- **SC-001**: Admin can invite a new team member; invitee receives email, accepts, and lands in dashboard with correct role
- **SC-002**: Role updates for a user only affect the current store; other store roles are preserved
- **SC-003**: Removing a team member removes their store role assignments without deleting their account
- **SC-004**: Expired invitation tokens are rejected with 422
- **SC-005**: _(6.0)_ Devise removed; JWT stack handles authentication per `6.0-platform-auth.md`

---

## Assumptions

- Roles are predefined in core; custom roles can be added via `Spree::Role.create`
- `RoleUser` resource polymorphism supports future Vendor/Account scoping (B2B plan)
- Email delivery for invitations uses existing mailer infrastructure
