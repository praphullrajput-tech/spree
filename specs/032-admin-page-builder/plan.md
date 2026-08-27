# Implementation Plan: Admin Page Builder

**Branch**: `032-admin-page-builder` | **Date**: 2026-08-25 | **Spec**: `specs/032-admin-page-builder/spec.md`

**Input**: Feature specification from `specs/032-admin-page-builder/spec.md`

**Note**: This module is frozen (legacy `spree/admin`, being phased out). This plan is a reverse-engineered record for migration reference, not a proposal for new work.

## Summary

The only surviving implementation is a single Stimulus controller, `page_builder_controller.js`, plus one CSS partial, in the legacy Rails admin (`spree/admin`). It provides an iframe-based live preview with click-to-edit overlays, drag-free reorder-by-button, a responsive breakpoint toggle, and a mobile sidebar toggle for editing a storefront theme's pages/sections/blocks. The domain models and admin CRUD controllers/routes this JS assumes exist (`Spree::Page`, `Spree::PageSection`, `Spree::PageBlock`, `/admin/page_previews/*`) were not found anywhere in this monorepo checkout — only documentation (`docs/developer/storefront/rails/{pages,sections,blocks,themes}.mdx`) and two `defined?(...)` guards in `spree/core/app/helpers/spree/base_helper.rb` remain. No backend, API, or frontend-SPA work is proposed by this plan; it documents what exists.

## Technical Context

**Language/Version**: JavaScript (Stimulus controller, ESM, bundled by the legacy admin's asset pipeline) + CSS (Tailwind partial). No Ruby controllers/models found to back it.

**Primary Dependencies**: `@hotwired/stimulus` (`Controller` base class), `ResizeObserver` (browser API), Turbo events (`turbo:frame-render`, `turbo:load`), `sessionStorage`.

**Storage**: N/A — no persistence layer found for this feature in this checkout.

**Testing**: No test coverage found. No `spec/` file under `spree/admin` or `spree/core` references `page_builder_controller`, `Spree::Page`, `PageSection`, or `PageBlock`. No Vitest/Playwright coverage either (this predates the `packages/dashboard` SPA and was never ported there).

**Target Platform**: Legacy Rails admin (`spree/admin` engine), server-rendered views + Turbo + Stimulus, running inside the Rails host app described in `CLAUDE.md` → "Development Server".

**Project Type**: Monorepo — single Ruby gem asset (`spree/admin`), JS-only surface.

**Performance Goals**: None documented.

**Constraints**: None documented beyond what's inferable from the code: overlay recompute must stay responsive to iframe resize/navigation (`ResizeObserver` + Turbo event listeners), since stale overlays would silently drift out of alignment with re-rendered content.

**Scale/Scope**: Single file (`page_builder_controller.js`, 316 lines) + one CSS partial (`_page-builder.css`, 217 lines). No other files were found to belong to this feature after searching for `Spree::Page`, `Spree::PageSection`, `Spree::PageBlock`, `Spree::Theme`, admin routes/controllers under `pages`/`sections`/`blocks`/`page_previews`, and page-builder-related view partials.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Module Boundaries**: Touches only `spree/admin` (legacy, explicitly called out in the constitution as "being phased out — do not add new features here"). No boundary crossing occurs because there is effectively nothing left to cross into (no `spree/core` model, no `spree/api` endpoint). PASS (no new work proposed).
- **II. Admin API Is the Only Frontend Data Source**: N/A — this is legacy `spree/admin`, not `packages/dashboard`; the constitution's Admin-API-only rule governs the SPA, not this frozen module.
- **III. Read/Write Field Symmetry**: N/A — no serializer, no API.
- **IV. Test-Backed**: No tests exist and none are being added; this plan is documentation-only (brownfield migration). If this module were ever revived, RSpec (controller specs) would be the applicable framework per `CLAUDE.md`, but reviving it contradicts Principle I.
- **V. Translations and Prefixed IDs**: N/A — no user-visible strings or resource IDs are introduced by this plan; the existing JS has no i18n calls (legacy admin uses `Spree.t`/`I18n.t` elsewhere, but this controller has no translated strings — it manipulates DOM classes and hidden buttons only).
- **VI. `docs/plans/` for Architectural Changes**: N/A — no architectural change is being made; this is a reverse-engineered record of existing (largely absent) functionality, not new work. No `docs/plans/6.0-*` entry references a page-builder rebuild.

No violations. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/032-admin-page-builder/
├── plan.md              # This file
└── spec.md              # Reverse-engineered spec
```

No `research.md`, `data-model.md`, `contracts/`, or `quickstart.md` are produced — there is no data model or API contract to document, and no new research question to resolve (the gap itself — missing backing models — is the finding, recorded directly in spec.md's Assumptions/Migration Notes).

### Source Code (repository root)

```text
# spree/admin — legacy Rails admin (the entire surviving surface for this feature)
spree/admin/
├── app/javascript/spree/admin/controllers/page_builder_controller.js   # Stimulus controller (existing, unchanged)
├── app/javascript/spree/admin/application.js                          # imports PageBuilderController (existing, unchanged)
└── app/assets/tailwind/spree/admin/views/_page-builder.css             # overlay/toolbar styling (existing, unchanged)

# spree/core — the only remaining trace of the domain model
spree/core/
└── app/helpers/spree/base_helper.rb   # `defined?(Spree::Page)` / `defined?(Spree::PageLink)` guards (existing, unchanged)
```

**Structure Decision**: Reverse-engineering only, touching `specs/032-admin-page-builder/` — no source files are added or modified. The Module Impact table in spec.md marks `spree/admin` as "Touched? Yes" only in the sense that it is the location of the existing code being documented, and `spree/core` as "Partial" for the two `defined?` guards; all other modules are untouched and this plan proposes no changes to any of them.

## Complexity Tracking

Not applicable — no constitution violations.
