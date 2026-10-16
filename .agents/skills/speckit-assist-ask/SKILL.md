---
name: speckit-assist-ask
description: Answer developer questions about features, architecture, rationale, setup,
  and where logic lives — using the RAG index (specs, constitution, CLAUDE.md, developer
  docs, plans) and the code graph to find sources fast, then reading and verifying them
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: assist:commands/speckit.assist.ask.md
---

# Ask Codebase Questions

Answer a developer's question about this codebase the way a senior engineer would: complete, correct, and checkable. The RAG index and the code graph are **navigation aids** — they tell you where to look. The evidence is what you then read: spec sections, docs, and source files. Never answer from retrieved snippets alone.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding. It is a natural-language question ("How does a cart become a shipped order?", "Why are order states derived?", "How do I run the project locally?") or a bare requirement/task id ("FR-009", "T042").

## Prerequisites

1. Verify `.specify/`, `.specify/memory/constitution.md`, and `specs/` exist.
2. Resolve `RAG_PIPELINE_HOME`: the env var if set, else `~/spree/tools/rag-pipeline`. Resolve `RAG_PIPELINE_PYTHON`: `$RAG_PIPELINE_HOME/.venv/bin/python` if it exists, else `python3`.
3. Resolve `GRAPHIFY_PYTHON`: the contents of `graphify-out/.graphify_python` if present (graphify then runs as `"$GRAPHIFY_PYTHON" -m graphify ...`), else `graphify` on PATH, else none.

## Outline

### 1. Plan the answer before searching

- Classify the question: **how** (behaviour/flow), **why** (rationale), **where** (code location), **procedural** (setup, commands, workflow), or a bare id.
- Write a private **coverage checklist**: the 3–12 distinct things a complete answer must contain. For a flow question that is every stage and every handoff between them; for a procedural question it is prerequisites, steps, verification, and the gotchas (destructive commands, ports, credentials, things that are missing or untested); for a why question it is the decision, the constraint that forced it, and the trade-off.
- Turn the checklist into 2–6 short, specific **sub-queries**, each naming one concept in the project's vocabulary (e.g. "tax calculation during checkout", "stock reservation released on completion", "shipment pending to ready transition").

### 2. Retrieve candidates (one call)

Run from the project root:

```bash
"$RAG_PIPELINE_PYTHON" "$RAG_PIPELINE_HOME/cli_ask.py" "$ARGUMENTS" \
  --sub "<sub-query 1>" --sub "<sub-query 2>" ... \
  --top-k 8 --expand --graph-always
```

Output (JSON):
- `results` — candidate chunks across all queries, with `file_path`, `heading_path`, line range, `raw_text`, `matched_queries`, and `section` (the enclosing section's text; `truncated: true` means only a window around the hit was returned, the full span is in `section_lines`).
- `coverage` — per query, how many hits and the top score. A sub-query with no hits or a weak top score marks a checklist item the index probably doesn't cover.
- `files` — hits grouped by file, best first.
- `code_context` — code symbols named in the retrieved chunks, resolved through the code graph (`seeds`) plus graph neighbours. These are **leads to open**, not facts.
- For a bare id: `type` is `unique` (answer from it), `ambiguous` (ask one question naming the candidate features, then re-run with the feature name in the query), or `not_found` (grep `specs/` for the literal id before concluding it's undocumented).

If the command exits non-zero (index or Milvus unavailable), skip to step 3 and do the reading yourself: scan `specs/*/spec.md`, `plan.md`, `tasks.md`, the constitution, `CLAUDE.md`, `docs/developer/`, and `docs/plans/` directly.

### 3. Read the sources — this is where the answer comes from

- **Judge relevance yourself.** The ranking is a starting point. Drop hits that are off-topic, and don't let a high-ranked tangent crowd out the question.
- **Read whole sections, not snippets.** Use `section.text`; when it is truncated, or when one feature's spec/plan dominates `files`, Read the file (the section's line range, or the whole spec/plan for the 1–2 most relevant features).
- **Fill the gaps.** For every checklist item `coverage` left weak or empty, search directly: Grep across `specs/`, `docs/`, `CLAUDE.md`, and source; re-run `cli_ask.py` with a re-worded sub-query; or read the obvious file (`package.json`, a directory listing). Never stop at "the corpus doesn't cover this" while the repo can still answer it.

### 4. Verify against the code

Specs here are partly reverse-engineered (`status: migrated`) and can lag the code. Every claim about behaviour, a class, a method, a callback, an endpoint, a path, or a command must be checked against the source before it goes in the answer.

- Locate code with, in order: `code_context.seeds` (each has `source_file:line`), `"$GRAPHIFY_PYTHON" -m graphify explain "<Symbol>"` / `query "<question>" --budget 1500` (on an ambiguity error, retry with the `<path>::Symbol` form it prints), and Grep.
- **Open the file and read the relevant lines.** Cite `file:line` only for lines you actually read.
- Graph call edges are partial and name-based. Use them to find candidates, never as proof that something does or doesn't call something.
- When spec and code disagree, the code describes what ships today. Say so, and cite both.
- Prefer pointers into the public source tree (`spree/`, `packages/`, `docs/`, `CLAUDE.md`, `package.json`) over pointers into `specs/` or `.specify/`, since a new joiner can always open the former.

### 5. Check completeness

Go back to the checklist. Every item must be either answered (with a source) or explicitly marked as not documented and not found in code. Add anything step 3 or 4 showed matters that the checklist missed (a gotcha, an extension seam, a 6.0 change in flight from `docs/plans/`).

### 6. Write the answer

Lead with the direct answer. Shape the body to the question:

- **Flow / how** — a stage-by-stage table or numbered sequence: stage → what happens → the class/method/callback that hands off to the next stage (`file:line`).
- **Procedural** — copy-pasteable commands in order, with ports, credentials, and verification steps; the gotchas called out before the step they bite on.
- **Why** — the decision, the constraint or principle that drove it, and the trade-off.
- **Where** — the locations, each with a one-line role.

Then:

```markdown
## Rationale & Architecture
- The "why" behind the answer, from the constitution, plan.md, CLAUDE.md, or docs/plans/.
- What is shipped today vs. planned for 6.0, where relevant.

## Gaps & Caveats
- Anything undocumented, inferred from code rather than a spec, or where spec and code disagree.

## Sources
- 🔧 `spree/core/app/models/spree/shipment.rb:120` — determine_state (code, read)
- 📘 `CLAUDE.md` § Testing
- 📄 `specs/003-payments/spec.md` § Functional Requirements, lines 88-101
```

## Rules

* **Read-only** — never modify files or generate artifacts.
* **Retrieval finds, reading proves** — no claim rests on a retrieved snippet or a graph edge alone. Read the section or the source it points to.
* **Complete over minimal** — answer every part of the question; a short answer that skips half the flow is wrong for a new joiner.
* **Cite what you read** — `file:line` for code, `file § heading` for docs/specs. Never cite a line you didn't open.
* **Label provenance by source, not by tool** — say "from spec 003", "from CLAUDE.md", "inferred from code", or "undocumented". Don't narrate retrieval: no scores, no "the index returned", no "the code graph", no "reranked".
* **Respect feature origins** — note when a spec is `status: migrated` (reverse-engineered, may have gaps) versus natively specified.
* **Acknowledge missing context** — if the rationale isn't written down anywhere, say it's undocumented before inferring it from code.
