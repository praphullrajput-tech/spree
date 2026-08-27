# Implementation Plan: Newsletter Subscriptions

**Branch**: `024-newsletter-subscriptions` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-newsletter-subscriptions/spec.md`

**Note**: This plan is reverse-engineered from an already-shipped feature (brownfield migration), not authored ahead of implementation.

## Summary

A store-scoped, double-opt-in email subscription system. `Spree::NewsletterSubscriber` holds the subscription state (`verified_at`, `verification_token`); `Spree::Newsletter::Subscribe` handles the create-or-reconcile entry point (skipping opt-in when the email matches the logged-in user); `Spree::Newsletter::Verify` completes the opt-in and propagates consent onto a linked user; `Spree::Newsletter::LinkUser` is a best-effort reconciliation service run from both paths. Exposed only via the Store API (`create`/`verify`); managed only via the legacy Rails admin (no Admin API v3 controller or SPA route exists).

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engine, `spree/core` + `spree/api`).

**Primary Dependencies**: `has_secure_token` (verification token generation), `Spree::SingleStoreResource` (store scoping), `Spree::Metafields`, `Spree::Current`/`Spree::Store.current` (store resolution), Rails events (`publish_event`).

**Storage**: PostgreSQL/SQLite3 via ActiveRecord. Uniqueness enforced at both the validation layer (`scope: spree_base_uniqueness_scope + [:store_id]`) and (per repo migration conventions) expected to be backed by a matching DB index.

**Testing**: RSpec — `spree/api/spec/integration/spree/api/v3/store/newsletter_subscribers_spec.rb`, `spree/api/spec/serializers/spree/api/v3/newsletter_subscriber_serializer_spec.rb`, `spree/admin/spec/controllers/spree/admin/newsletter_subscribers_controller_spec.rb`. No dedicated model/service spec files were located for `NewsletterSubscriber`/`Newsletter::{Subscribe,Verify,LinkUser}` in this pass.

**Target Platform**: Store API v3 (subscribe/verify) + legacy `spree/admin` Rails engine (list/filter/export).

**Project Type**: Monorepo — `spree/core` (model + services) + `spree/api` (Store API controller/serializer) + `spree/admin` (legacy management UI). No `packages/dashboard` involvement.

**Performance Goals**: N/A — low-volume, request-scoped operations; rate-limited by design (see Constraints), not a throughput concern.

**Constraints**: Both `create` and `verify` API actions are rate-limited (`Spree::Api::Config[:rate_limit_register]` within `rate_limit_window`) to prevent enumeration/abuse of the subscribe and token-verification endpoints.

**Scale/Scope**: Single model, 3 service objects, 1 Store API controller, 1 legacy admin controller.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: `spree/core` (model/services), `spree/api` (Store API only), `spree/admin` (legacy read/export UI). No `packages/dashboard` crossing exists. PASS.
- **II. Admin API Is the Only Frontend Data Source**: N/A today — no dashboard SPA surface exists for this feature (management is legacy-admin-only). If a future SPA settings page for subscribers is added, an Admin API v3 controller MUST exist first, per this principle — flagged as a Migration Notes gap, not a current violation.
- **III. Read/Write Field Symmetry**: Store API `create` accepts `email` (and implicitly the authenticated session/redirect_url); `verify` accepts `token`. No serializer/`permitted_params` mismatch identified.
- **IV. Test-Backed**: Admin controller and API integration/serializer specs exist; model/service-level (`Subscribe`/`Verify`/`LinkUser`) spec files were not independently located in this pass — flagged, not asserted missing.
- **V. Translations and Prefixed IDs**: `has_prefix_id :sub` in place (`sub_...` IDs). Error messages use `Spree.t(:newsletter_verification_token_invalid, scope: :api)` — i18n-backed.
- **VI. `docs/plans/` for Architectural Changes**: No plan doc exists; none needed for this migration (documentation-only, no code change).

No violations. Complexity Tracking table intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/024-newsletter-subscriptions/
├── plan.md              # This file
├── spec.md              # Reverse-engineered specification
└── tasks.md             # Reverse-engineered task list (all complete)
```

### Source Code (repository root)

```text
# spree/core — model + services
spree/core/
├── app/models/spree/newsletter_subscriber.rb
└── app/services/spree/newsletter/{subscribe,verify,link_user}.rb

# spree/api — Store API only
spree/api/
├── app/controllers/spree/api/v3/store/newsletter_subscribers_controller.rb   # create, verify
├── app/serializers/spree/api/v3/newsletter_subscriber_serializer.rb
└── spec/integration/spree/api/v3/store/newsletter_subscribers_spec.rb
    spec/serializers/spree/api/v3/newsletter_subscriber_serializer_spec.rb

# spree/admin — legacy read/export UI only
spree/admin/
├── app/controllers/spree/admin/newsletter_subscribers_controller.rb
├── app/views/spree/admin/newsletter_subscribers/
├── app/views/spree/admin/tables/columns/_newsletter_subscriber_customer.html.erb
└── spec/controllers/spree/admin/newsletter_subscribers_controller_spec.rb

# Related (022-exports feature) — CSV export path
spree/core/app/models/spree/exports/newsletter_subscribers.rb
spree/core/app/presenters/spree/csv/newsletter_subscriber_presenter.rb

# [NOT PRESENT] spree/api/v3/admin — no Admin API controller exists
# [NOT PRESENT] packages/dashboard — no route/hook exists
```

**Structure Decision**: Backend + Store API + legacy admin only. No `packages/dashboard`/`dashboard-ui`/`dashboard-core` involvement exists today — confirmed absent by directory search.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
</content>
