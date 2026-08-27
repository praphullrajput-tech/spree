---

description: "Task list for feature migration (retrospective — feature already shipped)"
---

# Tasks: Webhooks

**Input**: Design documents from `/specs/020-webhooks/`

**Prerequisites**: plan.md, spec.md

**Status**: migrated — all tasks below reflect code that already exists in the repository. This is a retrospective record, not pending work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent files, no dependency ordering required
- **[Story]**: Maps to spec.md's user stories (US1 = configure endpoint, US2 = automatic delivery + retries, US3 = inspect delivery history, US4 = verify signature client-side)

## Phase 1: Backend Data Model

- [x] T001 `spree/core/app/models/spree/webhook_endpoint.rb` — endpoint URL, secret, subscribed event list, active flag, store-scoped
- [x] T002 `spree/core/app/models/spree/webhook_delivery.rb` — one row per delivery attempt, status, response code/body, timestamps
- [x] T003 `spree/core/app/mailers/spree/webhook_mailer.rb` — endpoint-disabled notification email

## Phase 2: Event Publishing & Delivery Pipeline [US2]

- [x] T004 [P] `spree/core/lib/spree/events.rb` — `publish_event` entry point used across `spree/core`/`spree/api` to fire named events (e.g. `order.completed`)
- [x] T005 [P] `spree/api/app/subscribers/spree/webhook_event_subscriber.rb` — subscribes to all webhook-eligible events, fans out to matching `WebhookEndpoint`s
- [x] T006 `spree/api/app/jobs/spree/webhook_delivery_job.rb` — async HTTP delivery, records a `WebhookDelivery` row per attempt, retry/backoff handling
- [x] T007 `spree/api/app/services/spree/webhooks/deliver_webhook.rb` — HMAC-signs the payload, performs the HTTP POST, classifies success/failure
- [x] T008 [P] `spree/api/lib/spree/api/testing_support/matchers/webhooks.rb` — RSpec matcher support for asserting webhook delivery in specs

## Phase 3: Admin API v3 [US1, US3]

- [x] T009 [P] `spree/api/app/controllers/spree/api/v3/admin/webhook_endpoints_controller.rb` — CRUD, inherits `ResourceController`
- [x] T010 [P] `spree/api/app/controllers/spree/api/v3/admin/webhook_deliveries_controller.rb` — read-only, scoped to an endpoint, includes a manual "send test" action
- [x] T011 [P] `spree/api/app/serializers/spree/api/v3/admin/webhook_endpoint_serializer.rb`
- [x] T012 [P] `spree/api/app/serializers/spree/api/v3/admin/webhook_delivery_serializer.rb`

## Phase 4: Legacy Rails Admin (frozen — historical reference only) [US1, US3]

- [x] T013 `spree/admin/app/controllers/spree/admin/webhook_endpoints_controller.rb`
- [x] T014 `spree/admin/app/controllers/spree/admin/webhook_deliveries_controller.rb`
- [x] T015 `spree/admin/app/helpers/spree/admin/webhook_endpoints_helper.rb` + table column partials (`_webhook_delivery_status`, `_webhook_delivery_actions`, `_webhook_endpoint_health`, `_webhook_deliveries_stats`)

## Phase 5: Admin SPA [US1, US3]

- [x] T016 [P] `packages/dashboard/src/routes/_authenticated/$storeId/settings/webhooks/index.tsx` — list + create-endpoint sheet
- [x] T017 [P] `packages/dashboard/src/routes/_authenticated/$storeId/settings/webhooks/$webhookEndpointId.tsx` — endpoint detail + delivery history
- [x] T018 [P] `packages/dashboard/src/components/spree/webhook-endpoint-form.tsx`
- [x] T019 [P] `packages/dashboard/src/hooks/use-webhook-endpoints.ts` — `useCreateWebhookEndpoint`, `useToggleWebhookEndpoint`, `useDeleteWebhookEndpoint`, `useSendTestWebhook`
- [x] T020 [P] `packages/dashboard/src/lib/webhook-health.ts` — client-side health/status derivation
- [x] T021 [P] `packages/dashboard/src/schemas/webhook-endpoint.ts`
- [x] T022 [P] `packages/dashboard/src/tables/webhook-endpoints.tsx`, `packages/dashboard/src/tables/webhook-deliveries.tsx`
- [x] T023 `packages/dashboard/e2e/webhooks.spec.ts`

## Phase 6: Client-Side Verification (SDK) [US4]

- [x] T024 [P] `packages/sdk/src/webhooks.ts` — `verifyWebhookSignature`, `WebhookEvent` type, for consumers receiving webhooks
- [x] T025 [P] `packages/sdk/tests/webhooks.test.ts`
- [x] T026 [P] `packages/admin-sdk/src/types/generated/{WebhookEndpoint,WebhookDelivery}.ts`, `packages/admin-sdk/tests/webhook-endpoints.test.ts`

## Notes

- Every phase above is already implemented; nothing here is scheduled work.
- Per spec.md's Migration Notes, HMAC signature verification exists on both sides (server signs in `DeliverWebhook`, client verifies via `packages/sdk`'s `verifyWebhookSignature`) — confirmed a coherent contract rather than a gap.
- Delivery history IS inspectable in both the legacy admin and the SPA (`$webhookEndpointId.tsx` + `webhook-deliveries` table) — this corrects an earlier draft's assumption that no such UI existed.
</content>
