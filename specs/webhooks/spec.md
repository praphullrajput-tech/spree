---
status: migrated
---

# Spec: Webhooks

**Feature**: Outbound webhook delivery system — notify external services of Spree events via signed HTTP POST

---

## Overview

The Webhooks feature lets merchants configure HTTP endpoints to receive real-time notifications when events occur in their store (orders placed, products updated, shipments sent, etc.). Each endpoint subscribes to specific events or all events (`*`). Deliveries are signed with HMAC-SHA256, retried on failure with exponential backoff, and logged for auditing. Endpoints with 15+ consecutive failures are auto-disabled with an email notification. An inbound payment webhook handler also exists for payment gateways to push status updates back into Spree.

---

## User Scenarios

### US1 — Merchant creates a webhook endpoint
Given a merchant in the admin SPA,
When they navigate to Settings → Webhooks and click "Add endpoint",
Then they configure a URL, optional name, and event subscriptions from a grouped picker (or type custom event names); on save the response shows the secret key once, which must be copied immediately.

### US2 — Merchant views delivery history
Given a configured webhook endpoint,
When the merchant opens the endpoint detail page,
Then they see a table of deliveries with event name, success/failure status, response code, execution time, and timestamp; they can open a delivery to inspect the full request payload and response body.

### US3 — Merchant redelivers a failed delivery
Given a failed webhook delivery,
When the merchant clicks "Redeliver",
Then a new delivery is created with the same payload and queued for immediate re-send; the original delivery record is preserved for audit.

### US4 — Merchant sends a test webhook
Given a configured endpoint,
When the merchant clicks "Send test",
Then a `webhook.test` delivery is created and queued; the result appears in the deliveries list.

### US5 — Endpoint auto-disabled after repeated failures
Given an endpoint that has accumulated 15 consecutive failed deliveries,
When the 15th failure is recorded,
Then the endpoint is automatically disabled; the store's notification email receives an alert; the endpoint detail page shows the disabled badge and reason.

### US6 — External service verifies webhook signature
Given a delivery with `X-Spree-Webhook-Signature` and `X-Spree-Webhook-Timestamp` headers,
When the external service computes `HMAC-SHA256(secret_key, "#{timestamp}.#{payload_json}")`,
Then the computed digest matches the header; the service rejects the request otherwise.

### US7 — Payment gateway pushes status update
Given an inbound payment webhook configured on a payment method,
When the gateway posts to `/api/v3/webhooks/payments/:payment_method_id`,
Then Spree verifies the gateway's signature, rate-limits to 120 requests/minute, and enqueues an async processing job; the gateway receives 200 immediately.

---

## Functional Requirements

### FR-001 — WebhookEndpoint model
`Spree::WebhookEndpoint` with prefix `whe_`. Belongs to store. `acts_as_paranoid`. Columns: `name`, `url`, `active`, `subscriptions` (JSONB array), `secret_key` (encrypted at rest when Rails encryption enabled), `disabled_at`, `disabled_reason`. Secret generated on create (64-char hex). Secret exposed in create response only (`@reveal_secret_in_response`).

### FR-002 — Event subscription filtering
`subscribed_to?(event_name)` supports exact match and wildcard `*` (subscribe to all events). Empty subscriptions treated as `['*']`. Subscription list returned as configured array.

### FR-003 — WebhookDelivery model
`Spree::WebhookDelivery` with prefix `whd_`. Belongs to endpoint. Columns: `event_name`, `event_id` (for deduplication), `payload` (JSONB), `response_code`, `response_body`, `error_type`, `request_errors`, `execution_time`, `success` (tri-state: `true`/`false`/`nil`), `delivered_at`. Unique index on `(webhook_endpoint_id, event_id)` where `event_id IS NOT NULL`.

### FR-004 — Delivery job
`Spree::WebhookDeliveryJob` on queue `Spree.queues.webhooks`. Polynomial backoff, 5 retry attempts. Calls `Spree::Webhooks::DeliverWebhook`. Discards `ActiveJob::DeserializationError`.

### FR-005 — HMAC-SHA256 signing
`DeliverWebhook` service sends POST with headers: `X-Spree-Webhook-Signature` (HMAC-SHA256 of `"#{timestamp}.#{payload_json}"`), `X-Spree-Webhook-Timestamp` (Unix seconds), `X-Spree-Webhook-Event` (event name), `Content-Type: application/json`, `User-Agent: Spree-Webhooks/1.0`. 30-second timeout.

### FR-006 — SSRF protection
In production, `SsrfFilter.post()` blocks delivery to private/loopback IPs. Disabled in development to allow localhost testing.

### FR-007 — Auto-disable after failures
`WebhookEndpoint#check_auto_disable!` fires after each delivery completion. If 15+ consecutive failed deliveries exist, endpoint is disabled (`disabled_at`, `disabled_reason = 'auto'`). `WebhookMailer#endpoint_disabled` sends notification email.

### FR-008 — Admin API
`Admin::WebhookEndpointsController` — full CRUD + `send_test`, `enable`, `disable` actions. `Admin::WebhookDeliveriesController` — nested under endpoint; `index`, `show`, `redeliver` actions. Both store-scoped.

### FR-009 — Event subscriber
`Spree::WebhookEventSubscriber` subscribes to `'*'` (all events). Checks `webhooks_enabled`, loads enabled endpoints for the store, filters by subscription, creates `WebhookDelivery`, enqueues job. Payload envelope: `{ id, name, created_at, data, metadata }`.

### FR-010 — Admin SPA — list page
`settings/webhooks/index.tsx` — ResourceTable of endpoints with columns: name, url, subscriptions count, status badge, health badge (healthy/degraded/failing/disabled), last delivery. Create modal (secret reveal dialog), send test, delete.

### FR-011 — Admin SPA — detail page
`settings/webhooks/$webhookEndpointId.tsx` — health summary card (success %, counts), nested deliveries table with status filter, delivery detail sheet (request payload + response JSON viewer), redeliver action, edit sheet.

### FR-012 — Health computation
`webhookEndpointHealth(endpoint)` computes bucket: `disabled`, `no_deliveries`, or `healthy` (≥95%), `degraded` (≥80%), `failing` (<80%) based on `recent_delivery_count` and `recent_failure_count` (last 7 days).

### FR-013 — Event subscription picker
`EventPicker` component groups 25+ built-in event types by domain (order, product, payment, shipment, customer, etc.). Free-text custom event input. Shows "All events" when subscriptions is empty.

### FR-014 — Inbound payment webhooks
`Webhooks::PaymentsController` at `POST /api/v3/webhooks/payments/:payment_method_id`. Verifies gateway signature synchronously; returns 401 on failure. Rate-limited to 120 requests/minute by IP. Enqueues async processing job with 30s delay. Returns 200 immediately.

### FR-015 — Configuration
`Spree::Api::Config.webhooks_enabled` (default: `true`). `Spree::Api::Config.webhooks_verify_ssl` (default: `!Rails.env.development?`).

---

## Non-Functional Requirements

- **NFR-001** — Delivery is always async — no synchronous HTTP calls from model callbacks
- **NFR-002** — Secret key never returned after create; stored encrypted at rest
- **NFR-003** — `(webhook_endpoint_id, event_id)` unique index prevents duplicate deliveries for the same event
- **NFR-004** — SSRF protection blocks private IP targets in production
- **NFR-005** — Auto-disable protects against runaway jobs on dead endpoints

---

## Success Criteria

- [ ] `POST /api/v3/admin/webhook_endpoints` creates endpoint with secret in response only
- [ ] Delivery is queued on event publish; `X-Spree-Webhook-Signature` verifiable by external service
- [ ] Failed delivery increments consecutive-failure counter; 15th triggers auto-disable + email
- [ ] `redeliver` creates new delivery with same payload; original preserved
- [ ] Admin SPA settings/webhooks shows health badge, delivery table, delivery detail sheet
- [ ] Inbound payment webhook at `/api/v3/webhooks/payments/:id` verifies signature + rate-limits + returns 200 async

---

## Out of Scope

- Model webhook concerns wired to domain events (Order, Product, Variant, Shipment webhook stubs exist but event publishing not fully wired for all models)
- Webhook event catalog management UI (events are code-defined constants)
- Webhook log retention/purge policy
- Delivery replay from UI for all events (only individual redeliver supported)
