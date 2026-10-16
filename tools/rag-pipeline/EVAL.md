# Evaluating the ask skills

Compares `/speckit-assist-ask` (retrieval as navigation + reading + code verification) against the baselines, using the onboarding answer-quality rubric (F1–F8).

## Variants

| Variant | What it is | Role |
|---|---|---|
| `speckit-assist-ask0` | Reads specs/constitution directly, cross-references code | Baseline to beat |
| `speckit-assist-ask-rag` | Top-k hybrid RAG over specs only, no reading, no graph | Control (unchanged) |
| `speckit-assist-ask` | Sub-queries + section expansion over the full corpus, then reads and verifies against code | Candidate |

## Ablations

Add one change at a time and re-score, so each change's contribution is visible. If a step adds little, report that.

1. **Skill rules only.** Run the new skill against a specs-only index (`build_index.py --specs-only`), with plain `cli_ask.py "<q>"` (no `--sub`, `--expand`, `--graph-always`).
2. **+ Section expansion.** Add `--expand`.
3. **+ Full corpus.** Rebuild with `build_index.py` (CLAUDE.md, developer docs, plans).
4. **+ Sub-queries.** Add `--sub`.
5. **+ Graph leads.** Add `--graph-always` and graphify lookups. Expect this to matter mainly for where and what-calls questions.

## Question set

Keep these fixed across runs. Write each answer key before reading any answers, and hold out at least half the questions from any tuning.

1. Trace a cart to a shipped order: which class or callback hands off at each stage? (flow)
2. How do I set up and run the project locally, and where are the tests for each layer? (procedural)
3. Why are order `payment_state` and `shipment_state` derived rather than set directly? (why)
4. Where is the default order-routing strategy chosen, and how would I plug in my own? (where + extension)
5. What does `FR-009` require in the payments feature? (bare id → ambiguous → scoped)
6. What changes for Store API clients when Shipment becomes Fulfillment in 6.0? (plans / currency)

## Protocol

- Run 2–3 answers per variant per question. One answer per technique is noise at a gap of about 5 points.
- Strip phrases that identify the technique ("the index", scores, "code graph") before raters see the answers.
- State whether raters can open `specs/` and `.specify/`. This changes F4 and can reorder close results.
- Check F1 claims against a pinned commit, and record that commit with the scores.

## Rebuilding the index

Run from the project root. Milvus must be reachable at `127.0.0.1:19530`.

```bash
tools/rag-pipeline/.venv/bin/python tools/rag-pipeline/build_index.py            # full corpus
tools/rag-pipeline/.venv/bin/python tools/rag-pipeline/build_index.py --specs-only
tools/rag-pipeline/.venv/bin/python tools/rag-pipeline/build_index.py --list     # show the corpus only
```
