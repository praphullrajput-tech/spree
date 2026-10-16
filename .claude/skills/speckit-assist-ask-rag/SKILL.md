---
name: speckit-assist-ask-rag
description: Answer developer questions about features, architecture, and rationale
  by querying the RAG-indexed specs/ knowledge base using hybrid retrieval only (no
  graphify code graph)
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: assist:commands/speckit.assist.ask-rag.md
---

# Ask Codebase Questions (Hybrid RAG only)

Query the project's specification knowledge base to understand how features work, why architectural decisions were made, and where specific logic lives. This command retrieves from an embedded index of the `specs/` directory (both migrated and newly authored artifacts) and `.specify/memory/constitution.md`, built and queried by the RAG pipeline at `tools/rag-pipeline/` — it does not scan those files directly itself. This variant uses hybrid retrieval (dense + keyword, reranked) only; it never consults the graphify knowledge graph.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding. The user will provide a natural language question (e.g., "Why do we use Redis for the auth system?", "How does the payment retry mechanism work?", "Where are the validation rules for user registration?"), or a bare requirement/task id (e.g. "FR-009", "T042").

## Prerequisites

1. Verify a spec-kit project exists by checking for the `.specify/` directory.
2. Verify the existence of `.specify/memory/constitution.md`.
3. Verify the `specs/` directory exists and contains feature subdirectories with `.md` artifacts.
4. Resolve `RAG_PIPELINE_HOME`: the env var if set, else `~/spree/tools/rag-pipeline` (this machine's current install — update this default if you move the pipeline to a standalone checkout). Resolve `RAG_PIPELINE_PYTHON`: `$RAG_PIPELINE_HOME/.venv/bin/python` if that file exists, else `python3` on PATH.

## Outline

1. **Query the index**: run, from the current project's root (so the pipeline's project-root auto-detection resolves to *this* project, not wherever the pipeline itself lives):
   ```bash
   "$RAG_PIPELINE_PYTHON" "$RAG_PIPELINE_HOME/cli_ask.py" "$ARGUMENTS" --mode hybrid --no-graph
   ```
   This prints one JSON object to stdout, tagged by `"type"`:
   - `"search"` — a ranked `results` list, each item carrying `file_path`, `heading_path`, `start_line`/`end_line`, `item_kind`/`item_id` (when the chunk is a tagged FR-XXX/T###/principle/quality-gate/technical-context item, else `null`), `raw_text`, and `final_score`.
   - `"unique"` — the query named exactly one bare id (e.g. "FR-009", "T013", a Constitution-Check numeral); `result` is that one chunk.
   - `"ambiguous"` — the bare id exists in more than one feature (FR-XXX/T### numbering resets per file); `candidates` lists each match's `file_path`/`heading_path`.
   - `"not_found"` — no chunk carries that item_id.

   The response's `code_context` block will read `"trigger": "disabled"` because of `--no-graph` — ignore it entirely.

   If the command exits non-zero (pipeline not indexed for this project yet, or Milvus unreachable — check stderr), **do not fail the request**: fall back to directly reading `specs/*/spec.md`, `specs/*/plan.md`, `specs/*/tasks.md`, and `.specify/memory/constitution.md` yourself, and say plainly in the answer that this ran without the indexed backend.

2. **Branch on `type`**:
   - `"unique"` → answer directly from that one chunk.
   - `"ambiguous"` → ask a single clarifying question naming the candidate features (from `heading_path`/`file_path`), then re-run step 1 with the feature name folded into the query text (e.g. "FR-009 for cart and checkout") so the pipeline's own feature-name filter scopes it — don't try to disambiguate by guessing.
   - `"not_found"` → state that no indexed requirement matches that id, then fall back to a plain-text search across `specs/` for the literal id before concluding it isn't documented at all.
   - `"search"` → use the top 1-3 results (already ranked by `final_score`, reranked and boosted for structured-item precision — do not re-sort or second-guess that ordering) as the primary sources for the answer. A low top `final_score` (rough guide: hybrid+rerank scores are cross-encoder outputs, not cosine similarities — treat anything not clearly topically on-point as a weak match) means the corpus likely doesn't cover this; say so rather than stretching a marginal match into an answer.

3. **Synthesize the answer**: combine the retrieved chunk(s) — and constitution content when the question is a "why" — into a direct answer. Quote or closely paraphrase `raw_text`; don't invent detail beyond what the retrieved chunks support.

4. **Output format**:
    ```markdown
    # Answer: [Brief Summary of Topic]

    [Direct, clear answer to the user's question]

    ## Rationale & Architecture
    - Explain the "why" based on `constitution.md` or `plan.md`.
    - Highlight any specific architectural constraints that influenced this.

    ## Feature Details
    - Summarize the exact behavior defined in the relevant `spec.md`.
    - Mention if this feature was reverse-engineered (`status: migrated`) or originally specified via SDD.

    ## Sources Referenced
    - 📄 `specs/feature-name/spec.md` § Requirements > FR-005, lines 31-48
    - 📄 `.specify/memory/constitution.md` § I. Module Boundaries, lines 10-18
    ```

## Rules

* **Read-only** — this command never modifies any files or generates new artifacts.
* **Retrieval-first** — always ground the answer in what `cli_ask.py` returned (or, on fallback, what's directly in `specs/`/`constitution.md`) over guessing purely from raw source code.
* **Don't re-rank what's already ranked** — the pipeline's `final_score` ordering already accounts for hybrid retrieval, cross-encoder reranking, and a structured-item precision boost calibrated on this corpus; use its top results as given rather than re-judging relevance from `raw_text` alone.
* **Cite your sources** — explicitly mention which files and line ranges (from `file_path`/`start_line`/`end_line`) provided the information. Spec evidence is cited as `file § heading, lines X-Y` (from `heading_path`/`start_line`/`end_line` in `results`).
* **Acknowledge missing context** — if the answer cannot be found via retrieval or the fallback scan, clearly state that the rationale is undocumented before attempting to infer from the code.
* **Respect feature origins** — take note if a spec is marked `status: migrated` (meaning it was reverse-engineered and might contain identified "gaps") versus a natively planned Spec Kit feature.
* **No code graph** — never run graphify or cite graph-derived code locations from this command. If the user wants to know where something lives in code, point them to `/speckit-assist-ask` (graph-enabled) or offer a separate code search, labelled as not from the index.
* **Say when the backend was unavailable** — if step 1 fell back to a direct file scan, mention that in the response instead of presenting it as an indexed-retrieval answer.
