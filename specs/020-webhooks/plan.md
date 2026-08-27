# Implementation Plan: Webhooks

**Branch**: `020-webhooks` | **Date**: 2026-08-25 | **Spec**: `specs/020-webhooks/spec.md`

**Input**: Feature specification from `specs/020-webhooks/spec.md`

**Note**: This document reverse-engineers the plan for an already-shipped feature (brownfield migration), describing the implementation as built rather than prescribing new work.

## Summary

Outbound webhook delivery: `Spree::WebhookEndpoint` (store-owned destination + subscriptions + HMAC secret) and `Spree::WebhookDelivery` (per-attempt audit log) in `spree/core`; event fan-out (`Spree::WebhookEventSubscriber`, subscribed to `'*'`), HMAC-signed HTTP delivery (`Spree::Webhooks::DeliverWebhook`), and retrying background delivery (`Spree::WebhookDeliveryJob`) in `spree/api`; full CRUD + `send_test`/`enable`/`disable`/`redeliver` custom actions on the Admin API v3; a legacy Rails admin UI and a React admin SPA UI (Settings → Webhooks) consuming that API; and a framework-agnostic signature-verification helper shipped in `@spree/sdk` for external receivers.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines: `spree/core`, `spree/api`, `spree/admin`) and TypeScript (`packages/dashboard`, `packages/sdk`, `packages/admin-sdk`)

**Primary Dependencies**: CanCanCan (admin authorization), Ransack (delivery-log filtering), Pagy (pagination), Alba serializers, `ssrf_filter` gem (endpoint URL validation), `openssl`/`Net::HTTP` (signed delivery), `state_machines-activerecord` not used here (status is plain boolean `active` + `disabled_at`/`disabled_reason`). Frontend: TanStack Router/Query, React Hook Form + Zod, shadcn/ui + Base UI.

**Storage**: PostgreSQL/MySQL/SQLite via ActiveRecord — `spree_webhook_endpoints` and `spree_webhook_deliveries` tables, no foreign key constraints, JSON/JSONB `subscriptions` and `payload` columns guarded with `respond_to?(:jsonb)`.

**Testing**: RSpec + Factory Bot (`spree/core/spec/models/spree/webhook_{endpoint,delivery}_spec.rb`, `spree/api/spec/{services,subscribers,jobs,controllers,integration}/...`, `spree/admin/spec/controllers/...`); Vitest (`packages/sdk/tests/webhooks.test.ts`, `packages/admin-sdk/tests/webhook-endpoints.test.ts`); Playwright (`packages/dashboard/e2e/webhooks.spec.ts`).

**Target Platform**: Rails engine gems consumed by a Spree host app; React SPA served standalone, proxying to the Rails Admin API v3; external receivers are arbitrary third-party HTTP services.

**Project Type**: Monorepo — spans `spree/core`, `spree/api`, `spree/admin` (legacy), `packages/dashboard`, `packages/sdk`, `packages/admin-sdk`.

**Performance Goals**: Delivery is fully asynchronous (ActiveJob-queued); publishing an event must not block on the outbound HTTP call. `TIMEOUT = 30` seconds per delivery attempt (open + read timeout).

**Constraints**: No FK constraints (repo migration convention); endpoint URLs must not resolve to private/internal IPs outside development (SSRF protection via `ssrf_filter` + `Resolv`); `secret_key` encrypted at rest (`encrypts ... deterministic: true`) and exposed in plaintext exactly once (create response only).

**Scale/Scope**: Per-store fan-out over "all Spree events" (subscriber is a global `'*'` listener); dedup via a unique partial index on `(webhook_endpoint_id, event_id)`; auto-disable threshold fixed at 15 consecutive failures (`AUTO_DISABLE_THRESHOLD`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (models, mailer, migrations), `spree/api` (controllers, serializers, service, subscriber, job, config), `spree/admin` (legacy UI, present but frozen), `packages/dashboard` (SPA UI), `packages/sdk`/`packages/admin-sdk` (client verification + generated types). Crossing is via the documented Dependencies/Events system (`publish_event` → subscriber → job) and the Admin API — no gem reaches directly into another's internals. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: `packages/dashboard`'s webhook UI (`use-webhook-endpoints.ts`, tables, form) calls only `@spree/admin-sdk`, which hits `Spree::Api::V3::Admin::WebhookEndpointsController`/`WebhookDeliveriesController`. No server-rendered HTML or direct model access from the SPA. **Pass.**
- **III. Read/Write Field Symmetry**: `WebhookEndpointSerializer` exposes `name`, `url`, `active`, `subscriptions` for read; `WebhookEndpointsController#permitted_params` permits exactly those four (plus none extra). Computed/audit fields (`secret_key`, `disabled_at`, delivery counts) are read-only and never accepted on write, which is correct (they aren't client-settable data). **Pass.**
- **IV. Test-Backed**: RSpec covers models (`webhook_endpoint_spec.rb`, `webhook_delivery_spec.rb`), service (`deliver_webhook_spec.rb`), subscriber (`webhook_event_subscriber_spec.rb`), job (`webhook_delivery_job_spec.rb`), controllers + integration specs for both API and legacy admin. Vitest covers `@spree/sdk` signature verification and `@spree/admin-sdk` resource client. Playwright covers the SPA flow end-to-end (`webhooks.spec.ts`). **Pass.**
- **V. Translations and Prefixed IDs**: `WebhookEndpoint`/`WebhookDelivery` use `has_prefix_id :whe` / `:whd` and are always serialized/looked-up via `find_by_prefix_id!`. SPA strings run through i18next per the dashboard's locale files (verified present in the webhook table/form components at a glance; not independently re-audited key-by-key in this migration pass). **Pass** (with the caveat noted).
- **VI. `docs/plans/` for Architectural Changes**: No `docs/plans/` entry exists for webhooks, and none is required going forward — it's a shipped, stable feature, not an open architectural change. **N/A / Pass.**

No violations — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/020-webhooks/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
# spree/core — models, services, business logic
spree/core/app/models/spree/webhook_endpoint.rb
spree/core/app/models/spree/webhook_delivery.rb
spree/core/app/mailers/spree/webhook_mailer.rb
spree/core/app/views/spree/webhook_mailer/
spree/core/lib/spree/webhooks.rb                       # deprecated legacy disable-flag shim
spree/core/lib/spree/testing_support/factories/webhook_endpoint_factory.rb
spree/core/lib/spree/testing_support/factories/webhook_delivery_factory.rb
spree/core/db/migrate/20251214000001_create_spree_webhook_endpoints.rb
spree/core/db/migrate/20251214000002_create_spree_webhook_deliveries.rb
spree/core/db/migrate/20260326000001_improve_spree_webhooks.rb
spree/core/spec/models/spree/webhook_endpoint_spec.rb
spree/core/spec/models/spree/webhook_delivery_spec.rb

# spree/api — Admin REST API v3 + delivery pipeline
spree/api/app/controllers/spree/api/v3/admin/webhook_endpoints_controller.rb
spree/api/app/controllers/spree/api/v3/admin/webhook_deliveries_controller.rb
spree/api/app/serializers/spree/api/v3/admin/webhook_endpoint_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/webhook_delivery_serializer.rb
spree/api/app/services/spree/webhooks/deliver_webhook.rb
spree/api/app/subscribers/spree/webhook_event_subscriber.rb
spree/api/app/jobs/spree/webhook_delivery_job.rb
spree/api/lib/spree/api/testing_support/spree_webhooks.rb
spree/api/lib/spree/api/testing_support/matchers/webhooks.rb
spree/api/spec/controllers/spree/api/v3/admin/webhook_{endpoints,deliveries}_controller_spec.rb
spree/api/spec/integration/spree/api/v3/admin/webhook_{endpoints,deliveries}_spec.rb
spree/api/spec/services/spree/webhooks/deliver_webhook_spec.rb
spree/api/spec/subscribers/spree/webhook_event_subscriber_spec.rb
spree/api/spec/jobs/spree/webhook_delivery_job_spec.rb

# spree/admin — legacy Rails admin (frozen, not extended further)
spree/admin/app/controllers/spree/admin/webhook_endpoints_controller.rb
spree/admin/app/controllers/spree/admin/webhook_deliveries_controller.rb
spree/admin/app/helpers/spree/admin/webhook_endpoints_helper.rb
spree/admin/app/views/spree/admin/webhook_endpoints/
spree/admin/app/views/spree/admin/webhook_deliveries/
spree/admin/app/views/spree/admin/tables/columns/_webhook_{delivery_status,delivery_actions,endpoint_health,deliveries_stats}.html.erb
spree/admin/spec/controllers/spree/admin/webhook_{endpoints,deliveries}_controller_spec.rb

# packages/dashboard — admin SPA routes/forms
packages/dashboard/src/routes/_authenticated/$storeId/settings/webhooks/$webhookEndpointId.tsx
packages/dashboard/src/components/spree/webhook-endpoint-form.tsx
packages/dashboard/src/hooks/use-webhook-endpoints.ts
packages/dashboard/src/lib/webhook-health.ts
packages/dashboard/src/schemas/webhook-endpoint.ts
packages/dashboard/src/tables/webhook-endpoints.tsx
packages/dashboard/src/tables/webhook-deliveries.tsx
packages/dashboard/e2e/webhooks.spec.ts

# packages/sdk / packages/admin-sdk — client verification + generated types
packages/sdk/src/webhooks.ts                            # verifyWebhookSignature, WebhookEvent type
packages/sdk/tests/webhooks.test.ts
packages/admin-sdk/src/types/generated/WebhookEndpoint.ts
packages/admin-sdk/src/types/generated/WebhookDelivery.ts
packages/admin-sdk/examples/webhook-endpoints/
packages/admin-sdk/tests/webhook-endpoints.test.ts
```

**Structure Decision**: Full-stack feature spanning every layer of the Module Impact table except `packages/dashboard-ui`/`dashboard-core` (no shared primitives were needed beyond existing table/form components) and the Store API (webhooks are Admin-API-only, back-office concern).

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
