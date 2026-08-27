# Feature Specification: Webhooks

**Feature Branch**: `020-webhooks`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing implementation (brownfield migration). Outbound HTTP webhook delivery system: `Spree::WebhookEndpoint` + `Spree::WebhookDelivery` models, HMAC-signed delivery via `Spree::Webhooks::DeliverWebhook`, event fan-out via `Spree::WebhookEventSubscriber`, Admin API v3 CRUD + endpoint-scoped actions (`send_test`, `enable`, `disable`, `redeliver`), legacy Rails admin UI, React admin SPA UI, and `@spree/sdk` client-side signature verification. Shipped since Spree 5.3.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merchant registers a webhook endpoint to receive order events (Priority: P1)

A store admin wants an external system (CRM, fulfillment service, custom integration) to be notified in real time when orders complete, ship, or get paid. They create a webhook endpoint in the admin, pointing at their receiving URL and subscribing to specific event patterns (e.g. `order.*`).

**Why this priority**: This is the entire reason the feature exists — without endpoint registration nothing else in the system has a destination.

**Independent Test**: Create a `Spree::WebhookEndpoint` (via Admin API `POST /api/v3/admin/webhook_endpoints` or the admin/dashboard UI) with `url` + `subscriptions`, publish a matching event (e.g. `order.publish_event('order.completed')`), and confirm a `Spree::WebhookDelivery` row is created and `Spree::WebhookDeliveryJob` is enqueued.

**Acceptance Scenarios**:

1. **Given** an active endpoint subscribed to `order.*`, **When** `order.completed` is published for that store, **Then** a `WebhookDelivery` is created with the serialized event payload and a delivery job is queued.
2. **Given** an endpoint with `subscriptions: []` or `['*']`, **When** any event is published for that store, **Then** the endpoint receives it.
3. **Given** an endpoint belonging to store A, **When** an event is published with a different store's `store_id`, **Then** no delivery is created for store A's endpoint.

---

### User Story 2 - Receiving system verifies webhook authenticity via HMAC signature (Priority: P1)

The external system receiving webhooks must be able to confirm the request genuinely came from the Spree store and was not tampered with, before acting on the payload.

**Why this priority**: Without signature verification, webhooks are an open door for spoofed requests — this is a hard security requirement for any consumer.

**Independent Test**: Trigger a delivery, capture the `X-Spree-Webhook-Signature` and `X-Spree-Webhook-Timestamp` headers plus the raw body, recompute `HMAC-SHA256(secret_key, "#{timestamp}.#{body}")`, and confirm it matches. `@spree/sdk`'s `verifyWebhookSignature` (in `packages/sdk/src/webhooks.ts`) implements the same check for JS consumers.

**Acceptance Scenarios**:

1. **Given** a valid signature computed with the endpoint's `secret_key`, **When** the receiver recomputes it from the raw body + timestamp, **Then** they match.
2. **Given** the `secret_key` is only exposed in the `WebhookEndpoint` create API response (`secret_key_for_response`), **When** the endpoint is read again later, **Then** `secret_key` serializes as `nil`.

---

### User Story 3 - Admin inspects delivery history and retries failed deliveries (Priority: P2)

When a webhook fails to reach its destination (endpoint down, 5xx, timeout), the admin needs to see what happened and manually resend it without re-triggering the original business event.

**Why this priority**: Operational necessity for running webhooks in production, but the system functions (delivers + retries automatically) without a human looking at it.

**Independent Test**: Force a delivery failure (stub a non-2xx response), confirm the `WebhookDelivery` record captures `response_code`/`error_type`/`request_errors`, then call `redeliver!` (or `POST .../deliveries/:id/redeliver`) and confirm a new delivery row is created and queued, with the original preserved.

**Acceptance Scenarios**:

1. **Given** a delivery that failed with a timeout, **When** the admin views the endpoint's delivery log, **Then** they see `error_type: 'timeout'` and `request_errors` with the exception message.
2. **Given** a failed delivery, **When** the admin triggers redeliver, **Then** a new `WebhookDelivery` is created with the same `event_name`/`payload`, queued for delivery, and the original row is untouched.
3. **Given** an endpoint accumulates 15 consecutive failed deliveries with no interspersed success, **When** the 15th failure completes, **Then** the endpoint is auto-disabled (`active: false`, `disabled_at` set) and a notification email is sent to store staff.

---

### Edge Cases

- What happens when an endpoint URL resolves to a private/internal IP address (SSRF)? → Blocked at validation time (`url_must_not_resolve_to_private_ip`, via the `ssrf_filter` gem) except in development, where localhost/`host.docker.internal` must be reachable for local storefront testing.
- How does the system handle duplicate deliveries for the same event? → `event_id` + `webhook_endpoint_id` has a unique partial index (`WHERE event_id IS NOT NULL`); the subscriber checks for an existing delivery before creating one, and `ActiveRecord::RecordNotUnique` races are swallowed.
- What happens when an event has no `store_id`? → The subscriber skips it entirely (webhooks are store-scoped).
- What happens when `Spree::Api::Config.webhooks_enabled` is false? → The subscriber returns immediately; no deliveries are created for any store.
- What happens on delivery job deserialization failure (e.g., delivery record deleted before the job runs)? → `discard_on ActiveJob::DeserializationError`; the job perform also guards with `return if delivery.nil?`.
- What happens when a delivery is manually redelivered vs. auto-retried? → Auto-retry (`retry_on StandardError`, 5 attempts, polynomial backoff) reruns the same job/delivery; manual redeliver (`redeliver!`) creates a brand-new `WebhookDelivery` row with `event_id: nil` so it can't collide with the dedup index.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow creating, listing, updating, and destroying `Spree::WebhookEndpoint` records scoped to the current store, with `url`, `active`, `subscriptions`, and optional `name`.
- **FR-002**: System MUST generate a random 64-character hex `secret_key` on endpoint creation and expose it in plaintext only in the create response; all subsequent reads MUST serialize it as `nil`.
- **FR-003**: System MUST validate that endpoint URLs use `http`/`https` and do not resolve to a private/internal IP address, except in the `development` environment.
- **FR-004**: System MUST listen to all Spree events (`Spree::WebhookEventSubscriber` subscribes to `'*'`) and, for each event with a `store_id`, find enabled endpoints of that store whose `subscriptions` match the event name (exact match or `*`-wildcard pattern).
- **FR-005**: System MUST create a `Spree::WebhookDelivery` record (event name, event id, payload) per matching endpoint and enqueue `Spree::WebhookDeliveryJob`, deduplicating on `(webhook_endpoint_id, event_id)` when `event_id` is present.
- **FR-006**: System MUST deliver the payload via HTTP POST with headers `Content-Type`, `User-Agent`, `X-Spree-Webhook-Event`, `X-Spree-Webhook-Signature` (HMAC-SHA256 of `"{timestamp}.{payload_json}"` using the endpoint's `secret_key`), and `X-Spree-Webhook-Timestamp`.
- **FR-007**: System MUST record the outcome of every delivery attempt (`response_code`, `execution_time`, `success`, `error_type`, `request_errors`, `response_body`, `delivered_at`) via `WebhookDelivery#complete!`.
- **FR-008**: System MUST retry failed delivery jobs automatically (`retry_on StandardError`, 5 attempts, polynomial backoff) and MUST discard jobs whose delivery record can no longer be deserialized.
- **FR-009**: System MUST auto-disable an endpoint (set `active: false`, `disabled_at`, `disabled_reason`) after 15 consecutive delivery failures with no interspersed success, and notify store staff by email (`Spree::WebhookMailer#endpoint_disabled`).
- **FR-010**: System MUST allow admins to manually enable/disable an endpoint (`enable!` / `disable!`), send a synthetic `webhook.test` delivery (`send_test!`), and redeliver a past delivery as a new, independently-tracked `WebhookDelivery` (`redeliver!`).
- **FR-011**: System MUST expose all of the above through the Admin API v3 (`Spree::Api::V3::Admin::WebhookEndpointsController`, `WebhookDeliveriesController`) under secret-key-scope or JWT+CanCanCan auth, matching serializer read fields to controller `permitted_params` exactly (name, url, active, subscriptions).
- **FR-012**: System MUST provide a global kill switch (`Spree::Api::Config.webhooks_enabled`) and an SSL-verification toggle (`Spree::Api::Config.webhooks_verify_ssl`, defaulting to verified in all environments except explicit opt-out).
- **FR-013**: System MUST allow filtering delivery history via Ransack-whitelisted attributes (`event_name`, `response_code`, `execution_time`, `success`, `delivered_at`, `created_at`) scoped to a single endpoint.

### Key Entities

- **Spree::WebhookEndpoint**: A store-owned destination URL for outbound event notifications. Attributes: `url`, `active`, `subscriptions` (JSON array of event-name patterns, `*` wildcard supported), `secret_key` (encrypted at rest, deterministic), `name`, `disabled_at`/`disabled_reason` (auto/manual disable bookkeeping). Soft-deletable (`acts_as_paranoid`). Belongs to `Spree::Store`; has many `Spree::WebhookDelivery`.
- **Spree::WebhookDelivery**: A single delivery attempt log entry for one endpoint + one event. Attributes: `event_name`, `event_id` (dedup key, nullable), `payload` (JSON), `response_code`, `execution_time` (ms), `error_type` (`timeout`/`connection_error`/nil), `request_errors`, `response_body` (truncated to 10k chars), `success`, `delivered_at`. Belongs to `Spree::WebhookEndpoint`.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/core` (models, services) | Yes | `Spree::WebhookEndpoint`, `Spree::WebhookDelivery` models; `Spree::WebhookMailer`; migrations creating both tables plus a follow-up migration adding `name`/`disabled_reason`/`disabled_at`/`event_id`; deprecated `Spree::Webhooks` legacy disable-flag module |
| `spree/api` (Store/Admin API v3) | Yes | `Spree::Api::V3::Admin::WebhookEndpointsController` (+ `send_test`/`enable`/`disable`), `WebhookDeliveriesController` (+ `redeliver`), Admin serializers, `Spree::Webhooks::DeliverWebhook` service, `Spree::WebhookEventSubscriber`, `Spree::WebhookDeliveryJob`, `Spree::Api::Config` (`webhooks_enabled`, `webhooks_verify_ssl`) |
| `spree/admin` (legacy Rails admin) | Yes | `Spree::Admin::WebhookEndpointsController`, `Spree::Admin::WebhookDeliveriesController` (index/show/redeliver), views + health/status column partials — present but frozen per repo policy (no new legacy-admin features; SPA is canonical going forward) |
| `packages/dashboard` (admin SPA) | Yes | Settings → Webhooks route (`routes/.../settings/webhooks`), `webhook-endpoint-form.tsx`, `webhook-endpoints`/`webhook-deliveries` tables, `use-webhook-endpoints` hook, `webhook-health.ts`, Zod schema |
| `packages/dashboard-ui` / `dashboard-core` | No | No shared primitives/registries specific to webhooks beyond standard table/form components |
| `packages/sdk` / `packages/admin-sdk` | Yes | `packages/sdk/src/webhooks.ts` (`verifyWebhookSignature`, `WebhookEvent` type — consumer-side verification, framework-agnostic); `packages/admin-sdk` generated `WebhookEndpoint`/`WebhookDelivery` types + `webhookEndpoints` resource client |
| `docs/plans/` | No | No `docs/plans/*.md` entry exists for webhooks; feature predates/sits outside the current plan backlog. Not flagged as an open architectural change. |

### API Contract *(include if feature touches spree/api)*

- **Endpoints**: `GET/POST /api/v3/admin/webhook_endpoints`, `GET/PATCH/DELETE /api/v3/admin/webhook_endpoints/:id`, `POST /api/v3/admin/webhook_endpoints/:id/send_test`, `PATCH /api/v3/admin/webhook_endpoints/:id/enable`, `PATCH /api/v3/admin/webhook_endpoints/:id/disable`; `GET /api/v3/admin/webhook_endpoints/:webhook_endpoint_id/deliveries`, `GET .../deliveries/:id`, `POST .../deliveries/:id/redeliver`
- **Serializer fields (read → write)**: `name`, `url`, `active`, `subscriptions` are both serialized and permitted 1:1 (Constitution Principle III honored). `secret_key`, `disabled_at`, `disabled_reason`, `last_delivery_at`, and the delivery-count aggregates are read-only/computed, never accepted on write.
- **Auth**: Admin API — secret API key with scopes, or Admin JWT + CanCanCan (`authorize!(:update, @resource)` on the mutating custom actions). No Store API surface — webhooks are a back-office concern only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A published event with a matching subscribed endpoint results in a queued delivery job within the same request/transaction that published the event (fire-and-forget, non-blocking to the triggering action).
- **SC-002**: A receiving system can verify the authenticity of 100% of legitimate deliveries using only the documented HMAC scheme and the one-time `secret_key`.
- **SC-003**: Transient endpoint failures (timeouts, 5xx) are retried automatically up to 5 times before requiring manual intervention.
- **SC-004**: An endpoint that fails 15 consecutive deliveries is auto-disabled and store staff are notified, preventing indefinite silent failure.
- **SC-005**: Admins can locate and resend any specific past delivery without needing to reproduce the original triggering business event.

## Assumptions

- The feature was implemented and shipped prior to this spec-kit migration (since Spree 5.3); this document reverse-engineers intent from existing code, tests, and `docs/developer/core-concepts/webhooks.mdx` / `docs/api-reference/webhooks-events.mdx` rather than proposing new behavior.
- The legacy Rails admin webhook UI (`spree/admin/app/controllers/spree/admin/webhook_{endpoints,deliveries}_controller.rb`) is considered frozen/deprecated in favor of the `packages/dashboard` SPA per repo-wide policy, even though it remains present and tested.
- No `docs/plans/` entry governs webhooks specifically; it is not currently an active architectural workstream, so none was created as part of this migration.
- Webhook delivery is intentionally decoupled from the Store API — it is exclusively an Admin API / back-office capability.

## Migration Notes

- **HMAC signature verification**: Implemented. `Spree::Webhooks::DeliverWebhook#generate_signature` computes `OpenSSL::HMAC.hexdigest('SHA256', secret_key, "#{timestamp}.#{payload_json}")` and sends it as `X-Spree-Webhook-Signature` alongside `X-Spree-Webhook-Timestamp`. Client-side verification is provided for JS consumers via `verifyWebhookSignature` in `packages/sdk/src/webhooks.ts`; Ruby receivers must reimplement the same HMAC comparison (documented with a full example in `docs/developer/core-concepts/webhooks.mdx`).
- **Retry / delivery-failure handling**: Two independent layers. (1) Job-level: `Spree::WebhookDeliveryJob` retries `StandardError` up to 5 times with polynomial backoff, discards on `ActiveJob::DeserializationError`. (2) Endpoint-level: `WebhookEndpoint#check_auto_disable!` (invoked from `WebhookDelivery#complete!` on failure) auto-disables an endpoint after 15 consecutive failures with no interspersed success, emailing store staff via `Spree::WebhookMailer#endpoint_disabled`. Manual recovery is via `redeliver!` (new tracked delivery, original preserved) and `enable!`/`disable!`.
- **Admin UI for delivery history**: Yes, in two places. Legacy Rails admin (`spree/admin/app/controllers/spree/admin/webhook_deliveries_controller.rb`, index/show/redeliver, with status/health column partials) and the React admin SPA (`packages/dashboard/src/tables/webhook-deliveries.tsx`, `webhook-endpoints.tsx`, `webhook-health.ts`), both backed by the same Admin API v3 endpoints. Filtering is Ransack-based (`success_eq`, `event_name_eq`, etc.).
- **Gap identified**: No `docs/plans/` entry exists for webhooks despite it being a substantial cross-cutting feature (core + api + admin + dashboard + sdk); this migration did not backfill one since no architectural change is pending — flagged here for awareness only.
- **Gap identified**: SSRF protection (`url_must_not_resolve_to_private_ip`) is skipped entirely in `development`, which is correct for local testing but worth noting as an intentional environment-scoped exception rather than a general safeguard.
