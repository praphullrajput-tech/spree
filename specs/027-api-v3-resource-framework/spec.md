# Feature Specification: API v3 Resource Framework

**Feature Branch**: `027-api-v3-resource-framework`

**Created**: 2026-08-25

**Status**: migrated

**Input**: Reverse-engineered from existing code (brownfield migration) — no original feature request survives; behavior below is inferred from `spree/api/app/controllers/spree/api/v3/` and its concerns.

## User Scenarios & Testing *(mandatory)*

<!--
  This is an internal framework/extension-point feature, not a user-facing
  one. "User" here means a Spree core/extension developer adding a new
  Store or Admin API v3 resource controller.
-->

### User Story 1 - Add a new Admin API resource with full CRUD (Priority: P1)

A developer adds a new admin-manageable model (e.g. `Spree::Foo`) to the Admin API. They create `Spree::Api::V3::Admin::FoosController < ResourceController`, override `model_class` and `serializer_class`, and get `index`/`show`/`create`/`update`/`destroy` for free — including pagination, Ransack filtering, prefixed-ID lookups, CanCanCan authorization, and JSON:API-ish `sort=` parsing — without writing any action bodies.

**Why this priority**: This is the dominant use case — the large majority of the ~300 Admin API endpoints are plain `ResourceController` subclasses with only `model_class`/`serializer_class`/`scope` overridden. If this path doesn't work cleanly, every other admin endpoint pays the cost.

**Independent Test**: Subclass `Admin::ResourceController`, override only `model_class`/`serializer_class`, wire a route, and confirm all five REST actions work against a fresh model with no controller code beyond the two overrides.

**Acceptance Scenarios**:

1. **Given** a new `Admin::FoosController` with only `model_class`/`serializer_class` overridden, **When** a JWT-authenticated admin with the right CanCanCan ability calls `GET /api/v3/admin/foos`, **Then** the response returns a paginated, Ransack-filterable, store-scoped collection with pagination `meta`.
2. **Given** the same controller, **When** an admin POSTs invalid attributes, **Then** the response is a 422 with field-level validation errors (no custom `create` code needed).
3. **Given** a secret API key lacking the resource's scope, **When** it calls any action, **Then** the request is rejected before reaching the controller action (scope-based, not CanCanCan-based, per `Spree::Api::V3::ScopedAuthorization`).

---

### User Story 2 - Add a new Store API resource, read-only by default (Priority: P1)

A developer exposes a customer-facing resource (e.g. product categories) via `Store::ResourceController`. By default only `index`/`show` are routed; write actions are opted into per-resource (e.g. carts, customers, addresses) rather than inherited automatically.

**Why this priority**: The Store API's safety posture (read-only unless explicitly opened up) is a deliberate default that every new storefront-facing resource depends on to avoid accidentally exposing mutation endpoints.

**Independent Test**: Add a `Store::CategoriesController < ResourceController` with only `model_class`/`serializer_class`/`scope`, wire only `index`/`show` routes, and confirm `POST`/`PATCH`/`DELETE` are simply unrouted (404), not 403 — the safety comes from routing, not a controller-level lockout.

**Acceptance Scenarios**:

1. **Given** a publishable-key request, **When** it calls `GET /api/v3/store/categories`, **Then** the collection is scoped to the current store, guest-cacheable, and channel/storefront-gating (`StorefrontGating`) applies (`login_required` / `prices_hidden` postures).
2. **Given** a resource that does opt into writes (e.g. `Store::CartsController`), **When** an unauthenticated guest POSTs, **Then** the guest-cart-token flow (`X-Spree-Token`) authorizes the mutation without a customer JWT.

---

### User Story 3 - Resource with legacy-name write bridge (Priority: P2)

A model's public API field name differs from its underlying column (e.g. `label` vs. `presentation`). A developer adds the reader/writer alias pair on the model, and the controller's `permitted_params` (or the shared `Spree::PermittedAttributes` list) permits only the public name — no controller- or SDK-side translation.

**Why this priority**: Read/write field symmetry is a non-negotiable constitutional rule (Principle III); the framework must make it the path of least resistance, not an opt-in developers have to remember.

**Independent Test**: Confirm the serializer's exposed attribute name and the controller's accepted write param name are textually identical for a legacy-column-backed resource, with the translation living in a model-level `attr=` alias.

**Acceptance Scenarios**:

1. **Given** `Spree::OptionType#label`/`label=` aliasing `presentation`/`presentation=`, **When** a client PATCHes `{ label: "Color" }`, **Then** the model's `presentation` column is updated and the serializer echoes back `label`.

---

### User Story 4 - Nested resource under a parent (Priority: P3)

A developer adds a resource nested under another (e.g. wishlist items under a wishlist, promotion rules under a promotion). They override `set_parent` to load `@parent` and call `authorize_parent!`, and override `parent_association` if it doesn't match `controller_name`. `scope`, `build_resource`, and the parent-ability mapping (`parent_ability_action`) all key off `@parent` automatically.

**Why this priority**: Nesting is common (STI subclass resources, cart line items, wishlist items) but is a layered extension on top of the P1 flows, not the base case.

**Independent Test**: Add a nested controller that only implements `set_parent`, confirm `index`/`create` operate against `@parent.send(parent_association)` and that a role permitted to view the parent but not update it can read but not mutate the nested collection.

**Acceptance Scenarios**:

1. **Given** a nested controller under `@parent`, **When** `index` is called, **Then** `scope` returns `@parent.send(parent_association)` rather than a store-wide `model_class` scope.
2. **Given** a role with `:show` but not `:update` on the parent, **When** it POSTs to the nested collection, **Then** `authorize_parent!` (mapped via `parent_ability_action`) rejects the write with 403.

### Edge Cases

- What happens when a subclass doesn't override `model_class`/`serializer_class`? `NotImplementedError` is raised — a loud failure at boot/first-request rather than a silent misbehavior.
- How does the framework handle a `destroy` on a resource whose model defines `can_be_deleted?` returning false? Renders 422 (`validation_error`), not 403 — the caller is authorized, the resource's state is what blocks the operation.
- How are Stripe-style prefixed IDs handled in Ransack query params (e.g. `q[product_id_in][]=prod_x`)? Decoded before being handed to Ransack, for both FK predicates and the bare `id_*` predicates on the resource's own primary key.
- What happens when a client sends `q[with_option_value_ids]` (a custom Ransack scope, not a predicate)? Left undecoded — the regex requires a recognized predicate suffix, so scope names aren't mistaken for ID predicates.
- How does bulk-tagging behave when `ids` is omitted vs. an empty array? Omitted → 422 (`missing_ids`); empty array → treated as a valid no-op.
- How does an STI resource (`PaymentMethod`, `PromotionAction`, `PromotionRule`) resolve its concrete subclass on `create`? Via `subclassed_via` registry lookup on `params[:type]`; unknown type → 422 with a per-controller error code.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The framework MUST provide a base `Spree::Api::V3::ResourceController` implementing `index`, `show`, `create`, `update`, `destroy` against an overridable `model_class`/`serializer_class`, requiring no action-body code in the common case.
- **FR-002**: The framework MUST separate Store API and Admin API concerns into distinct subclasses (`Store::ResourceController`, `Admin::ResourceController`) that plug in different authentication (`authenticate_api_key!` vs. `authenticate_admin!`) while sharing all collection/resource/authorization logic.
- **FR-003**: The framework MUST scope every collection and resource lookup through `scope`, which applies store-scoping (`for_store`), CanCanCan (`accessible_by`), and — for nested resources — the parent association, so controllers cannot accidentally bypass authorization by querying `model_class` directly.
- **FR-004**: The framework MUST support prefixed (Stripe-style) IDs transparently: decoding them in path params (`find_by_prefix_id!`), in Ransack query predicates (`q[*_id_in]`), and in write params (`ParamsNormalizer`).
- **FR-005**: The framework MUST provide Ransack-based filtering, JSON:API-style `sort=-field,field` parsing (translated to Ransack `s=`), and Pagy-based pagination with a consistent `meta` shape on every `index` response.
- **FR-006**: The framework MUST allow per-controller overrides for `collection_includes`, `scope_includes`, `collection_distinct?`, and `apply_collection_sort` to handle N+1 avoidance and custom sorting without re-implementing `collection`.
- **FR-007**: The framework MUST support two independent Admin API authorization models converging on the same controllers: secret API key + scopes (`ScopedAuthorization`), and JWT + CanCanCan — both authorizing the same action methods.
- **FR-008**: The framework MUST support nested resources via `set_parent`/`@parent`/`parent_association`, with `authorize_parent!` mapping read vs. write actions to `:show` vs. `:update` on the parent.
- **FR-009**: The framework MUST provide a shared bulk-tagging concern (`BulkOperations`) and an STI-subclass create/update concern (`SubclassedResource`) as opt-in mixins rather than baking them into the base controller.
- **FR-010**: `destroy` MUST defer to a model's `can_be_deleted?` (422 on false) when defined, distinguishing "authorized but blocked by state" from CanCanCan's 403 ("not authorized").
- **FR-011**: The framework MUST attach rate-limit headers, security headers, locale/currency/market resolution, and channel resolution uniformly across Store and Admin controllers via shared concerns, not per-controller code.

### Key Entities *(include if feature involves data)*

- **ResourceController hierarchy**: `BaseController` (auth-agnostic infra: rate limiting, locale/currency, JWT/API-key auth methods, security headers) → `ResourceController` (CRUD actions + scoping/pagination/ransack) → `Store::ResourceController` / `Admin::ResourceController` (concrete auth wiring) → concrete per-model controllers.
- **Scope**: the ability- and store-scoped `ActiveRecord::Relation` every action reads/writes through; the framework's sole sanctioned data-access seam.
- **Permitted params**: the write-side allowlist, inferred by default from `Spree::PermittedAttributes` keyed off `model_class.model_name.element`, overridable per controller.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/api` (Store/Admin API v3) | Yes | This *is* the framework: `app/controllers/spree/api/v3/{base_controller,resource_controller}.rb`, `store/`, `admin/` base+resource controllers, and the concerns in `app/controllers/concerns/spree/api/v3/` (`params_normalizer`, `bulk_operations`, `channel_resolution`, `storefront_gating`, `locale_and_currency`, `rate_limit_headers`, `security_headers`, `admin/subclassed_resource`, etc.) |
| `spree/core` (models, services) | No | Consumed via `Spree.base_class`, `Spree::PermittedAttributes`, `Spree::PrefixedId`, `Spree::Ability` — not modified by this feature |
| `packages/dashboard` / `packages/sdk` / `packages/admin-sdk` | No | Downstream consumers of the ~300 endpoints this framework underlies; not part of this feature's surface |
| `docs/plans/` | Yes (reference only) | Governed by `docs/plans/6.0-admin-api.md` (Admin REST API conventions) — no new plan entry needed for this migrated spec |

### API Contract *(include if feature touches spree/api)*

- **New/changed endpoints**: None — this is the shared framework underlying all existing `/api/v3/store/*` and `/api/v3/admin/*` endpoints, not a new endpoint itself.
- **Serializer fields (read)**: N/A at the framework level — enforced per-resource via Constitution Principle III (read/write field symmetry). The framework's contribution is `ParamsNormalizer` (prefixed-ID + nested-attribute normalization) and the default `permitted_attributes` inference from `Spree::PermittedAttributes`.
- **Auth**: All four credential types (Store publishable key, Admin secret key + scopes, JWT for both APIs, Store API guest cart token) converge on this framework's `authenticate_request!` seam.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new Admin API resource with standard CRUD needs only two required method overrides (`model_class`, `serializer_class`) to become fully functional — no action bodies.
- **SC-002**: Every `index` response across ~300 Admin + Store endpoints returns the same `{ data, meta }` shape with identical pagination fields (`page`, `limit`, `count`, `pages`, `from`, `to`, `previous`, `next`).
- **SC-003**: 100% of prefixed-ID inputs (path params, Ransack predicates, write params) are decoded before touching the database — no raw integer IDs are ever exposed in responses.
- **SC-004**: Zero controllers implement their own rate-limiting, security-header, or locale/currency resolution logic — all inherited from shared concerns.

## Migration Notes

This spec documents an existing framework rather than proposing a new one.
The stable public contract subclasses build against — the set of methods
`ResourceController` defines as override points — is:

- **`model_class`** — required. The ActiveRecord class this controller manages. Raises `NotImplementedError` if unset.
- **`serializer_class`** — required. The Alba serializer used for `show`/`create`/`update`/collection item serialization. Raises `NotImplementedError` if unset.
- **`scope`** — the sole sanctioned data-access seam. Default: `model_class.for_store(current_store).accessible_by(current_ability, ability_action_for_request)`, or `@parent.send(parent_association)` for nested resources. Override to add controller-specific scoping (e.g. `Store::ProductsController#scope` adds `.available(...)`) — always call `super` first.
- **`find_resource`** — resolves `params[:id]` to a single record within `scope`. Default: `scope.find_by_prefix_id!(params[:id])`. Override for alternate lookup keys (e.g. `Store::ProductsController` falls back to slug lookup with locale fallback).
- **`permitted_params`** — the write-side allowlist, run through `ParamsNormalizer` (prefixed-ID decoding + nested-attributes normalization). Default: infers `Spree::PermittedAttributes.public_send("#{model_class.model_name.element}_attributes")`. New controllers are encouraged to override with an explicit `params.permit(...)` list per CLAUDE.md's "API Controllers" guidance, rather than relying on the global allowlist.
- **`collection_includes`** / **`scope_includes`** — eager-load hints. `collection_includes` feeds `ransack`'s `.includes`; `scope_includes` feeds the base `scope` for associations `ar_lazy_preload` can't handle automatically (e.g. prices, stock items).
- **`collection_distinct?`** / **`apply_collection_sort`** — override to disable `DISTINCT` or inject custom ordering when the default Ransack `s=` sort isn't sufficient (e.g. computed-column sorts).
- **`set_parent`** / **`parent_association`** — nested-resource hooks. `set_parent` loads `@parent` and typically calls `authorize_parent!`; `parent_association` defaults to `controller_name` and is overridden when the association name differs.

Any new Store or Admin API v3 controller is expected to build exclusively on
this contract rather than reaching around it (e.g. querying `model_class`
directly instead of `scope`, or hand-rolling pagination instead of
overriding `collection_includes`/`apply_collection_sort`).

## Assumptions

- The framework is considered "done" as continuously-evolving shared infrastructure — this spec captures its current contract as of the migration date, not a fixed scope that stops changing.
- Store API "read-only by default" is enforced by routing convention (only `index`/`show` routes generated unless a resource opts in), not by a controller-level action lockout — `Store::ResourceController` itself does not forbid `create`/`update`/`destroy` if a route is added.
- Existing controllers using the global `Spree::PermittedAttributes` allowlist (rather than local `params.permit(...)`) remain valid under this framework per the CLAUDE.md 6.0 transition note; this spec does not require migrating them.
- No RSpec changes are required by this reverse-engineered spec itself; `spree/api/spec/controllers/spree/api/v3/resource_controller_spec.rb` and `admin/base_controller_spec.rb` already cover the framework's behavior.
