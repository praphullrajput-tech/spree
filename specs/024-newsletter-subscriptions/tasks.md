---

description: "Task list for feature migration (retrospective — feature already shipped)"
---

# Tasks: Newsletter Subscriptions

**Input**: Design documents from `/specs/024-newsletter-subscriptions/`

**Prerequisites**: plan.md, spec.md

**Status**: migrated — all tasks below reflect code that already exists in the repository. This is a retrospective record, not pending work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent files, no dependency ordering required
- **[Story]**: US1 = subscribe + double opt-in, US2 = user reconciliation, US3 = admin management/export

## Phase 1: Core Model [US1, US2]

- [x] T001 `spree/core/app/models/spree/newsletter_subscriber.rb` — store-scoped, prefixed ID (`sub_`), `has_secure_token :verification_token`, `verified`/`unverified` scopes, email uniqueness scoped per store

## Phase 2: Subscribe & Verify Services [US1]

- [x] T002 `spree/core/app/services/spree/newsletter/subscribe.rb` — find-or-create, skips opt-in when email matches the current user, publishes `newsletter_subscriber.subscription_requested`
- [x] T003 `spree/core/app/services/spree/newsletter/verify.rb` — sets `verified_at`, clears token, propagates `accepts_email_marketing` to a linked user, publishes `newsletter_subscriber.verified`

## Phase 3: User Reconciliation [US2]

- [x] T004 `spree/core/app/services/spree/newsletter/link_user.rb` — best-effort link + consent propagation, logs (does not raise) on failure

## Phase 4: Store API [US1]

- [x] T005 `spree/api/app/controllers/spree/api/v3/store/newsletter_subscribers_controller.rb` — `create` + `verify` actions, rate-limited, guest-accessible
- [x] T006 `spree/api/app/serializers/spree/api/v3/newsletter_subscriber_serializer.rb`
- [x] T007 [P] `spree/api/spec/integration/spree/api/v3/store/newsletter_subscribers_spec.rb`, `spree/api/spec/serializers/spree/api/v3/newsletter_subscriber_serializer_spec.rb`

## Phase 5: Admin Management & Export [US3]

- [x] T008 `spree/admin/app/controllers/spree/admin/newsletter_subscribers_controller.rb` — index/filter (verified/unverified Ransack scopes)
- [x] T009 [P] `spree/admin/app/views/spree/admin/newsletter_subscribers/`, `spree/admin/app/views/spree/admin/tables/columns/_newsletter_subscriber_customer.html.erb`
- [x] T010 [P] `spree/admin/spec/controllers/spree/admin/newsletter_subscribers_controller_spec.rb`
- [x] T011 CSV export path (shared with `022-exports`): `spree/core/app/models/spree/exports/newsletter_subscribers.rb`, `spree/core/app/presenters/spree/csv/newsletter_subscriber_presenter.rb`

## Notes

- Every phase above is already implemented; nothing here is scheduled work.
- Per spec.md's Migration Notes: no Admin API v3 controller exists for this resource (legacy-admin-only management), and the actual sender of the verification email (webhook consumer vs. `spree/emails` mailer) was not independently traced — both flagged, not remediated, as this migration is documentation-only.
</content>
