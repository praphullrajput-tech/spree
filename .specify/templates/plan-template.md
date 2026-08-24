# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Ruby (Rails 7.2 engines, backend) and/or TypeScript (React SPA, frontend) — [state which side(s) this feature touches]

**Primary Dependencies**: [Backend: CanCanCan, Ransack, Pagy, Alba serializers, state_machines-activerecord. Frontend: TanStack Router/Query, React Hook Form + Zod, shadcn/ui + Base UI — or NEEDS CLARIFICATION]

**Storage**: PostgreSQL (production), SQLite3 (backend test default) — via ActiveRecord, no foreign key constraints per migration conventions

**Testing**: RSpec + Factory Bot (backend, per-gem `spec/`), Vitest (frontend unit, colocated `*.test.ts`), Playwright (`packages/dashboard/e2e`, UI-only assertions — no `waitForResponse`)

**Target Platform**: Rails engine gems consumed by a Spree host app; React SPA served standalone, proxying to the Rails Admin/Store API v3

**Project Type**: Monorepo — Ruby gem(s) under `spree/*` and/or TypeScript package(s) under `packages/*`. State which specific gem(s)/package(s) per the Module Impact table in spec.md.

**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]

**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]

**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Cite each constitution principle (`.specify/memory/constitution.md`) by
numeral and state pass/violate:

- **I. Module Boundaries**: [which gem(s)/package(s) from the Module Impact
  table does this touch — does the plan cross a boundary without going
  through a documented extension point?]
- **II. Admin API Is the Only Frontend Data Source**: [N/A if backend-only;
  otherwise confirm the API endpoint exists/is planned before any SPA work]
- **III. Read/Write Field Symmetry**: [N/A if no serializer changes;
  otherwise confirm `permitted_params` will match serializer output exactly]
- **IV. Test-Backed**: [which test frameworks from Principle IV will cover
  this — RSpec/Vitest/Playwright — and where]
- **V. Translations and Prefixed IDs**: [N/A if no user-visible strings or
  new resource IDs; otherwise confirm i18next keys + prefixed ID usage]
- **VI. `docs/plans/` for Architectural Changes**: [does this qualify per
  the spec.md Module Impact table? If yes, link the `docs/plans/` entry]

Any violation must appear in Complexity Tracking below with justification.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Delete the module blocks below that this feature doesn't
  touch, and expand the remaining ones with the real files/paths this
  feature will add or modify. The delivered plan must not include the
  bracketed placeholders.
-->

```text
# [REMOVE IF UNUSED] spree/core — models, services, business logic
spree/core/
├── app/models/spree/[entity].rb
├── app/models/concerns/spree/[concern].rb
├── app/services/spree/[namespace]/[service].rb
├── app/finders/spree/[namespace]/[finder].rb
├── db/migrate/[timestamp]_[change].rb
└── spec/models/spree/[entity]_spec.rb, spec/services/..., spec/finders/...

# [REMOVE IF UNUSED] spree/api — Store & Admin REST API v3
spree/api/
├── app/controllers/spree/api/v3/{store,admin}/[resource]_controller.rb
├── app/serializers/spree/api/v3/[resource]_serializer.rb
├── app/serializers/spree/api/v3/admin/[resource]_serializer.rb
└── spec/integration/[resource]_spec.rb   # happy-path + simple 422 only

# [REMOVE IF UNUSED] packages/dashboard — admin SPA routes/forms
packages/dashboard/src/
├── routes/_authenticated/$storeId/[section]/[route].tsx
├── hooks/use-[resource].ts
├── schemas/[resource].ts
├── locales/en.json               # + all other locale files, same keys
└── e2e/[resource].spec.ts

# [REMOVE IF UNUSED] packages/dashboard-ui / dashboard-core — shared primitives/registries
packages/dashboard-ui/src/components/[primitive].tsx
packages/dashboard-core/src/{registries,providers}/[name].ts

# [REMOVE IF UNUSED] packages/sdk / packages/admin-sdk — generated + hand-written clients
packages/sdk/src/{types,zod}/generated/   # regenerated, not hand-edited
packages/admin-sdk/src/store-client.ts    # only if adding a hand-written resource method
```

**Structure Decision**: [State which module(s) from the Module Impact table
(spec.md) this plan implements in, and why — e.g., "Backend-only: new
`spree/core` model + `spree/api` Admin endpoint; no dashboard changes needed
this phase."]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
