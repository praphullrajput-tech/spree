# Feature Specification: Newsletter Subscriptions

**Feature Branch**: `024-newsletter-subscriptions`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration) — `spree/core/app/models/spree/newsletter_subscriber.rb`, `spree/core/app/services/spree/newsletter/{subscribe,verify,link_user}.rb`, `spree/api/app/controllers/spree/api/v3/store/newsletter_subscribers_controller.rb`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Subscribe to the store newsletter with double opt-in (Priority: P1)

A storefront visitor (guest or logged-in) submits their email to a newsletter sign-up form and, unless already logged in with that exact email, must confirm via a verification link before being counted as a real subscriber.

**Why this priority**: The entire value of the feature — an unverified email address on file is not usable for marketing (`accepts_email_marketing` returns `false` until `verified?`).

**Independent Test**: `POST /api/v3/store/newsletter_subscribers` with an email not belonging to the current session; verify a `Spree::NewsletterSubscriber` row is created with `verified_at: nil` and a `newsletter_subscriber.subscription_requested` event is published (for an external email-sender to consume); then `POST /api/v3/store/newsletter_subscribers/verify` with the returned token and verify `verified_at` is set.

**Acceptance Scenarios**:

1. **Given** a new email with no existing subscriber row for the current store, **When** `Spree::NewsletterSubscriber.subscribe` is called, **Then** a subscriber is created (store-scoped, `find_or_create_by`) and, if not already verified, `newsletter_subscriber.subscription_requested` is published with the verification token in the payload — no email is sent directly by this service, only the event.
2. **Given** the subscribing email matches the currently logged-in user's email, **When** subscribing, **Then** `Spree::Newsletter::Verify` is called immediately — the double opt-in is skipped because login already proved the email.
3. **Given** an already-verified subscription exists for that email+store, **When** `subscribe` is called again, **Then** no duplicate row is created; `Spree::Newsletter::LinkUser` reconciles the user link and returns the existing subscriber.
4. **Given** a valid, unexpired verification token, **When** `POST .../verify` is called, **Then** the subscriber's `verified_at` is set, its token is cleared, and — if linked to a user — the user's `accepts_email_marketing` is flipped to `true`, and a `newsletter_subscriber.verified` event is published.
5. **Given** an invalid or already-used token, **When** `POST .../verify` is called, **Then** the API returns an `invalid_token` error (422) rather than a 404, since the lookup is scoped to `unverified` subscribers only.

---

### User Story 2 - Reconcile a subscription with a customer account (Priority: P2)

A visitor subscribes to the newsletter before creating an account (or while logged out), then later logs in or registers with the same email — their prior marketing consent should not be silently lost.

**Why this priority**: Without this, opt-in state and email consent could desync between the anonymous subscription and the eventual customer record.

**Independent Test**: Create an unlinked, verified `NewsletterSubscriber` for an email, then call `Spree::Newsletter::LinkUser` with a matching user who has `accepts_email_marketing: false`; verify the subscriber's `user_id` is set and the user's `accepts_email_marketing` becomes `true`.

**Acceptance Scenarios**:

1. **Given** a verified subscriber not yet linked to a user, **When** a user with the same email is later known (login, registration, or a repeat `subscribe` call), **Then** `LinkUser` sets `subscriber.user` and propagates `accepts_email_marketing: true` onto the user.
2. **Given** the link or consent-propagation update fails validation, **When** `LinkUser` runs, **Then** the failure is logged (`Rails.logger.warn`) but not raised — this is best-effort reconciliation, not a transactional precondition (explicitly documented in the class's own comment).

---

### User Story 3 - Admin manages and exports the subscriber list (Priority: P3)

A store admin wants to see who has subscribed (verified vs. unverified), search by email, and export the list for use in an external email marketing tool.

**Why this priority**: Read/export access, not core to the subscribe/verify flow — supports marketing operations.

**Independent Test**: In the legacy Rails admin, visit the newsletter subscribers index; verify the "verified"/"unverified" Ransack scopes filter correctly and a CSV export (via `Spree::Exports::NewsletterSubscribers`, `026`-adjacent) produces a row per subscriber.

**Acceptance Scenarios**:

1. **Given** subscribers with and without `verified_at`, **When** an admin filters by the `verified`/`unverified` Ransack scope, **Then** only matching rows are returned (`whitelisted_ransackable_scopes`).
2. **Given** a subscriber linked to a customer, **When** viewed in the admin table, **Then** the customer column (`_newsletter_subscriber_customer.html.erb`) links to that customer's profile.

### Edge Cases

- What happens if the same email subscribes to two different stores? Uniqueness is scoped to `[store_id]` (plus the base uniqueness scope), so this is allowed — one subscriber row per store.
- What happens if `current_store` isn't passed explicitly? `NewsletterSubscriber#set_store` and `Subscribe#current_store` both fall back to `Spree::Current.store`/`Spree::Store.current`.
- What happens on a malformed email? Rejected at the model-validation layer (`URI::MailTo::EMAIL_REGEXP`) before any service logic runs.
- What happens to the rate limit on repeated subscribe/verify attempts? Both `create` and `verify` API actions share `Spree::Api::Config[:rate_limit_register]` within `rate_limit_window` — a deliberate anti-abuse measure on both directions of the flow.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow both guest and logged-in storefront visitors to submit an email for newsletter subscription (`allow_guest_storefront_access!`).
- **FR-002**: System MUST enforce double opt-in (email verification) before a subscription counts toward `accepts_email_marketing`, EXCEPT when the subscribing email matches the currently authenticated user's email (login already proves ownership).
- **FR-003**: System MUST NOT send verification emails itself — it publishes `newsletter_subscriber.subscription_requested` (with the verification token in the payload) for an external consumer (webhook/email service) to act on.
- **FR-004**: System MUST reconcile subscriber-to-user linkage whenever a known user becomes associated with a subscribed email (at subscribe time, at verify time, or on repeat subscription), propagating verified consent onto the user record without failing the overall operation if the propagation itself fails validation.
- **FR-005**: System MUST scope subscriber uniqueness per store (`[store_id]` + base uniqueness scope) — the same email may subscribe independently to multiple stores.
- **FR-006**: System MUST rate-limit both the `create` (subscribe) and `verify` API actions to prevent abuse.
- **FR-007**: Admins MUST be able to filter subscribers by verified/unverified status and export the list to CSV.

### Key Entities

- **Spree::NewsletterSubscriber**: Store-scoped, prefixed-ID (`sub_`), optionally linked to a user, holds a `has_secure_token :verification_token` and `verified_at` timestamp. Includes `Spree::Metafields`.
- **Spree::Newsletter::Subscribe**: Orchestrates find-or-create + immediate verification (if email matches current user) + event publication.
- **Spree::Newsletter::Verify**: Marks a subscriber verified, propagates consent to a linked user, publishes `newsletter_subscriber.verified`.
- **Spree::Newsletter::LinkUser**: Best-effort reconciliation service — links a subscriber to a user and propagates consent; logs rather than raises on failure.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `NewsletterSubscriber` model, `Newsletter::{Subscribe,Verify,LinkUser}` services |
| `spree/api` (Store/Admin API v3) | Yes | `Store::NewsletterSubscribersController` (`create`, `verify`), `NewsletterSubscriberSerializer` — Store API only, no Admin API v3 controller found |
| `packages/dashboard` (admin SPA) | No | No route/hook found — management is legacy-admin-only |
| `packages/dashboard-ui` / `dashboard-core` | No | — |
| `packages/sdk` / `packages/admin-sdk` | Partial | `packages/sdk` (Store API client) likely has a generated type/method for this resource; `packages/admin-sdk` has none (no Admin API controller to generate from) |
| `docs/plans/` | No | No dedicated plan doc found |

### API Contract

- **Endpoints**: `POST /api/v3/store/newsletter_subscribers` (subscribe), `POST /api/v3/store/newsletter_subscribers/verify` (verify by token)
- **Auth**: Store API, publishable key or guest — `allow_guest_storefront_access!`
- **Serializer fields (read)**: shaped by `Spree::Api::V3::NewsletterSubscriberSerializer` (not independently re-verified for exact field list in this pass)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A guest visitor can subscribe and, after clicking a verification link/token, becomes a verified subscriber without needing an account.
- **SC-002**: A logged-in user subscribing with their account email becomes verified immediately, with zero additional steps.
- **SC-003**: No duplicate subscriber rows are ever created for the same email+store pair, regardless of how many times `subscribe` is called.
- **SC-004**: Admins can export the full subscriber list to CSV for use in an external marketing tool.

## Assumptions

- "Feature" here means the existing newsletter subscription subsystem as built today — this document reverse-engineers current behavior for spec-kit tracking, not a proposed redesign.
- An external system (webhook consumer or `spree/emails`) is assumed to handle actually sending the verification email in response to `newsletter_subscriber.subscription_requested` — this was not independently traced in this pass.
- `Spree.user_class` is configured per standard Spree conventions.

## Migration Notes

- **Gap — no Admin API v3 controller**: Subscriber management (view/filter/verify-status) is legacy-Rails-admin-only; no `spree/api/v3/admin/newsletter_subscribers_controller.rb` was found. A future dashboard SPA settings page would need this built first, per Constitution Principle II.
- **Gap — verification email sender not traced**: `Subscribe`/`Verify` only publish domain events (`newsletter_subscriber.subscription_requested`/`.verified`); this pass did not confirm which subscriber (webhook, `spree/emails` mailer, or an external integration) actually sends the verification email to the visitor. Flagged for follow-up, not asserted as missing.
- **Not migrated**: no code changes were made. This is a reverse-engineered spec for existing, already-shipped behavior.
</content>
