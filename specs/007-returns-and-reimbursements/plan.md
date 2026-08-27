# Implementation Plan: Returns & Reimbursements

**Branch**: `007-returns-and-reimbursements` | **Date**: 2026-08-24 | **Spec**: `specs/007-returns-and-reimbursements/spec.md`

**Input**: Feature specification from `/specs/007-returns-and-reimbursements/spec.md`

**Note**: This is a brownfield reverse-engineering pass (`/speckit.brownfield.migrate`). The plan below documents the architecture as built, not a forward design — "tasks" in `tasks.md` are retroactive and marked complete.

## Summary

Returns/reimbursements are modeled as a six-model chain in `spree/core`: an admin authorizes a return (`ReturnAuthorization`) against shipped inventory, the warehouse records physical receipt (`CustomerReturn` + `ReturnItem` reception/acceptance state machines with a pluggable eligibility-validator chain), and an admin performs a payout (`Reimbursement`, fanning out to `ReimbursementType` STI subclasses that create `Refund`/`Credit`/`Exchange` records with tax recomputed via `ReimbursementTaxCalculator`). The only write surface is the legacy `spree/admin` Rails engine; `spree/api` exposes the chain read-only as expandable nested attributes on the Admin order/reimbursement serializers. `spree/emails` sends one transactional email (`reimbursement.reimbursed` → `ReimbursementMailer`). No `packages/dashboard` (React SPA) code exists for this domain.

## Technical Context

**Language/Version**: Ruby (Rails 7.2 engines) — this feature is backend-only; no TypeScript/frontend code touches it.

**Primary Dependencies**: `state_machines-activerecord` (two independent state machines: `ReturnAuthorization#state`, `ReturnItem#reception_status` + `#acceptance_status`, `Reimbursement#reimbursement_status`), Alba serializers (read-only nested attributes), CanCanCan (legacy admin `ResourceController` authorization), `Spree::Core::NumberGenerator`/`Spree::NumberIdentifier` (RA/CR/RI number prefixes), `Spree::DisplayMoney` (money formatting), ActionMailer (`spree/emails`).

**Storage**: PostgreSQL/MySQL/SQLite via ActiveRecord. Relevant tables: `spree_return_authorizations`, `spree_return_authorization_reasons`, `spree_customer_returns`, `spree_return_items`, `spree_reimbursements`, `spree_reimbursement_types`, `spree_refunds`. Migration history for this domain predates this reverse-engineering pass except the most recent addition, `spree/core/db/migrate/20250304115943_add_performed_by_to_spree_reimbursements.rb`.

**Testing**: RSpec + Factory Bot in `spree/core/spec/models/spree/` — `return_authorization_spec.rb`, `customer_return_spec.rb`, `return_item_spec.rb` (+ `return_item/eligibility_validator/no_reimbursements_spec.rb`), `reimbursement_spec.rb` (+ `reimbursement/reimbursement_type_engine_spec.rb`, `reimbursement/reimbursement_type_validator_spec.rb`), `reimbursement_performer_spec.rb`, `reimbursement_tax_calculator_spec.rb`, `returns_calculator_spec.rb`, `reimbursement_type/*`, and `spree/core/spec/services/spree/seeds/returns_environment_spec.rb`. No frontend tests exist (no dashboard code).

**Target Platform**: Rails engine gems (`spree_core`, `spree_admin`, `spree_api`, `spree_emails`) consumed by a Spree host app.

**Project Type**: Monorepo, backend-only for this feature — `spree/core` (models/state machines), `spree/admin` (legacy CRUD UI, the only write path), `spree/api` (read-only serializer exposure), `spree/emails` (deprecated notification mailer/subscriber).

**Performance Goals**: N/A — no stated throughput targets; existing behavior only.

**Constraints**: No FK constraints (repo-wide convention); reimbursement rounding tolerance is `(number_of_distinct_reimbursement_types_used - 1) * $0.01` per `Reimbursement#unpaid_amount_within_tolerance?`.

**Scale/Scope**: 6 core models + 5 eligibility validators + 4 `ReimbursementType` STI subclasses + 1 tax calculator + 3 legacy admin controllers + 1 mailer/subscriber pair + 6 read-only Alba serializers. No migrations, API endpoints, or SPA surface added by this migration pass (documentation only).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches `spree/core` (models), `spree/admin` (legacy controllers — write path), `spree/api` (read-only serializers), `spree/emails` (mailer/subscriber). All coupling is within-gem or via the documented Alba serializer / event-subscriber extension points (`publish_event`/`Spree::Subscriber`) — no gem reaches across a boundary directly. **Pass.**
- **II. Admin API Is the Only Frontend Data Source**: N/A for this migration (no `packages/dashboard` code exists for this domain, and none is being added). Flagged in spec.md Migration Notes that any future SPA work here must add the missing Admin API write endpoints first. **Pass (N/A, gap documented).**
- **III. Read/Write Field Symmetry**: N/A — no serializer changes in this migration; existing serializers are read-only (no corresponding `permitted_params` on the API side since there is no API controller). The legacy admin controllers use `permitted_return_authorization_attributes` / `permitted_reimbursement_attributes` / `permitted_customer_return_attributes` from the global `Spree::PermittedAttributes` allowlist (pre-v3-convention, not touched here). **Pass (N/A, no changes made).**
- **IV. Test-Backed**: Existing RSpec coverage enumerated above under Testing; this migration adds no new code, so no new tests are required — the retroactive task list in tasks.md cites the existing specs as already satisfying this principle. **Pass.**
- **V. Translations and Prefixed IDs**: No user-visible strings added (legacy admin already uses `Spree.t`/i18n YAML, not i18next, since it's outside `packages/dashboard`). Prefixed IDs (`ra_`, `rar_`, `cr_`, `ri_`, `reimb_`, `rtype_`) are already used throughout the serializers and `has_prefix_id` declarations. **Pass.**
- **VI. `docs/plans/` for Architectural Changes**: This domain is already governed by `docs/plans/6.0-returns-exchanges-claims.md` (Draft), which plans to delete every model this spec documents in favor of `Return`/`Exchange`/`Claim`. This migration doesn't implement that plan — it documents current state — but per Principle VI its "Constraints on Current Work" section binds any future extension of the current models. **Pass, with cross-reference recorded.**

No violations — Complexity Tracking table omitted.

## Project Structure

### Documentation (this feature)

```text
specs/007-returns-and-reimbursements/
├── plan.md              # This file
└── tasks.md             # Retroactive task list (all marked complete)
```

No `research.md`, `data-model.md`, `contracts/`, or `quickstart.md` were generated — this is a reverse-engineering pass documenting shipped behavior, not a forward `/speckit-plan` design cycle.

### Source Code (repository root)

```text
# spree/core — models, services, business logic (existing, documented not authored here)
spree/core/app/models/spree/return_authorization.rb
spree/core/app/models/spree/return_authorization_reason.rb
spree/core/app/models/spree/customer_return.rb
spree/core/app/models/spree/return_item.rb
spree/core/app/models/spree/return_item/eligibility_validator/base_validator.rb
spree/core/app/models/spree/return_item/eligibility_validator/default.rb
spree/core/app/models/spree/return_item/eligibility_validator/order_completed.rb
spree/core/app/models/spree/return_item/eligibility_validator/time_since_purchase.rb
spree/core/app/models/spree/return_item/eligibility_validator/rma_required.rb
spree/core/app/models/spree/return_item/eligibility_validator/inventory_shipped.rb
spree/core/app/models/spree/return_item/eligibility_validator/no_reimbursements.rb
spree/core/app/models/spree/reimbursement.rb
spree/core/app/models/spree/reimbursement_type.rb
spree/core/app/models/spree/reimbursement_type/credit.rb
spree/core/app/models/spree/reimbursement_type/exchange.rb
spree/core/app/models/spree/reimbursement_type/original_payment.rb
spree/core/app/models/spree/reimbursement_type/store_credit.rb
spree/core/app/models/spree/reimbursement_type/reimbursement_helpers.rb
spree/core/app/models/spree/reimbursement_tax_calculator.rb
spree/core/app/services/spree/seeds/returns_environment.rb
spree/core/db/migrate/20250304115943_add_performed_by_to_spree_reimbursements.rb
spree/core/spec/models/spree/return_authorization_spec.rb
spree/core/spec/models/spree/customer_return_spec.rb
spree/core/spec/models/spree/return_item_spec.rb
spree/core/spec/models/spree/return_item/eligibility_validator/no_reimbursements_spec.rb
spree/core/spec/models/spree/reimbursement_spec.rb
spree/core/spec/models/spree/reimbursement_performer_spec.rb
spree/core/spec/models/spree/reimbursement_tax_calculator_spec.rb
spree/core/spec/models/spree/returns_calculator_spec.rb
spree/core/spec/models/spree/reimbursement/reimbursement_type_engine_spec.rb
spree/core/spec/models/spree/reimbursement/reimbursement_type_validator_spec.rb
spree/core/spec/services/spree/seeds/returns_environment_spec.rb

# spree/admin — legacy Rails admin (only write surface today)
spree/admin/app/controllers/spree/admin/orders/return_authorizations_controller.rb
spree/admin/app/controllers/spree/admin/orders/customer_returns_controller.rb
spree/admin/app/controllers/spree/admin/reimbursements_controller.rb
spree/admin/app/views/spree/admin/orders/return_authorizations/
spree/admin/app/views/spree/admin/orders/customer_returns/
spree/admin/app/views/spree/admin/reimbursements/
spree/admin/app/views/spree/admin/reimbursement_types/
spree/admin/app/views/spree/admin/return_authorization_reasons/
spree/admin/app/views/spree/admin/shared/_returns_and_refunds_nav.html.erb

# spree/api — Store & Admin REST API v3 (read-only, nested only — no dedicated controller)
spree/api/app/serializers/spree/api/v3/return_authorization_serializer.rb
spree/api/app/serializers/spree/api/v3/customer_return_serializer.rb
spree/api/app/serializers/spree/api/v3/return_item_serializer.rb
spree/api/app/serializers/spree/api/v3/reimbursement_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/reimbursement_serializer.rb
spree/api/app/serializers/spree/api/v3/refund_serializer.rb
spree/api/app/serializers/spree/api/v3/admin/order_serializer.rb   # expand?('return_authorizations'/'reimbursements')

# spree/emails — transactional email (deprecated in 6.0)
spree/emails/app/subscribers/spree/reimbursement_email_subscriber.rb
spree/emails/app/mailers/spree/reimbursement_mailer.rb
```

**Structure Decision**: Backend-only, spanning four gems (`spree/core`, `spree/admin`, `spree/api`, `spree/emails`) per the Module Impact table in spec.md. No `packages/*` frontend work exists or is proposed by this migration — the admin SPA has zero presence in this domain today, which is recorded as a gap rather than filled here.

## Complexity Tracking

*No violations — table omitted per template instructions.*
