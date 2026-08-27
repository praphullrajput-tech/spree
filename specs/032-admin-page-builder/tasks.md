---

description: "Task list template for feature implementation"
---

# Tasks: Admin Page Builder

**Input**: Design documents from `specs/032-admin-page-builder/`

**Prerequisites**: plan.md, spec.md

**Tests**: Not applicable — no tests exist for this feature and none are being added (see plan.md → Constitution Check, Principle IV).

**Organization**: This is a brownfield reverse-engineering pass, not new development. All tasks below record research/discovery steps already performed, marked complete.

## Phase 1: Discovery

- [x] T001 Read the only known starting file: `spree/admin/app/javascript/spree/admin/controllers/page_builder_controller.js` — confirmed a Stimulus controller (316 lines) providing iframe live-preview, overlay highlighting, toolbar-driven reorder, responsive breakpoint toggle, and mobile sidebar toggle.
- [x] T002 [P] Searched `spree/core` and the wider monorepo for `Spree::Page`, `Spree::PageSection`, `Spree::PageBlock`, `Spree::Theme` model files — none found. Only two `defined?(Spree::Page)` / `defined?(Spree::PageLink)` guards remain, in `spree/core/app/helpers/spree/base_helper.rb`.
- [x] T003 [P] Searched `spree/admin/app/controllers` and `spree/admin/config/routes.rb` for `pages`, `page_sections`, `page_blocks`, `page_previews` controllers/routes — none found. The only adjacent route is `resources :links, controller: 'page_links'` nested under store settings; no corresponding `page_links_controller.rb` file exists either.
- [x] T004 [P] Read `docs/developer/storefront/rails/pages.mdx` (and cross-referenced `sections.mdx`, `blocks.mdx`) to understand the documented design: built-in Pages (`Spree::Pages::Homepage`, `ProductDetails`, `Taxon`, `SearchResults`, `ShopAll`, `PostList`, `Post`, `Password`, `Custom`), each composed of ordered Sections, each composed of Blocks, all customizable via the page builder UI this Stimulus controller drives.
- [x] T005 [P] Confirmed via `graphify query` that the knowledge graph's only page-builder-adjacent nodes are the JS controller itself, the docs `.mdx` files (treated as doc nodes, not code), and the unrelated `query_builder_controller.js` (a Ransack query-builder UI for admin filters — a different feature, not part of page building).
- [x] T006 Confirmed the CSS partial `spree/admin/app/assets/tailwind/spree/admin/views/_page-builder.css` (217 lines) exists and is imported as part of the legacy admin's Tailwind build, providing the overlay/toolbar visual styling the JS controller depends on.
- [x] T007 Confirmed `application.js` imports `PageBuilderController` (`spree/admin/app/javascript/spree/admin/application.js:69`), so the controller is registered and active in the legacy admin even though its backing routes could not be located.

**Checkpoint**: Discovery complete — no backend/API/model code found; only frontend Stimulus + CSS survive.

## Phase 2: Documentation

- [x] T008 Wrote `specs/032-admin-page-builder/spec.md` per `spec-template.md`, with the frozen-module notice immediately under `**Status**: migrated`, honest Module Impact table (only `spree/admin` touched, `spree/core` partial via two guards, everything else "No"), and a "Migration Notes" section scoping this to the legacy Rails storefront theme system only (no Next.js storefront equivalent found).
- [x] T009 Wrote `specs/032-admin-page-builder/plan.md` per `plan-template.md`, with real file paths, a Constitution Check that passes (no new work, no boundary violations), and an explicit note that reviving this module would itself violate Principle I.
- [x] T010 Wrote this tasks.md recording the discovery/documentation work as completed tasks (no implementation tasks — nothing is being built or changed).

**Checkpoint**: All three spec-kit artifacts exist for feature 032 and accurately reflect what was found in the repository.

## Notes

- No Setup/Foundational/User-Story-implementation phases apply — this is a documentation-only brownfield migration for an already-frozen, largely-orphaned frontend controller.
- If a future team decides to rebuild visual page building for Spree 6.0, per the constitution (Principle I) that work belongs in `packages/dashboard` against a new `spree/api` surface — it would be a **new** spec-kit feature, not a continuation of this one.
