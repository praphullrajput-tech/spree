# Implementation Plan: Webhooks

**Branch**: `main` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Status**: Fully shipped including SPA + E2E; model webhook concern stubs not fully wired

---

## Summary

The Webhooks feature delivers signed HTTP POST notifications to merchant-configured endpoints when Spree events occur. The architecture is event-driven: `WebhookEventSubscriber` subscribes to `'*'` (all events), filters by endpoint subscription, creates a `WebhookDelivery` record, and enqueues `WebhookDeliveryJob`. The job calls `DeliverWebhook` service which handles signing, SSRF protection, SSL, timeout, and error classification. Auto-disable triggers after 15 consecutive failures. The Admin SPA provides full endpoint management with health monitoring and delivery audit.

---

## Technical Context

| | |
|--|--|
| **Backend language** | Ruby ≥ 3.2 · Rails 7.2–8.1 |
| **Frontend language** | TypeScript · React 19 · Vite |
| **Signing** | HMAC-SHA256 over `"#{timestamp}.#{payload_json}"` |
| **SSRF protection** | `SsrfFilter` gem in production |
| **Retry** | Polynomial backoff, 5 attempts |
| **Scope** | Fully shipped |

---

## Key Decisions

1. **Secret shown once at create; encrypted at rest.** The raw secret key is only included in the create API response (`@reveal_secret_in_response`). Subsequent reads return only metadata. Rails encryption protects the column at rest. This matches Stripe/GitHub webhook behavior.

2. **Auto-disable after 15 consecutive failures.** `check_auto_disable!` fires after every `complete!`. This protects against unbounded retries on dead endpoints. Email notification ensures the merchant knows and can fix + re-enable. `AUTO_DISABLE_THRESHOLD = 15`.

3. **`(webhook_endpoint_id, event_id)` unique index prevents duplicate deliveries.** If an event fires twice (e.g., during retry of the subscriber), the second delivery insert is a no-op rather than a duplicate delivery to the merchant's system. `event_id IS NOT NULL` partial index allows historical deliveries without `event_id`.

4. **SSRF protection via `SsrfFilter`, disabled in development.** Production environments block delivery to private/loopback IPs to prevent attackers from using webhooks to probe internal services. Dev allows `localhost` for testing.

5. **`DeliverWebhook` is a standalone service, not a callback.** Keeping HTTP delivery in a service (not a model callback or job inline) makes it testable and swappable. The job is responsible only for loading the delivery and calling the service.

6. **Inbound payment webhooks are separate from outbound.** The `Webhooks::PaymentsController` at `/api/v3/webhooks/payments/:id` is a distinct surface for payment gateways pushing status updates into Spree. It has its own signature verification, rate limiting, and async processing. It does not use the `WebhookDelivery` model.

7. **Health computation is client-side (frontend).** `webhookEndpointHealth()` computes the health bucket from serialized `recent_delivery_count` / `recent_failure_count` values. No server-side health field avoids stale cached values.

8. **Model webhook concerns are architectural stubs.** `Spree::Order::Webhooks`, `Spree::Product::Webhooks`, etc. contain method definitions that are not yet fully wired to the event system. They represent the intended interface for publishing domain events from models; implementation completeness varies.

---

## Constitution Check

- [x] **Prefixed IDs**: `whe_` (WebhookEndpoint), `whd_` (WebhookDelivery)
- [x] **API-First**: Admin API + SDK before SPA
- [x] **Read/Write Symmetry**: `name`, `url`, `active`, `subscriptions` exposed and accepted; `secret_key` write-once-exposed
- [x] **Serializer Hierarchy**: `Admin::WebhookEndpointSerializer`, `Admin::WebhookDeliverySerializer`
- [x] **Type Pipeline**: Typelizer types generated; SDK client methods exist
- [x] **Security**: SSRF protection; secret encrypted; signature verification on inbound; rate limiting on inbound
- [x] **Namespace**: `Spree::WebhookEndpoint`, `Spree::WebhookDelivery`, `Spree::Webhooks::DeliverWebhook`
- [x] **SingleStoreResource**: `belongs_to :store`; controller scoped to `current_store`

---

## Project Structure

```text
# Backend — models (✅ shipped)
spree/core/app/models/spree/webhook_endpoint.rb                ← whe_ prefix, paranoid, subscriptions JSONB
spree/core/app/models/spree/webhook_delivery.rb                ← whd_ prefix, tri-state success

# Backend — model stubs (partial)
spree/core/app/models/spree/order/webhooks.rb                  ← send_order_* methods (not fully wired)
spree/core/app/models/spree/product/webhooks.rb                ← send_product_* methods (not fully wired)
spree/core/app/models/spree/shipment/webhooks.rb               ← send_shipment_shipped_webhook (not fully wired)
spree/core/app/models/spree/payment/webhooks.rb                ← empty stub
spree/core/app/models/spree/variant/webhooks.rb                ← empty stub

# Backend — delivery (✅ shipped)
spree/api/app/jobs/spree/webhook_delivery_job.rb               ← polynomial backoff, 5 attempts
spree/api/app/services/spree/webhooks/deliver_webhook.rb       ← HMAC-SHA256, SSRF, 30s timeout

# Backend — subscriber (✅ shipped)
spree/api/app/subscribers/spree/webhook_event_subscriber.rb    ← subscribes to '*'

# Backend — mailer (✅ shipped)
spree/core/app/mailers/spree/webhook_mailer.rb                 ← auto-disable notification

# Backend — controllers (✅ shipped)
spree/api/app/controllers/spree/api/v3/admin/webhook_endpoints_controller.rb
spree/api/app/controllers/spree/api/v3/admin/webhook_deliveries_controller.rb
spree/api/app/controllers/spree/api/v3/webhooks/payments_controller.rb  ← inbound

# Backend — serializers (✅ shipped)
spree/api/app/serializers/spree/api/v3/admin/webhook_endpoint_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/webhook_delivery_serializer.rb

# Frontend (✅ shipped)
packages/dashboard/src/hooks/use-webhook-endpoints.ts
packages/dashboard/src/schemas/webhook-endpoint.ts             ← WEBHOOK_EVENT_GROUPS (25 domains)
packages/dashboard/src/lib/webhook-health.ts                   ← health bucket computation
packages/dashboard/src/tables/webhook-endpoints.tsx
packages/dashboard/src/tables/webhook-deliveries.tsx
packages/dashboard/src/components/spree/webhook-endpoint-form.tsx
packages/dashboard/src/routes/_authenticated/$storeId/settings/webhooks/index.tsx
packages/dashboard/src/routes/_authenticated/$storeId/settings/webhooks/$webhookEndpointId.tsx
packages/dashboard/e2e/webhooks.spec.ts
```

---

## Phase 1: Core + API + SPA (✅ Complete)

- `WebhookEndpoint` + `WebhookDelivery` models
- `WebhookEventSubscriber` + `DeliverWebhook` service + `WebhookDeliveryJob`
- Auto-disable (15 failures) + `WebhookMailer`
- Admin API: CRUD + send_test + enable/disable + redeliver
- TypeScript types generated; Admin SDK client methods
- Admin SPA: list + detail pages, health monitoring, event picker, delivery detail
- E2E: `webhooks.spec.ts`
- Inbound payment webhook handler

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected |
|-----------|------------|------------------------------|
| Tri-state `success` (`true`/`false`/`nil`) | `nil` represents pending (job not yet run); `false` is HTTP error; `true` is 2xx. Three states needed for UI — a boolean would conflate "not yet delivered" with "failed" | Two-state boolean — `nil` would look like `false` in the health dashboard, showing healthy endpoints as degraded before jobs run |
| Composite delivery payload envelope (`id`, `name`, `created_at`, `data`, `metadata`) | Standard envelope enables routing without parsing `data`; `id` enables idempotency checks by the receiver | Sending raw `data` only — receiver can't route by event name without parsing every payload |
