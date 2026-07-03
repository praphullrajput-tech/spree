---

description: "Task list for Webhooks — fully shipped including SPA + E2E; model webhook concern stubs partially wired"
---

# Tasks: Webhooks

**Status**: Fully shipped; model webhook concern stubs not fully wired for all models

---

## Path Reference

| Code type | Path |
|-----------|------|
| Core models | `spree/core/app/models/spree/` |
| Model stubs | `spree/core/app/models/spree/{order,product,shipment,...}/webhooks.rb` |
| Delivery job | `spree/api/app/jobs/spree/webhook_delivery_job.rb` |
| Delivery service | `spree/api/app/services/spree/webhooks/deliver_webhook.rb` |
| Subscriber | `spree/api/app/subscribers/spree/webhook_event_subscriber.rb` |
| Mailer | `spree/core/app/mailers/spree/webhook_mailer.rb` |
| Admin serializers | `spree/api/app/serializers/spree/api/v3/admin/` |
| Admin controllers | `spree/api/app/controllers/spree/api/v3/admin/` |
| Inbound controller | `spree/api/app/controllers/spree/api/v3/webhooks/` |
| Backend specs | `spree/core/spec/` and `spree/api/spec/` |
| Admin SDK types | `packages/admin-sdk/src/types/generated/` |
| Dashboard hooks | `packages/dashboard/src/hooks/` |
| Dashboard schemas | `packages/dashboard/src/schemas/` |
| Dashboard tables | `packages/dashboard/src/tables/` |
| Dashboard routes | `packages/dashboard/src/routes/_authenticated/$storeId/settings/webhooks/` |
| E2E specs | `packages/dashboard/e2e/` |

---

## Phase 1: Core + API + SPA ✅

### Models

- [x] T001 `spree/core/app/models/spree/webhook_endpoint.rb` — `has_prefix_id :whe`; `acts_as_paranoid`; `subscriptions` JSONB; `secret_key` encrypted; `subscribed_to?(event_name)` with wildcard support; `send_test!`; `disable!(reason, notify)`; `enable!`; `check_auto_disable!` (threshold: 15); `AUTO_DISABLE_THRESHOLD = 15`; scopes: `active`, `inactive`, `enabled`
- [x] T002 `spree/core/app/models/spree/webhook_delivery.rb` — `has_prefix_id :whd`; tri-state `success` (`true`/`false`/`nil`); `complete!(response_code, execution_time, error_type, request_errors, response_body)`; `redeliver!`; `queue_for_delivery!`; `ERROR_TYPES = %w[timeout connection_error]`; scopes: `successful`, `failed`, `pending`, `recent`, `for_event`

### Migrations

- [x] T003 `20251214000001_create_spree_webhook_endpoints.rb` — `store_id`, `url`, `active`, `subscriptions` (jsonb), `secret_key`, `deleted_at`, timestamps
- [x] T004 `20251214000002_create_spree_webhook_deliveries.rb` — `webhook_endpoint_id`, `event_name`, `payload` (jsonb), `response_code`, `response_body`, `error_type`, `execution_time`, `request_errors`, `success`, `delivered_at`, timestamps
- [x] T005 `20260326000001_improve_spree_webhooks.rb` — adds `name`, `disabled_reason`, `disabled_at` to endpoints; adds `event_id` to deliveries; unique index `(webhook_endpoint_id, event_id)` where `event_id IS NOT NULL`

### Delivery Infrastructure

- [x] T006 `spree/api/app/jobs/spree/webhook_delivery_job.rb` — queue `Spree.queues.webhooks`; polynomial backoff, 5 attempts; discard `ActiveJob::DeserializationError`
- [x] T007 `spree/api/app/services/spree/webhooks/deliver_webhook.rb` — `TIMEOUT = 30`; `Net::HTTP::Post`; HMAC-SHA256 signing over `"#{timestamp}.#{payload_json}"`; headers: `X-Spree-Webhook-Signature`, `X-Spree-Webhook-Timestamp`, `X-Spree-Webhook-Event`; `SsrfFilter.post()` in prod; SSL configurable; catches timeout + connection errors → `error_type`
- [x] T008 `spree/api/app/subscribers/spree/webhook_event_subscriber.rb` — subscribes to `'*'`; checks `webhooks_enabled`; filters enabled endpoints by subscription; creates `WebhookDelivery`; enqueues job; payload envelope: `{ id, name, created_at, data, metadata }`
- [x] T009 `spree/core/app/mailers/spree/webhook_mailer.rb` — `endpoint_disabled` email on auto-disable

### Serializers

- [x] T010 `spree/api/app/serializers/spree/api/v3/admin/webhook_endpoint_serializer.rb` — `whe_` prefix ID; name, url, active, subscriptions, secret_key (create only), disabled_at, disabled_reason; computed: `last_delivery_at`, `recent_delivery_count`, `recent_failure_count`, `total_delivery_count`, `successful_delivery_count`, `failed_delivery_count`
- [x] T011 `spree/api/app/serializers/spree/api/v3/admin/webhook_delivery_serializer.rb` — `whd_` prefix ID; event_name, event_id, response_code, execution_time, error_type, request_errors, response_body, success, payload, delivered_at; delegated: webhook_endpoint_id (prefixed), webhook_endpoint_url

### Controllers

- [x] T012 `spree/api/app/controllers/spree/api/v3/admin/webhook_endpoints_controller.rb` — full CRUD + `send_test` (POST), `enable` (PATCH), `disable` (PATCH, optional reason)
- [x] T013 `spree/api/app/controllers/spree/api/v3/admin/webhook_deliveries_controller.rb` — nested under endpoint; index, show, `redeliver` (POST)
- [x] T014 `spree/api/app/controllers/spree/api/v3/webhooks/payments_controller.rb` — inbound; signature verification; rate limit 120/min by IP; async job with 30s delay

### Specs

- [x] T015 `spree/core/spec/models/spree/webhook_endpoint_spec.rb` — subscription filtering; auto-disable; secret generation; enable/disable
- [x] T016 `spree/core/spec/models/spree/webhook_delivery_spec.rb` — tri-state success; `redeliver!` preserves original; `complete!` triggers auto-disable check
- [x] T017 `spree/api/spec/integration/spree/api/v3/admin/webhook_endpoints_spec.rb` — CRUD; send_test; enable/disable; secret in create only
- [x] T018 `spree/api/spec/integration/spree/api/v3/admin/webhook_deliveries_spec.rb` — list; redeliver

### Type Pipeline

- [x] T019 `bundle exec rake typelizer:generate` — `WebhookEndpoint`, `WebhookDelivery` TypeScript types generated
- [x] T020 Admin SDK: `webhookEndpoints.*` and `webhookEndpoints.deliveries.*` client methods in `packages/admin-sdk/src/admin-client.ts`
- [x] T021 `bundle exec rake rswag:specs:swaggerize`

### Configuration

- [x] T022 `Spree::Api::Config.webhooks_enabled` (default: `true`)
- [x] T023 `Spree::Api::Config.webhooks_verify_ssl` (default: `!Rails.env.development?`)

### Frontend

- [x] T024 `packages/dashboard/src/hooks/use-webhook-endpoints.ts` — `useWebhookEndpoint`, `useCreateWebhookEndpoint`, `useUpdateWebhookEndpoint`, `useDeleteWebhookEndpoint`, `useToggleWebhookEndpoint`, `useSendTestWebhook`, `useWebhookDelivery`, `useRedeliverWebhookDelivery`
- [x] T025 `packages/dashboard/src/schemas/webhook-endpoint.ts` — `webhookEndpointFormSchema`; `WEBHOOK_EVENT_GROUPS` (25 domains); `WebhookEndpointFormValues` type
- [x] T026 `packages/dashboard/src/lib/webhook-health.ts` — `webhookEndpointHealth()` → `healthy`/`degraded`/`failing`/`disabled`/`no_deliveries`; `webhookHealthBadgeVariant()`
- [x] T027 `packages/dashboard/src/tables/webhook-endpoints.tsx` — columns: name, url, subscriptions count, status, health, last_delivery_at
- [x] T028 `packages/dashboard/src/tables/webhook-deliveries.tsx` — columns: event_name, success (tri-state badge), response_code, execution_time, delivered_at
- [x] T029 `packages/dashboard/src/components/spree/webhook-endpoint-form.tsx` — `EventPicker` with grouped built-in events + custom free-text input
- [x] T030 `packages/dashboard/src/routes/_authenticated/$storeId/settings/webhooks/index.tsx` — create modal; secret reveal dialog (shown once); row click → detail; delete; send test; toggle
- [x] T031 `packages/dashboard/src/routes/_authenticated/$storeId/settings/webhooks/$webhookEndpointId.tsx` — health summary card; edit sheet; nested deliveries table; delivery detail sheet (JSON viewer); redeliver action
- [x] T032 Add i18n keys under `admin.webhooks.*`, `admin.webhook_endpoints.*`, `admin.webhook_deliveries.*` in all locale files

### E2E

- [x] T033 `packages/dashboard/e2e/webhooks.spec.ts` — list endpoints; create + secret reveal; navigate to detail; rename; send test; redeliver
- [x] T034 Run `pnpm test:e2e` ✅

**Checkpoint**: full webhook system — outbound delivery, signing, retry, auto-disable, health monitoring, SPA, E2E ✅

---

## Phase 2: Wire Model Webhook Concerns (PENDING)

The following model-level webhook concern stubs exist but are not fully wired to the event system:

- [ ] T035 `spree/core/app/models/spree/order/webhooks.rb` — wire `send_order_canceled_webhook`, `send_order_placed_webhook`, `send_order_resumed_webhook` to publish lifecycle events
- [ ] T036 `spree/core/app/models/spree/product/webhooks.rb` — wire `send_product_activated_webhook`, `send_product_archived_webhook`, `send_product_drafted_webhook`
- [ ] T037 `spree/core/app/models/spree/shipment/webhooks.rb` — wire `send_shipment_shipped_webhook`
- [ ] T038 `spree/core/app/models/spree/payment/webhooks.rb` — implement payment event publishing
- [ ] T039 `spree/core/app/models/spree/variant/webhooks.rb` — implement variant event publishing
- [ ] T040 Audit all event names in `WEBHOOK_EVENT_GROUPS` schema against actual published events — close any gaps

---

## ⚠️ Gaps Identified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| Model webhook concern stubs not fully wired | Medium | T035–T040; merchants subscribed to `order.*` or `product.*` events may not receive all expected events |
| No audit of `WEBHOOK_EVENT_GROUPS` vs actual published events | Medium | T040 — event names in the picker should match events the system actually publishes |
| No delivery log retention/purge policy | Low | Old deliveries accumulate indefinitely; consider a periodic purge job for deliveries older than N days |
