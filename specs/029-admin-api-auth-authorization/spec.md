# Feature Specification: Admin API Auth & Authorization

**Feature Branch**: `029-admin-api-auth-authorization`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing code (brownfield migration) — no original feature request survives; behavior below is inferred from `spree/api` (concerns, controllers, models) and `spree/core`'s `Spree::ApiKey`. Narrower sibling of `specs/016-authentication-store-and-admin/spec.md`, which covers the general login/JWT/refresh-token/invitation strategy shared by Store and Admin; this spec focuses specifically on **how a single Admin API controller supports two different authorization mechanics** — secret-key scopes and JWT+CanCanCan — without either one leaking into the other's code path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Secret API key request authorized by scope (Priority: P1)

An integration calls an Admin API endpoint (e.g. `PATCH /api/v3/admin/orders/:id`) with `X-Spree-API-Key: sk_...`. `AdminAuthentication#authenticate_admin!` finds the key by its HMAC digest, confirms it belongs to the current store, and sets `@current_api_key`. `ScopedAuthorization#authorize_api_key_scope!` then maps the action to `write_orders` (write, because `update` isn't `index`/`show`) and checks `@current_api_key.has_scope?('write_orders')`. If the key lacks the scope, the request is rejected `403` before any model code runs; CanCanCan is bypassed entirely via `Spree::ApiKeyAbility#manage(:all)`.

**Why this priority**: This is the entire reason the feature exists — server-to-server integrations need per-resource authorization without a user or role behind them.

**Independent Test**: Create a secret key with only `read_orders`, `PATCH` an order → `403` with `code: access_denied`, `details.required_scope: "write_orders"`. Create a key with `write_orders` (or `write_all`) → the same request succeeds.

**Acceptance Scenarios**:

1. **Given** a secret key with `read_orders` only, **When** it calls `PATCH /orders/:id`, **Then** the response is `403` naming `write_orders` as the missing scope, and no CanCanCan rule is evaluated.
2. **Given** a secret key with `write_all`, **When** it calls any `write_*`-mapped action on any resource, **Then** `has_scope?` returns true via the `write_all` alias, expanded at check time (not stored).
3. **Given** a secret key with `read_orders` only, **When** it calls `GET /orders/:id`, **Then** the request succeeds (`read_` action kind for `index`/`show`).

---

### User Story 2 - JWT admin request authorized by CanCanCan (Priority: P1)

An admin user's browser session (via `packages/dashboard`) calls the same `PATCH /api/v3/admin/orders/:id` with `Authorization: Bearer <jwt>`. No `@current_api_key` is set, so `ScopedAuthorization#authorize_api_key_scope!` returns immediately (`return unless current_api_key`) and `AdminAuthentication#current_ability` falls through to the real `Spree::Ability`, which resolves the admin's `Spree::Role`s/`PermissionSets` and runs the standard `authorize!` / `accessible_by` checks.

**Why this priority**: This is the authorization path every human admin session uses; it must never be weakened by the presence of the scope-check concern on the same controller.

**Independent Test**: Log in as an admin with a role lacking order-management permission sets, `PATCH /orders/:id` → `403` from CanCanCan (not from `ScopedAuthorization`, which never ran). Log in as an admin with the right role → succeeds.

**Acceptance Scenarios**:

1. **Given** a JWT-authenticated admin with no role on the current store, **When** they call any admin endpoint, **Then** `require_store_membership!` rejects the request `403` before CanCanCan or scope checks run.
2. **Given** a JWT-authenticated admin with a valid store role, **When** they call an endpoint their role's permission sets don't cover, **Then** CanCanCan denies it — scopes play no part in the decision.
3. **Given** both a JWT and a secret key are somehow presented on the same request, **When** authorization resolves, **Then** the JWT user wins (`current_ability` checks `current_user` first) and CanCanCan governs, per the documented precedence comment in `AdminAuthentication`.

---

### User Story 3 - New admin controller declares its scope (or opts out) (Priority: P2)

A developer adds a new `Spree::Api::V3::Admin::FoosController`. If it inherits scope checking (default) and does not call `scoped_resource :foos`, the first API-key request to hit it raises `ScopedAuthorization::MissingScopedResource` — a fail-closed error naming the controller class, not a silent allow. The developer fixes it by adding `scoped_resource :foos` (mapping to `read_foos`/`write_foos` from `Spree::ApiKey::SCOPES`) or, for exempt endpoints (auth, `/me`, `/tags`, `/direct_uploads`), calling `skip_scope_check!` (whole controller) or `skip_scope_check! only: :index` (single action).

**Why this priority**: Enforces the "every new admin controller must declare a scope" constraint from `docs/plans/5.5-admin-api-key-scopes.md` mechanically rather than relying on code review alone.

**Independent Test**: Add a controller with no `scoped_resource` declaration and no `skip_scope_check!`, hit it with any secret key → raises `MissingScopedResource` naming the controller. Add `scoped_resource :foos` → the same request now evaluates `has_scope?('read_foos'/'write_foos')` correctly.

**Acceptance Scenarios**:

1. **Given** a controller with neither `scoped_resource` nor `skip_scope_check!`, **When** a secret-key request reaches it, **Then** `MissingScopedResource` is raised identifying the offending controller.
2. **Given** `Admin::ApiKeysController` (`scoped_resource :api_keys`, `skip_scope_check! only: :current`), **When** a secret key calls `GET /api_keys/current` (self-describing the calling key), **Then** the scope check is skipped for that one action while `index`/`create`/etc. remain scope-gated.
3. **Given** a nested controller like `Orders::PaymentsController`, **When** it declares `scoped_resource :payments` (not `:orders`), **Then** its own scope, independent of its parent route, is what's checked.

---

### User Story 4 - Two parallel "describe the current credential" endpoints (Priority: P3)

`GET /api/v3/admin/me` (JWT half) and `GET /api/v3/admin/api_keys/current` (secret-key half) each answer "who/what is calling right now," but for mutually exclusive credential types. `MeController#show` 404s (`record_not_found`, pointing at the key endpoint) if the request has no `current_user` — i.e. it was authenticated by a secret key instead. `MeController` also serializes CanCanCan's rule set (`serialize_permissions`) so the SPA can pre-hide UI, explicitly noting this is UX-only: the server still enforces via CanCanCan/`ScopedAuthorization` regardless of what the client renders.

**Why this priority**: Supports SPA UX (permission-aware UI) but nothing else in authorization depends on it.

**Independent Test**: Call `/me` with a JWT → returns user + flattened permission rules. Call `/me` with a secret key only → `404`. Call `/api_keys/current` with a secret key → returns the key + its scopes.

**Acceptance Scenarios**:

1. **Given** a JWT-authenticated request, **When** `GET /me` is called, **Then** the response includes `user` and a `permissions` array of `{ allow, actions, subjects, has_conditions }` derived from `current_ability`'s CanCanCan rules, in rule order (last-match-wins semantics preserved for the frontend matcher).
2. **Given** a secret-key-only request (no `current_user`), **When** `GET /me` is called, **Then** the response is `404 record_not_found`, not a 500 from serializing `nil`.
3. **Given** a rule with per-record conditions (a scope or block), **When** it is serialized, **Then** `has_conditions: true` is set instead of attempting to serialize the condition itself — the SPA shows the action optimistically and handles a resulting 403.

---

### Edge Cases

- A secret key's `scopes` are immutable after creation (`ApiKey#scopes_immutable` validation, fires whenever `scopes_changed?` on a persisted record) — re-scoping means minting a new key and revoking the old one, mirroring Stripe/GitHub/AWS.
- `has_scope?` implements alias expansion at check time only: `write_x` implies `read_x`; `write_all`/`read_all` are never stored expanded, so re-toggling a key's tier later doesn't require rewriting stored scopes (moot in practice since scopes are immutable, but the expansion logic itself stays check-time for auditability).
- `RoleGrantGuard#reject_without_role_management!` explicitly treats API-key principals as exempt from the CanCanCan "can create a RoleUser" gate (`scope_limited_principal?` short-circuits it) — for API keys, `ScopedAuthorization` is the only gate on granting roles, but a key has no `Spree::Role` to lend, so in practice a key can only grant roles whose permission-set closure is empty.
- `authorize_api_key_scope!` runs as a `before_action` on every request through `ScopedAuthorization`, even when `current_api_key` is nil (JWT path) — it exits immediately via `return unless current_api_key`, so the concern is present on every admin controller but a no-op for JWT sessions.
- Scope validation (`validate_known_scopes`) only runs when scopes are new or changed (`scopes_enforceable?`) — deliberately so that revoking a key minted under a since-retired scope name doesn't fail validation on the revoke itself.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST authorize secret-key-authenticated Admin API requests exclusively via `read_<resource>`/`write_<resource>` scopes (`Spree::ApiKey::SCOPES`, `ScopedAuthorization#authorize_api_key_scope!`), bypassing CanCanCan for that decision.
- **FR-002**: System MUST authorize JWT-authenticated Admin API requests exclusively via CanCanCan (`Spree::Ability` + `Spree::PermissionSets::*`), leaving `ScopedAuthorization` a no-op for those requests.
- **FR-003**: System MUST map `index`/`show` actions to the `read_*` scope and every other action (including custom member actions) to the `write_*` scope for a controller's declared `scoped_resource`, unless a controller overrides `action_kind`.
- **FR-004**: System MUST require every Admin API controller reachable by a secret key to declare `scoped_resource :name` or explicitly `skip_scope_check!` (whole-controller or `only: [...]`); a controller doing neither MUST raise `ScopedAuthorization::MissingScopedResource` rather than silently allow or silently deny.
- **FR-005**: System MUST substitute `Spree::ApiKeyAbility` (`can :manage, :all`) as `current_ability` for secret-key-authenticated requests, so CanCanCan-based collection scoping (`accessible_by`) doesn't accidentally narrow results the scope check has already authorized at the resource level.
- **FR-006**: System MUST make `Spree::ApiKey#scopes` immutable after creation for secret keys — any attempt to change `scopes` on a persisted secret key MUST fail validation.
- **FR-007**: System MUST validate `scopes` against the fixed `SCOPES` vocabulary whenever scopes are set on create or explicitly changed, rejecting unknown scope names.
- **FR-008**: System MUST expand `read_all`/`write_all` at check time in `has_scope?` (never persisted in expanded form), and MUST treat any stored `write_<resource>` as implicitly satisfying `read_<resource>`.
- **FR-009**: System MUST provide two separate, credential-exclusive "describe current principal" endpoints — `GET /api/v3/admin/me` (JWT; 404s without a `current_user`) and `GET /api/v3/admin/api_keys/current` (secret key) — neither serving the other credential type's request.
- **FR-010**: System MUST serialize CanCanCan's resolved rule set for the JWT admin (`MeController#serialize_permissions`) as UX-only data; the underlying authorization decision on every subsequent request MUST still be enforced server-side, not trusted from client state.
- **FR-011**: System MUST let nested/child controllers declare a `scoped_resource` independent of their parent route segment (e.g., `Orders::PaymentsController` → `:payments`, not `:orders`).
- **FR-012**: System MUST exclude credential-management scopes (`read_api_keys`/`write_api_keys`) from the `settings` scope bucket, keeping API key administration separately grantable.

### Key Entities

- **`Spree::ApiKey`**: `belongs_to :store`; `key_type` (`publishable`/`secret`); secret keys carry an immutable `scopes` array (validated against `SCOPES`), HMAC-digested `token_digest`/`token_prefix` (never a recoverable plaintext), `revoked_at`/`revoked_by`.
- **`Spree::Api::V3::ScopedAuthorization`** (concern): Per-controller `scoped_resource` class declaration + `before_action :authorize_api_key_scope!`; owns the `read_*`/`write_*` action-kind mapping and the fail-closed `MissingScopedResource` error.
- **`Spree::ApiKeyAbility`**: A permissive `CanCan::Ability` (`can :manage, :all`) substituted as `current_ability` for API-key principals so CanCanCan-based collection filters don't conflict with the scope check being the real gate.
- **`Spree::Api::V3::AdminAuthentication`** (concern): Resolves which credential authenticated the request (secret key first, then JWT), sets `@current_api_key`/`current_user` accordingly, and picks `current_ability` based on which is present.
- **`Spree::Api::V3::Admin::RoleGrantGuard`** (concern): Cross-cutting rule that treats API-key principals as exempt from the CanCanCan role-management gate but still bounds what roles they can grant via permission-set closure.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::ApiKey` (`SCOPES`, `has_scope?`, immutability/known-scope validations, HMAC digest lookup) |
| `spree/api` (Store/Admin API v3) | Yes | `Spree::Api::V3::ScopedAuthorization`, `Spree::Api::V3::AdminAuthentication`, `Spree::Api::V3::Admin::{RoleGrantGuard, AuthCookies}`, `Spree::ApiKeyAbility`, `Admin::MeController`, `Admin::ApiKeysController#current`, every `Admin::*Controller`'s `scoped_resource`/`skip_scope_check!` declaration |
| `packages/dashboard` (admin SPA) | No | Consumes `/me`'s `permissions` array for UX-only optimistic hiding; no authorization logic lives here |
| `packages/admin-sdk` | Yes (generated types only) | `AdminUser`/permission-rule response shapes; secret-key scope management surfaced via the API keys admin UI, not hand-written client logic |
| `docs/plans/` | Yes (already governs this area) | `5.5-admin-api-key-scopes.md` — this feature is that plan's as-built state |

### API Contract *(include if feature touches spree/api)*

- **Endpoints**: All `spree/api/app/controllers/spree/api/v3/admin/**` endpoints (authorization mechanics apply uniformly); specifically documented here: `GET /api/v3/admin/me`, `PATCH /api/v3/admin/me`, `GET /api/v3/admin/api_keys/current`.
- **Serializer fields (read)**: `/me` — `user` (`Spree.api.admin_admin_user_serializer`) + `permissions: [{ allow, actions, subjects, has_conditions }]`. `/api_keys/current` — the requesting key's own record including `scopes`.
- **Auth**: Every Admin API endpoint (except `/auth/*`, `/me`, `/tags`, `/direct_uploads`) requires either a secret API key satisfying its declared `scoped_resource`'s `read_*`/`write_*` scope, or an admin JWT satisfying CanCanCan. The two mechanisms never both apply to the same request — the concern precedence is secret key first, JWT fallback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of `Admin::*Controller` classes reachable by a secret key resolve a `scoped_resource` (directly or inherited) or an explicit `skip_scope_check!` — `MissingScopedResource` fails closed for any that don't, rather than silently allowing.
- **SC-002**: A secret key request without the required scope is rejected `403` before any model read/write occurs, and the error names the missing scope in `details.required_scope`.
- **SC-003**: A JWT admin request is never affected by `ScopedAuthorization` (verified by: scope checks are a no-op whenever `current_api_key` is absent).
- **SC-004**: An attempt to change `scopes` on an already-persisted secret key always fails validation — the only way to change a key's authority is issuing a new key.

## Assumptions

- The scope vocabulary (`Spree::ApiKey::SCOPES`) is assumed complete for all currently-shipped Admin API resources; new resources are expected to extend it per `docs/plans/5.5-admin-api-key-scopes.md`'s "add a scope when a partner realistically wants read without write" heuristic, not to invent per-action scopes.
- `Spree::ApiKeyAbility#manage(:all)` is assumed intentional (not a placeholder) — it exists specifically so `accessible_by` doesn't double-gate what `ScopedAuthorization` already gated, per the comment in `spree/api/app/models/spree/api_key_ability.rb`.
- The plan document (`5.5-admin-api-key-scopes.md`) describes an earlier design (`serialize :scopes, type: Array, coder: JSON`, `current_ability` falling back to `@current_api_key.created_by`) that differs from what shipped — see Migration Notes.

## Migration Notes

Gaps and discrepancies surfaced during reverse-engineering:

1. **Shipped `current_ability` diverges from the plan doc.** `docs/plans/5.5-admin-api-key-scopes.md` specifies `current_ability` falling back to `Spree::Ability.new(@current_api_key&.created_by, ...)` — i.e., CanCanCan still runs, scoped to whatever user created the key, for per-record filtering. What shipped instead (`Spree::Api::V3::AdminAuthentication#current_ability`) substitutes a fully permissive `Spree::ApiKeyAbility` (`can :manage, :all`) with no reference to `created_by` at all. This is a stronger simplification than the plan proposed — per-record CanCanCan filtering for API-key requests no longer exists; `ScopedAuthorization` is the sole gate, at resource granularity only. Flagged because it changes the security model described in the plan (no per-record restriction for a key even if its creator had a limited role) without an accompanying plan update.
2. **Storage mechanism also diverges from the plan.** The plan specifies `serialize :scopes, type: Array, coder: JSON` on a `text` column. The shipped model uses `attribute :scopes, default: []` with a custom `scopes=` normalizer, implying a `jsonb`/`json` column (per this repo's cross-DB JSON convention) rather than a serialized text column. Functionally equivalent from the scope-check's perspective, but the plan's migration snippet is stale.
3. **Constant naming**: the plan calls it `KNOWN_SCOPES`; the shipped model calls it `SCOPES`. Purely cosmetic, but anyone grepping the plan for the constant name won't find it.
4. **`current_ability` for API keys carries no note of `created_by`-based scoping ever having been tried and reverted** — no changelog/comment explains the divergence from the plan; presumed a design simplification made during implementation without updating the plan doc's "Design Details" section.
5. **Per-controller `scoped_resource` coverage was not exhaustively verified controller-by-controller** in this migration (source scan showed a handful of controllers — base classes and some nested resource controllers — without their own declaration, which is expected if they inherit one from a concrete parent/subclass rather than the abstract base). `MissingScopedResource`'s fail-closed behavior is the actual safety net here, not manual audit; SC-001 should be checked by a spec assertion (e.g., iterating all `Admin::*Controller` descendants) rather than assumed from this document.
6. **`RoleGrantGuard`'s API-key exemption is easy to misread as "API keys can grant any role."** In practice a key can only grant roles whose permission-set closure is empty, because `Spree.permissions.permission_sets_for_roles` for a key (no `Spree::Role`s of its own) yields an empty caller set — `grantable_within?` then only passes for roles with an empty closure. This is correct but implicit; worth a code comment or spec making the actual bound explicit rather than relying on the emptiness of an unrelated lookup.
