# Feature Specification: Authentication (Store + Admin)

**Feature Branch**: `016-authentication-store-and-admin`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing code (brownfield migration) — no original feature request survives; behavior below is inferred from `spree/core`, `spree/api`, `spree/admin`, and `packages/dashboard-core` source.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Customer logs into the Store API (Priority: P1)

A storefront customer submits email + password to `POST /api/v3/store/auth/login`. On success they receive a short-lived JWT access token (1h default) and a long-lived opaque refresh token (30 days) in the JSON body, which the storefront client stores itself and uses to call `POST /api/v3/store/auth/refresh` / `POST /api/v3/store/auth/logout`.

**Why this priority**: Customer login gates every authenticated storefront action (order history, saved addresses, checkout as a known customer).

**Independent Test**: `POST /api/v3/store/auth/login` with valid `email`/`password` returns `{ token, refresh_token, user }`; wrong password returns 401 with `authentication_failed`; refreshing with the returned `refresh_token` rotates it (old token stops working) and returns a new JWT.

**Acceptance Scenarios**:

1. **Given** a registered customer, **When** they POST valid credentials to `/api/v3/store/auth/login`, **Then** they receive a JWT (`aud: store_api`) and a `Spree::RefreshToken`.
2. **Given** an expired or unknown refresh token, **When** the client POSTs it to `/refresh`, **Then** the request fails with `invalid_refresh_token` (401).
3. **Given** a valid refresh token, **When** the client POSTs it to `/logout`, **Then** the token is destroyed even without a valid access JWT (the refresh token itself is the credential).

---

### User Story 2 - Admin logs into the Admin API / SPA (Priority: P1)

An admin user submits email + password to `POST /api/v3/admin/auth/login`. On success they receive a JWT (`aud: admin_api`, 5-minute TTL) in the response body and a refresh token delivered as an `HttpOnly` signed cookie scoped to `/api/v3/admin/auth`. `packages/dashboard-core`'s `AuthProvider` schedules a silent refresh ~30s before expiry and retries once transparently on a 401.

**Why this priority**: This is the sole entry point into the admin SPA and every Admin API JWT session; nothing else in admin auth matters if login is broken.

**Independent Test**: Log in via the SPA, observe the access token held only in memory (`adminClient.setToken`) and the refresh token never readable from JS (`HttpOnly` cookie); wait past the scheduled interval and confirm a silent `/refresh` call keeps the session alive.

**Acceptance Scenarios**:

1. **Given** correct admin credentials, **When** POSTed to `/api/v3/admin/auth/login`, **Then** the response sets a signed `HttpOnly` refresh cookie (path-scoped, `SameSite=Lax` in dev / `None; Secure` in prod) and returns a JWT + serialized admin user.
2. **Given** an authenticated admin with no role on the current store, **When** they call any admin endpoint via JWT, **Then** the request is rejected 403 (`current_user_member_of_store?` check) — API-key principals are exempt (already store-bound).
3. **Given** a request authenticated by a `sk_` secret key instead of a JWT, **When** it hits an admin endpoint, **Then** authorization is scope-based (`ScopedAuthorization`) rather than CanCanCan, and `current_ability` grants `ApiKeyAbility#manage(:all)` so scope checks are the only gate.

---

### User Story 3 - Admin invites a teammate and they accept (Priority: P2)

An existing admin creates a `Spree::Invitation` (email + role) scoped to a resource (typically the current `Store`). The invitee receives a token-bearing link; `GET /api/v3/admin/auth/invitations/:id/lookup?token=...` previews it, and `POST /api/v3/admin/auth/invitations/:id/accept?token=...` either authenticates an existing admin account (by password) or creates a new one (requiring a password), then marks the invitation accepted and grants the role via `RoleUser`.

**Why this priority**: Onboarding new staff is common but not on the critical path of every request the way login is.

**Independent Test**: Create an invitation, call `lookup` with the right token (succeeds) and a wrong token (404, indistinguishable from "not found"), then `accept` with a password and confirm a `RoleUser` is created and a session (JWT + refresh cookie) is issued immediately.

**Acceptance Scenarios**:

1. **Given** a pending, non-expired invitation, **When** `accept` is called with the correct token and a password, **Then** the invitation transitions `pending → accepted`, a `Spree::RoleUser` is created for the granted role, and `invitation.accepted` is published.
2. **Given** an invitation whose token doesn't match or that has expired, **When** `lookup` or `accept` is called, **Then** the response is `404 record_not_found` — expired/wrong-token and truly-missing invitations are indistinguishable to the caller by design.
3. **Given** an invitation granting the literal `admin` role, **When** the inviting caller does not themselves hold the `admin` role on the current store, **Then** the grant is rejected (`RoleGrantGuard#reject_admin_role_grant!`) regardless of the invitee.

---

### User Story 4 - Pluggable authentication strategies and OAuth identities (Priority: P3)

Both Store and Admin auth controllers resolve a `provider` param (default `"email"`) against a `Spree::Authentication::StrategyRegistry` (`Spree.store_authentication_strategies` / `Spree.admin_authentication_strategies`), instantiate the matching `Strategies::BaseStrategy` subclass, and call `#authenticate`. The shipped strategy is `EmailPasswordStrategy` (Devise `valid_password?`, falling back to `has_secure_password`'s `#authenticate`). `Spree::UserIdentity` exists as an OAuth-identity join model (`find_or_create_from_oauth`) for integrators adding non-password strategies (e.g. Google, Auth0), but no OAuth strategy ships in core.

**Why this priority**: Extensibility matters for integrators but nothing in core depends on a second strategy shipping.

**Independent Test**: Register a fake strategy under a new key via `Spree.store_authentication_strategies.add(:fake, FakeStrategy)`, POST `{ provider: "fake", ... }` to `/auth/login`, and confirm it is dispatched instead of `EmailPasswordStrategy`.

**Acceptance Scenarios**:

1. **Given** an unregistered `provider` value, **When** POSTed to either auth login endpoint, **Then** the response is `400 invalid_provider`.
2. **Given** a valid OAuth payload for a first-time user, **When** `find_or_create_from_oauth` runs, **Then** a new `user_class` record is created with a random password and a linked `Spree::UserIdentity`.
3. **Given** a repeat OAuth login for an existing identity, **When** `find_or_create_from_oauth` runs, **Then** the existing identity's tokens/info are refreshed rather than creating a duplicate.

---

### Edge Cases

- Rate limiting on login/refresh is IP-keyed only at the API v3 layer (`rate_limit ... by:` defaults to the Rack `rate_limit` gem's per-IP default) — there is no per-email lockout bucket in `spree/api`, unlike the legacy `spree/admin` Devise flow (`AuthRateLimiting`), which buckets by **both** IP and normalized email. See Migration Notes.
- An admin JWT with no store membership is rejected even though the JWT itself is valid and unexpired — membership is re-checked per request, not baked into the token.
- Secret-key requests never populate `current_user`; `AdminAuthentication#current_ability` explicitly falls back to `ApiKeyAbility` (`can :manage, :all`) so per-record CanCanCan checks (e.g. `accessible_by`) don't accidentally deny an API-key-authenticated request whose real gate is `ScopedAuthorization`.
- `RoleGrantGuard` blocks not just the literal `admin` role but any custom role whose permission-set closure exceeds the caller's own — closing the "differently-named SuperUser-equivalent role" loophole.
- Invitation `accept` for an *existing* admin account requires the submitted `password` to match that account (`authenticate_existing`) — accepting an invitation does not silently take over an existing account.
- Store API refresh tokens are returned in the JSON response body (not a cookie) and must be persisted by the storefront client itself; Admin API refresh tokens are never exposed to JS at all. This is an intentional but easy-to-miss asymmetry — see Migration Notes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST authenticate Store API customers and Admin API admin users via a pluggable strategy dispatched by a `provider` request param, defaulting to `"email"` (`Spree::Authentication::StrategyRegistry`, `Spree.store_authentication_strategies` / `Spree.admin_authentication_strategies`).
- **FR-002**: System MUST issue short-lived JWTs scoped by `aud` claim (`store_api` vs `admin_api`) so a token minted for one surface cannot authenticate the other (`JwtAuthentication#expected_audience`, overridden per surface).
- **FR-003**: System MUST issue opaque, single-use-per-rotation refresh tokens (`Spree::RefreshToken`, `has_secure_token`) with a configurable expiry (`Spree::Api::Config[:refresh_token_expiry]`, default 30 days) and rotate-on-use (`#rotate!` destroys the old row and creates a new one in a transaction).
- **FR-004**: System MUST deliver the Admin API refresh token exclusively via an `HttpOnly`, signed, path-scoped (`/api/v3/admin/auth`) cookie, never in a JSON body (`Spree::Api::V3::Admin::AuthCookies`).
- **FR-005**: System MUST deliver the Store API refresh token in the JSON response body, not a cookie (asymmetric by design — see Migration Notes).
- **FR-006**: System MUST support two independent Admin API credential types beyond user JWTs: publishable keys (`pk_`, Store API, plaintext-token lookup) and secret keys (`sk_`, Admin API, HMAC-SHA256-digest lookup, never stored or logged in plaintext after creation).
- **FR-007**: System MUST authorize secret-key-authenticated Admin API requests by a fixed vocabulary of `read_*`/`write_*` scopes per resource (`Spree::ApiKey::SCOPES`, `ScopedAuthorization`), independent of and in place of CanCanCan; JWT-authenticated admin requests MUST instead use CanCanCan abilities (`Spree::Ability` + `Spree::PermissionSets::*`).
- **FR-008**: System MUST make secret-key scopes immutable after creation (`ApiKey#scopes_immutable` validation) — re-scoping requires issuing a new key and revoking the old one.
- **FR-009**: System MUST reject an Admin API JWT request when the authenticated admin holds no role on the current store, even with a valid unexpired token (`AdminAuthentication#require_store_membership!`).
- **FR-010**: System MUST rate-limit login and refresh endpoints on both Store and Admin auth controllers (`Spree::Api::Config[:rate_limit_login]` = 5, `[:rate_limit_refresh]` = 10, per `[:rate_limit_window]` = 60s), returning a `429 rate_limit_exceeded` with `Retry-After`/`X-RateLimit-*` headers.
- **FR-011**: System MUST support time-limited, single-role, single-resource staff invitations (`Spree::Invitation`, 2-week default expiry) with a public lookup + accept flow that treats "wrong token" and "not found" identically (no existence leakage).
- **FR-012**: System MUST prevent a caller from granting a role whose permission-set closure exceeds their own, and MUST specifically require the caller hold the literal `admin` role to grant it to someone else (`RoleGrantGuard`).
- **FR-013**: System MUST provide an OAuth-identity bridge (`Spree::UserIdentity`) for integrators to add non-password strategies without altering core user models, validating `provider` against the union of registered store/admin strategy keys.
- **FR-014**: System MUST NOT cache authenticated admin API responses (`Cache-Control: private, no-store` set unconditionally by `AdminAuthentication#set_no_store_cache`).
- **FR-015**: The legacy `spree/admin` Devise-based session/password-reset flow MUST independently rate-limit by **both** per-IP and per-normalized-email buckets (`Spree::Admin::AuthRateLimiting`), a stricter scheme than the API v3 auth controllers provide — see Migration Notes for the resulting inconsistency.

### Key Entities

- **`Spree::RefreshToken`**: Polymorphic `belongs_to :user` (customer or admin user), opaque `has_secure_token`, `expires_at`, `ip_address`/`user_agent` audit fields; `rotate!` and `revoke_all_for` lifecycle methods.
- **`Spree::ApiKey`**: `belongs_to :store`; `key_type` (`publishable`/`secret`) with type-specific validations, `token` (plaintext, publishable only) vs `token_digest`/`token_prefix` (secret only), immutable `scopes` array validated against `SCOPES`, `revoked_at`/`revoked_by` for revocation.
- **`Spree::Invitation`**: Polymorphic `resource` (what the invitee is being granted access to — typically `Store`) and `inviter`/`invitee` (User or AdminUser), `belongs_to :role`, `has_secure_token`, state machine `pending → accepted`, `expires_at` (2-week default).
- **`Spree::UserIdentity`**: Polymorphic `belongs_to :user`; `provider` + `uid` uniqueness scoped to `[provider, user_type]`; stores OAuth `info`/`access_token`/`refresh_token`/`expires_at`.
- **`Spree::Authentication::Strategies::BaseStrategy`** / **`EmailPasswordStrategy`**: Strategy pattern — `#authenticate` returns a `Spree::ServiceModule::Result`; registry-keyed by provider string.
- **`Spree::Role`** / **`Spree::RoleUser`**: Role assignment consumed by `RoleGrantGuard` and `Spree::Ability`/`PermissionSets::*`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::RefreshToken`, `Spree::ApiKey`, `Spree::ApiKeys::MarkAsUsed` job, `Spree::Invitation`, `Spree::UserIdentity`, `Spree::Authentication::{StrategyRegistry, Strategies::BaseStrategy, Strategies::EmailPasswordStrategy}`, `Spree::PermissionSets::*`, `Spree::Role`/`Spree::RoleUser` |
| `spree/api` (Store/Admin API v3) | Yes | `V3::Store::AuthController`, `V3::Admin::{AuthController, InvitationAcceptancesController}`, concerns `JwtAuthentication`, `ApiKeyAuthentication`, `ScopedAuthorization`, `AdminAuthentication`, `Admin::{AuthCookies, RoleGrantGuard}`, `Spree::ApiKeyAbility` |
| `spree/admin` (legacy Rails admin) | Yes (pre-existing, not migrated) | Devise-based `UserSessionsController`/`UserPasswordsController` + `Spree::Admin::AuthRateLimiting` concern — still the login path for the legacy Rails admin views; independent rate-limit implementation from API v3 |
| `packages/dashboard-core` (SPA framework) | Yes | `AuthProvider`/`useAuth` (token-in-memory, refresh-cookie-driven silent refresh + 401 retry), consumed via `@spree/admin-sdk`'s `adminClient.auth.*` |
| `packages/dashboard` (admin SPA) | Yes (consumer only) | Login/invitation-acceptance routes consume `useAuth()`; no auth business logic lives here |
| `packages/admin-sdk` / `packages/sdk` | Yes (generated + hand-written client methods) | `adminClient.auth.{login,refresh,logout,acceptInvitation}`, `AdminUser`/`Invitation`/`AuthTokens` generated types |
| `docs/plans/` | Yes (already governs this area) | `5.5-admin-api-key-scopes.md`, `5.5-admin-auth-cookie-refresh.md` — this feature is their as-built state, not new architecture |

### API Contract *(include if feature touches spree/api)*

- **Endpoints**: `POST /api/v3/store/auth/login`, `POST /api/v3/store/auth/refresh`, `POST /api/v3/store/auth/logout`; `POST /api/v3/admin/auth/login`, `POST /api/v3/admin/auth/refresh`, `POST /api/v3/admin/auth/logout`, `GET /api/v3/admin/auth/invitations/:id/lookup`, `POST /api/v3/admin/auth/invitations/:id/accept`.
- **Serializer fields (read)**: Store: `token`, `refresh_token`, `user` (`Spree.api.customer_serializer`). Admin: `token`, `user` (`Spree.api.admin_admin_user_serializer`) — refresh token is a cookie, never a body field.
- **Auth**: Login/refresh/logout/invitation endpoints are themselves public (`skip_before_action :authenticate_admin!` / `:authenticate_user`) but rate-limited. All other Admin API endpoints: secret key + scopes (`ScopedAuthorization`) or Admin JWT + CanCanCan (`Spree::Ability`). Store API: publishable key (guest) or customer JWT.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A brute-force attempt against `/auth/login` on either surface is throttled to `rate_limit_login` (5) attempts per `rate_limit_window` (60s) before receiving `429`.
- **SC-002**: An admin refresh token is never observable from JavaScript in the SPA (`HttpOnly` cookie) and an access token never outlives 5 minutes without a successful silent refresh.
- **SC-003**: 100% of Admin API endpoints reachable by a secret key resolve a `scoped_resource` (or explicit `skip_scope_check!`) — `MissingScopedResource` fails closed rather than silently allowing.
- **SC-004**: An invitee cannot distinguish "invitation doesn't exist" from "wrong token" from "expired" via response shape (all `404 record_not_found`).

## Assumptions

- The Admin SPA (`packages/dashboard`) is the only consumer of the Admin API v3 auth endpoints in production; the legacy `spree/admin` Devise flow is assumed to remain in parallel operation until `spree/admin` is retired, per `CLAUDE.md`'s module table ("legacy Rails admin — being phased out").
- `Spree.store_authentication_strategies` / `Spree.admin_authentication_strategies` are assumed to be populated by a Rails initializer (not located in the files read for this migration) defaulting at minimum to `{ email: EmailPasswordStrategy }` for both registries.
- No OAuth strategy ships in core today; `Spree::UserIdentity` is infrastructure-only until an integrator adds one.
- `jwt_secret` fallback chain (`Spree::Api::Config[:jwt_secret_key]` → Rails credential → `ENV['JWT_SECRET_KEY']` → `secret_key_base`) is assumed intentional multi-environment flexibility, not an oversight.

## Migration Notes

Gaps and ambiguities surfaced during reverse-engineering — flagged because this is a security-critical surface:

1. **Rate-limiting scope is inconsistent across the two auth stacks.** API v3 (`Store::AuthController`, `Admin::AuthController`) rate-limits `login`/`refresh`/`logout` purely by the `rack-attack`-style `rate_limit` DSL's default key (effectively per-IP via `Rails.cache`); there is **no per-email/per-account bucket**, so a distributed (many-IP) credential-stuffing attack against a single account is not throttled at the API v3 layer. By contrast, the legacy `spree/admin` Devise flow (`Spree::Admin::AuthRateLimiting`, exercised by `auth_rate_limiting_spec.rb`) explicitly buckets by **both** per-IP and per-normalized-email keys. This asymmetry was not something this migration resolved — it is flagged as a known gap for whoever owns `docs/plans/5.5-admin-auth-cookie-refresh.md` or a follow-up hardening pass to decide whether API v3 needs the same per-email bucket.
2. **Cookie flags**: `AuthCookies#base_cookie_attributes` sets `secure: false, same_site: :lax` for any non-`Rails.env.production?` environment (which includes `staging`/`demo`-style envs unless they're literally named `production`). Confirm this is intentional for all non-prod-named deployments before relying on it as a security boundary.
2b. The comment in `AuthCookies` explicitly disclaims CSRF token usage in favor of `SameSite` + CORS `AllowedOrigin` allowlisting; this repo-wide decision (`docs/plans/5.5-admin-auth-cookie-refresh.md`) is inherited, not re-derived here — flagged so a reviewer doesn't mistake the missing CSRF token for an oversight.
3. **Strategy extensibility surface has no code example of a second strategy.** `Spree::UserIdentity` and `StrategyRegistry` are fully built for OAuth/SSO strategies, but no OAuth strategy class exists anywhere in the repo (core or extensions) as of this migration — the registry's only registered key found in source is presumably `:email` (the initializer that populates it was not located; see Assumptions). Anyone relying on "OAuth support" as shipped functionality should verify a strategy is actually registered in their deployment.
4. **Store API refresh tokens are body-delivered, not cookie-delivered** (unlike Admin). This means storefront JS clients holding a long-lived refresh token in `localStorage`/memory carry XSS exfiltration risk that the Admin SPA deliberately avoids. This is presumably intentional (storefronts are often not the same origin/trust level as the admin SPA and may run on mobile/native clients that need the raw token), but it was not justified in comments the way the Admin cookie design was — flagged for explicit confirmation.
5. **`ApiKeyAbility` grants unconditional `can :manage, :all`.** Any code path that reaches CanCanCan (`accessible_by`, `authorize!`) for a secret-key-authenticated request is *not* actually gated by CanCanCan — it relies entirely on `ScopedAuthorization` having run first as a `before_action`. A controller that (by bug) declares `scoped_resource` incorrectly or a future controller that skips `ScopedAuthorization` entirely (not just via `skip_scope_check!`, but by not including the concern) would have no per-record protection at all for API-key traffic. No such bug was found, but the coupling is implicit and worth a lint/spec assertion (e.g. "every `Admin::ResourceController` subclass includes `ScopedAuthorization`").
6. **`RoleGrantGuard`'s escalation check is name/permission-set-based**, not a general graph-closure algorithm — it compares `Spree.permissions.permission_sets_for_roles` sets. This is correct for the shipped `PermissionSets::*`, but any custom permission set an integrator adds that computes conditional/dynamic permissions (a `can` block rather than a flat grant) is invisible to this diffing and could let an escalating grant through undetected. No such dynamic permission set exists in `spree/core` today (all shipped sets are flat grants save `SuperUser`'s order-cancellation conditionals), so current risk is theoretical.
7. **JWT secret fallback chain** ends at `Rails.application.secret_key_base` if nothing else is configured — standard Rails practice, but worth confirming `Spree::Api::Config[:jwt_secret_key]` or a credential is actually set in every real deployment so that changing `secret_key_base` for unrelated reasons doesn't silently invalidate every issued admin/customer JWT (5-minute TTL makes this low-impact for admin, higher-impact for the 1h/30-day store tokens).
