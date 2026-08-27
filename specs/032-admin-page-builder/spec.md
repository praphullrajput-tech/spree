# Feature Specification: Admin Page Builder

**Feature Branch**: `032-admin-page-builder`

**Created**: 2026-08-25

**Status**: migrated

**Note**: This module is frozen — documented for historical/migration reference only. Per the project constitution, no new features should be added here; new admin work belongs in `packages/dashboard`.

**Input**: Reverse-engineered from existing implementation (brownfield migration). A Stimulus controller (`page_builder_controller.js`) in the legacy Rails admin that drives a live iframe preview + click-to-edit overlay UI for the storefront's theme page/section/block system. The backing domain models and admin CRUD controllers referenced by the docs and by this controller's own endpoints (`Spree::Page`, page/section/block admin controllers, `/admin/page_previews/...`) are **not present in this monorepo checkout** — only a `defined?(Spree::Page)` guard in `spree/core` and a single nested `page_links` route remain.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin visually edits a storefront theme page (Priority: P1)

A store admin opens a theme page in the legacy Rails admin. The page renders inside an iframe; hovering over a rendered section or block highlights it with an overlay, and clicking the overlay opens an editor for that section/block in a side panel, without a full page reload.

**Why this priority**: This is the entire interaction the controller exists to support — everything else (responsive breakpoint toggle, add-section flow, reorder buttons) is secondary to the core "click what you see to edit it" loop.

**Independent Test**: As documented in `docs/developer/storefront/rails/pages.mdx` — cannot currently be exercised end-to-end in this repo, because the admin routes/controllers/views that would serve the iframe content (`/admin/page_previews/...`) and the `Spree::Page`/section/block models the JS expects to find `[data-editor-id]` elements for are not present. See Gaps below.

**Acceptance Scenarios**:

1. **Given** the page builder iframe has loaded a preview containing elements with `data-editor-id`, **When** the admin hovers a section, **Then** an absolutely-positioned overlay is drawn over it matching its bounding box (`initializeOverlay`, `initializeOverlays`).
2. **Given** an overlay is visible, **When** the admin clicks it, **Then** the sidebar iframe (`#page_sidebar`) navigates to the element's `data-editor-link` and the sections sidebar panel opens (`showSectionsSidebar`).
3. **Given** an overlay has a toolbar with move-up/move-down controls, **When** the admin clicks one, **Then** the corresponding hidden button (`editor-toolbar-higher-<id>` / `editor-toolbar-lower-<id>`) is clicked and the section/block's DOM position swaps with its sibling (`toolbarHigher`/`toolbarLower` handlers).
4. **Given** the admin toggles the desktop/mobile breakpoint buttons, **When** a breakpoint is selected, **Then** the preview container class and `sessionStorage['breakpoint']` are updated (`setResponsiveBreakpoint`).

---

### Edge Cases

- What happens when the iframe reloads via Turbo (`turbo:frame-render`, `turbo:load`)? The controller re-reads the `editor_id` query param from the new URL and re-initializes overlays so the previously-active selection survives navigation inside the iframe.
- How does the system handle a resize of the iframe body? A `ResizeObserver` on `iframeDocument.body` removes and re-creates all overlays so their positions stay in sync with reflowed content.
- What happens when an overlay belongs to a block rather than a section? Blocks carry `data-editor-parent-id`; the overlay is appended to the parent element's parent node instead of the block's own parent, and z-index is bumped (1089 vs 1088 for sections, 1090 for links) so nested overlays stack correctly.
- What happens on narrow viewports? A separate mobile sidebar toggle (`showSidebarMobile`/`hideSidebarMobile`) adds/removes a `mobile_sidebar_open` body class; a `.back` control triggers `clearActiveOverlays` to also close the mobile sidebar.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The admin MUST render a live iframe preview of the current theme page/section/block tree, driven by a `previewUrl` Stimulus value.
- **FR-002**: The admin MUST overlay every element carrying `data-editor-id` inside the iframe with a positioned, clickable highlight box, recomputed on resize and on Turbo navigation within the iframe.
- **FR-003**: Clicking an overlay MUST load that section/block's editor into a separate sidebar iframe (`#page_sidebar`) via its `data-editor-link` and open the sections sidebar.
- **FR-004**: The admin MUST support reordering a section or block one position at a time via toolbar controls, without a full page reload, by delegating to hidden per-element move buttons and re-running the overlay pass.
- **FR-005**: The admin MUST support switching the preview between a desktop and mobile responsive view, persisting the last choice in `sessionStorage`.
- **FR-006**: The admin MUST support an "add section" entry point that opens the sidebar iframe at a `sections/new` URL scoped to the page.
- **FR-007**: The admin MUST support a mobile layout where the sidebar is shown/hidden via a dedicated toggle rather than always being visible alongside the preview.

### Key Entities *(include if feature involves data)*

None present in this codebase. The controller and docs reference the following domain concepts, but no corresponding ActiveRecord models, migrations, or admin controllers exist in this monorepo checkout:

- **Page** (`Spree::Page`, `Spree::Pages::*` — Homepage, ProductDetails, Taxon, SearchResults, ShopAll, PostList, Post, Password, Custom): a themeable storefront page, per the docs. Only a `defined?(Spree::Page)` guard survives, in `spree/core/app/helpers/spree/base_helper.rb`.
- **PageSection** (`Spree::PageSection`, `Spree::PageSections::*`): an ordered content block belonging to a Page. No trace found in this repo beyond documentation.
- **PageBlock** (`Spree::PageBlock`, `Spree::PageBlocks::*`): a nested content unit belonging to a Section. No trace found in this repo beyond documentation.
- **Theme** (`Spree::Theme`): documented as the owner of a store's Pages. No trace found in this repo beyond documentation.
- **PageLink**: the one adjacent concept that *does* exist — `Spree::Admin::PageLinksController`... actually not found either; only the route `resources :links, controller: 'page_links', only: [:create]` nested under store settings exists, plus a `defined?(Spree::PageLink)` guard in `base_helper.rb`. No `page_links_controller.rb` file was found in this checkout.

## Module Impact *(mandatory)*

| Module | Touched? | What changes |
|--------|----------|---------------|
| `spree/admin` (legacy Rails admin) | Yes | `page_builder_controller.js` (Stimulus, imported by `application.js`), `_page-builder.css` — this is the entirety of the surviving implementation |
| `spree/core` (models, services) | Partial | Two `defined?(Spree::Page)` / `defined?(Spree::PageLink)` guards in `base_helper.rb#spree_storefront_resource_url`-style helper; no `Page`/`PageSection`/`PageBlock`/`Theme` models present |
| `spree/api` (Store/Admin API v3) | No | No page/section/block endpoints found |
| `packages/dashboard` (admin SPA) | No | No equivalent found; not planned per docs (docs describe only the legacy Rails admin flow) |
| `packages/dashboard-ui` / `dashboard-core` | No | N/A |
| `packages/sdk` / `packages/admin-sdk` | No | N/A |
| `docs/plans/` | No | Not in the active/pending plans list in `CLAUDE.md`; not an architectural change being made now (reverse-engineering only) |

### API Contract

Not applicable — no `spree/api` surface found for this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The Stimulus controller correctly re-derives overlay positions after any iframe resize or Turbo navigation, with no stale overlays left in the DOM (`removeOverlays` always precedes `initializeOverlays`).
- **SC-002**: Reordering a section/block via the overlay toolbar produces the same DOM position change as clicking the underlying hidden move button directly (parity, not a separate code path).

No further success criteria are defined — the feature has no measurable business outcome documented anywhere in this repo (no specs, no analytics, no docs/plans entry).

## Assumptions

- The `Spree::Page` / `Spree::PageSection` / `Spree::PageBlock` / `Spree::Theme` models, their admin CRUD controllers (`/admin/pages`, `/admin/page_previews/*`), and their views are assumed to have existed at some point (they are documented in detail in `docs/developer/storefront/rails/{pages,sections,blocks,themes}.mdx` with GitHub source links) but are not present in this monorepo checkout at the reverse-engineering date. This spec documents only what remains: the frontend Stimulus controller and its CSS.
- The `defined?(...)` guards in `base_helper.rb` suggest these models are optional/pluggable at runtime (e.g., shipped by a separate gem or extension not vendored into this monorepo), rather than fully deleted — but no such gem was found in the workspace.
- This is a legacy Rails-admin-only feature; the Next.js storefront (see `server/` bootstrap docs) has no equivalent page-builder concept anywhere in this monorepo.

## Migration Notes

- This feature applies **only to the legacy Rails admin + legacy Rails storefront theme system** (`spree/admin`, plus the documented-but-absent `Spree::Page`/`Theme` models that would live in `spree/core`/a storefront gem). It has no bearing on the Next.js storefront, which has no page-builder equivalent anywhere in this monorepo.
- Per the project constitution (Principle I, "Module Boundaries Are Load-Bearing"): `spree/admin` is explicitly called out as "being phased out — do not add new features here." Combined with the missing backing models, this feature should be treated as **frozen and non-extensible** — any future visual page-building capability for Spree 6.0 belongs in `packages/dashboard`, built against a new `spree/api` surface, not as a continuation of this controller.
- Because the backing domain models could not be located in this checkout, the "Key Entities" and "Independent Test" sections above are necessarily incomplete; they describe the *documented* design (per `docs/developer/storefront/rails/*.mdx`) rather than a design this repo's tests could verify. Nothing in `spree/core/spec` or `spree/admin/spec` was found covering `Spree::Page`, sections, or blocks.
