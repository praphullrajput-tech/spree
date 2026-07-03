# Feature Specification: [FEATURE NAME]

**Feature Branch**: `[###-feature-name]`

**Created**: [DATE]

**Status**: Draft

**Input**: User description: "$ARGUMENTS"

**Active Plan (if applicable)**: `docs/plans/[plan-file].md` — check "Constraints on Current Work" before designing

---

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE — if you implement just ONE,
  you should still have a viable MVP that delivers value.

  Assign priorities (P1, P2, P3…). Think of each story as a standalone slice that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated independently
-->

### User Story 1 — [Brief Title] (Priority: P1)

[Describe this user journey in plain language. For admin features, describe the admin operator's perspective. For API features, describe what the API consumer can do.]

**Why this priority**: [Explain the value and why it ranks first]

**Independent Test**: [How this can be tested on its own — e.g., "Admin can navigate to /products, create a product, and see it in the list"]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]
2. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 2 — [Brief Title] (Priority: P2)

[Description]

**Why this priority**: [Explanation]

**Independent Test**: [How to verify independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

- What happens when [boundary condition]?
- How does the system handle [error scenario]?
- What if the store has no [related resource]?

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: [Specific capability — what the system MUST do]
- **FR-002**: [Specific capability]
- **FR-003**: [Key interaction]

*Mark unclear requirements as `[NEEDS CLARIFICATION: reason]`*

### Key Entities *(include when the feature involves data)*

- **[Entity]**: [What it represents; key attributes without implementation detail; relationships]

---

## Backend Requirements *(include when feature touches Ruby/Rails)*

### Data Model Changes

- **New model**: `Spree::[Name]` — [purpose]; key attributes: [list]
- **Migration**: [what changes — new table, new column, index]; target: `ActiveRecord::Migration[7.2]`
- **Associations**: [belongs_to / has_many with `class_name:` and `dependent:`]
- **Soft delete**: [yes/no — paranoia `acts_as_paranoid`]

### API Surface

#### Store API *(customer-facing — read-only by default)*

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/[resources]` | List [resources] |
| GET | `/api/v3/[resources]/:id` | Show [resource] |

#### Admin API *(back-office — full CRUD by default)*

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v3/admin/[resources]` | List [resources] |
| GET | `/api/v3/admin/[resources]/:id` | Show [resource] |
| POST | `/api/v3/admin/[resources]` | Create [resource] |
| PATCH | `/api/v3/admin/[resources]/:id` | Update [resource] |
| DELETE | `/api/v3/admin/[resources]/:id` | Delete [resource] |

### Serializer Fields

**Store serializer** (`Spree::Api::V3::[Resource]Serializer`):
- [field]: [type] — [description; note: no timestamps, no cost/internal data]

**Admin serializer** (`Spree::Api::V3::Admin::[Resource]Serializer`, extends Store):
- [field]: [type] — [admin-only attribute]
- `created_at`, `updated_at`, `deleted_at` (when paranoid)

### Authorization

- CanCanCan ability: `can :manage, Spree::[Resource]` for admin; `can :read, Spree::[Resource]` for store
- Ransack allowlist additions: [which attributes/scopes to expose]

### i18n (Rails)

- New keys in `spree/[engine]/config/locales/en.yml` under `spree.[section].[key]`

---

## Frontend Requirements *(include when feature touches the React SPA)*

### SPA Route(s)

- `packages/dashboard/src/routes/_authenticated/$storeId/[resource]/index.tsx` — list page
- `packages/dashboard/src/routes/_authenticated/$storeId/[resource]/$[id].tsx` — detail/edit

### Resource Hook(s)

- `packages/dashboard/src/hooks/use-[resource]s.ts` — wraps Admin SDK calls via TanStack Query

### Form Schema

- `packages/dashboard/src/schemas/[resource].ts` — Zod schema + `FormValues` type + defaults

### Component(s)

- [New component or reused component from `packages/dashboard-ui/src/`]
- All data via props; no direct provider/hook imports in `dashboard-ui` components

### i18n Keys (TypeScript)

New keys must be added to **all** locale files:
- `packages/dashboard/src/locales/en.json` under `admin.[resource].[key]`
- Repeat for every other locale file in the same directory

Key categories: page titles, column headers, button labels, empty states, toast messages, form labels/placeholders/help text, badge/status text.

### Drag-and-drop *(include if model uses `acts_as_list`)*

- Top-level resource tables: use `reorder` prop on `<ResourceTable>`
- Nested collections: dnd-kit with `useFieldArray.move()` + computed `position`

### Date/time fields *(include if feature has date inputs)*

- Use `<StoreDatePicker>` exclusively — never `<Input type="date">`
- Inside a `<Sheet>`: pass `inline` prop

---

## Success Criteria *(mandatory)*

- **SC-001**: [Measurable outcome — e.g., "Admin can create a [resource] in under 3 steps"]
- **SC-002**: [API contract — e.g., "GET /api/v3/admin/[resources] returns paginated list with prefixed IDs"]
- **SC-003**: [UI acceptance — e.g., "List page renders within 1s on first load; empty state visible when no records exist"]

---

## Assumptions

- [Assumption about scope or environment]
- [Assumption about existing infrastructure — auth, store context, etc.]
- [Out-of-scope items for this iteration]
