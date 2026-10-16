"""Phase 3: dense, sparse, and native-hybrid query functions.

All three apply `is_leaf == true` unconditionally — see the zero-vector
investigation from Phase 2/3 review for why this is load-bearing rather than
optional: a non-leaf row's placeholder dense vector scores a clean 0.0 under
COSINE (Milvus never errors or returns NaN for it), and its `raw_text` is
real prose that BM25 can and does keyword-match competitively (empirically
confirmed: a multi-field query put non-leaf "Technical Context" parents at
ranks #2/#6/#9/#10 in an unfiltered result set). The filter is applied on
every AnnSearchRequest individually, not just once at the top — hybrid
search fuses two independently-filtered candidate sets, not one filtered
and one not.
"""
from __future__ import annotations

import re
from functools import lru_cache

from pymilvus import AnnSearchRequest, RRFRanker, WeightedRanker
from sentence_transformers import SentenceTransformer

import config
from milvus_schema import COLLECTION_NAME, get_client

SPECS_DIR = config.specs_dir()

LEAF_FILTER = "is_leaf == true"
MODEL_NAME = "BAAI/bge-base-en-v1.5"
# BGE's asymmetric-retrieval convention: the query gets an instruction
# prefix, the indexed passage/document does not (embed_and_insert.py never
# adds this — only here, at query time).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

CITATION_FIELDS = ["chunk_id", "file_path", "heading_path", "start_line", "end_line",
                   "chunk_type", "parent_chunk_id", "item_kind", "item_id", "raw_text"]

# Bare item-id queries (FR-009, T013, a Constitution-Check principle numeral)
# aren't a ranking problem — every mode "worked" on Q2's "FR-009" and still
# answered a question the corpus can't disambiguate: FR-XXX/T### numbering
# resets PER FILE, so "FR-009" alone names 43 unrelated requirements, one per
# feature. Vector/keyword search can't fix that (it's not a relevance
# problem, it's a missing key), so these route to a scalar `item_id` filter
# instead — cheap, exact, and it surfaces the ambiguity explicitly rather
# than silently picking a plausible-looking but arbitrary winner.
_ROMAN_PRINCIPLES = {"I", "II", "III", "IV", "V", "VI"}  # this corpus's Constitution Check range
_BARE_ID_RE = re.compile(r"^(FR-\d+|T\d+|[IVX]{1,4})$", re.IGNORECASE)


def detect_bare_id(query_text: str) -> str | None:
    """The normalized item_id a query names, or None if it isn't a bare-id query."""
    m = _BARE_ID_RE.match(query_text.strip())
    if not m:
        return None
    token = m.group(1).upper()
    if token.startswith("FR-") or (token.startswith("T") and token[1:].isdigit()):
        return token
    if token in _ROMAN_PRINCIPLES:
        return token
    return None  # e.g. "IIII" matches the regex shape but isn't a real numeral


def lookup_by_item_id(item_id: str) -> dict:
    """Scalar lookup, not a search. Returns one of:
      {"type": "unique", "result": <row>}
      {"type": "ambiguous", "item_id": ..., "candidates": [{"file_path", "heading_path", "chunk_id"}, ...]}
      {"type": "not_found", "item_id": ...}
    """
    client = get_client()
    rows = client.query(
        collection_name=COLLECTION_NAME,
        filter=f'item_id == "{item_id}"',
        output_fields=CITATION_FIELDS,
    )
    if not rows:
        return {"type": "not_found", "item_id": item_id}
    if len(rows) == 1:
        return {"type": "unique", "result": rows[0]}
    return {
        "type": "ambiguous",
        "item_id": item_id,
        "candidates": [
            {"file_path": r["file_path"], "heading_path": r["heading_path"], "chunk_id": r["chunk_id"]}
            for r in rows
        ],
    }


def lookup_by_item_id_in_file(item_id: str, file_path_substring: str) -> dict:
    """Disambiguated follow-up: same item_id, narrowed to a specific feature
    (e.g. after `lookup_by_item_id` returns "ambiguous" and the caller/user
    picks one). Substring match on file_path, not exact, so "cart-and-checkout"
    or "001-cart" both work without requiring the full path."""
    client = get_client()
    rows = client.query(
        collection_name=COLLECTION_NAME,
        filter=f'item_id == "{item_id}" and file_path like "%{file_path_substring}%"',
        output_fields=CITATION_FIELDS,
    )
    if not rows:
        return {"type": "not_found", "item_id": item_id}
    if len(rows) == 1:
        return {"type": "unique", "result": rows[0]}
    return {"type": "ambiguous", "item_id": item_id,
            "candidates": [{"file_path": r["file_path"], "heading_path": r["heading_path"],
                             "chunk_id": r["chunk_id"]} for r in rows]}


# Feature-name detection: the Q3/Q4 reranker failures were "right concept,
# wrong feature" — a topically-rich passage from an unrelated feature
# outscored a terse but correctly-scoped one, because a cross-encoder scores
# query-vs-passage similarity and has no notion of "which feature this
# query names." That's exactly what a literal name match can enforce
# deterministically instead of hoping a bigger model happens to weight it
# correctly. Built from the actual specs/ folder names, not a hardcoded
# list, so it stays correct as features are added/renamed.
def _load_feature_registry() -> list[dict]:
    registry = []
    if not SPECS_DIR.is_dir():
        return registry
    for d in sorted(SPECS_DIR.iterdir()):
        if not d.is_dir():
            continue
        phrase = re.sub(r"^\d+-", "", d.name).replace("-", " ")
        registry.append({"dir": d.name, "phrase": phrase, "prefix": f"specs/{d.name}/"})
    return registry


FEATURE_REGISTRY = _load_feature_registry()


def detect_feature(query_text: str) -> tuple[str | None, str | None]:
    """(file_path prefix, matched phrase) if the query names EXACTLY ONE known
    feature by its folder-derived phrase (word-boundary match, e.g. "payments"
    or "cart and checkout"), else (None, None) — including when it names
    zero or more-than-one feature, since a wrong guess is worse than no
    filter at all."""
    q = query_text.lower()
    matches = [f for f in FEATURE_REGISTRY if re.search(rf"\b{re.escape(f['phrase'])}\b", q)]
    if len(matches) == 1:
        return matches[0]["prefix"], matches[0]["phrase"]
    return None, None


# Third instance of the same underlying pattern in this corpus, at a third
# different scoring mechanism: BM25 favored non-leaf PARENT chunks over
# leaves (Phase 2, fixed with the is_leaf filter); RRF/WeightedRanker fusion
# favored a "generalist" present in both candidate pools over a "specialist"
# present in only one (Phase 3, no native-ranker fix exists, needed a
# cross-encoder); and now a cross-encoder itself favors broad NARRATIVE
# section chunks (no item_kind — Summary, User Story, Success Criteria) over
# precise structured/tagged chunks (item_kind set — a functional_requirement,
# task, constitution_check_principle, technical_context_field, quality_gate)
# for specific factual questions, confirmed empirically: TWO independently-
# trained cross-encoders (bge-reranker-base AND bge-reranker-v2-m3) both put
# Q1's untagged "User Story 1" narrative at #1 and its functional_requirement
# target at #6 (rerank_score 0.2391 vs the winner's 0.8389 — roughly a 3.5x
# gap). The recurring shape: broader/narrative chunks keep winning over
# precise/structured ones, across BM25 term-frequency, rank-based/linear
# fusion, AND now cross-encoder joint scoring — three unrelated mechanisms,
# same failure shape. Each needed its own explicit protection for structured
# content, because none of these scoring mechanisms carries a notion of
# "this chunk is a precise, tagged fact" on its own.
#
# This only applies to specific factual questions ("does X apply to Y",
# "how does X handle Y") — a genuinely broad query ("tell me about the
# checkout flow") should still let a narrative chunk win; boosting item_kind
# unconditionally would break that case for no reason.
_SPECIFIC_QUESTION_RE = re.compile(
    r"^(does|is|are|can|will|should|must|how\s+(does|do|is|are)|what\s+\w+(\s+\w+){0,3}\s+(does|do))\b",
    re.IGNORECASE,
)


def looks_like_specific_question(query_text: str) -> bool:
    """True for a yes/no or 'how does X handle Y' / 'what Y does X use'
    question, where a structured/tagged chunk is more likely the precise
    answer than a broad narrative section. False for 'what is X' / 'tell me
    about X' / 'describe X' broad queries, where narrative winning is
    correct behavior, not a defect to boost away."""
    return bool(_SPECIFIC_QUESTION_RE.match(query_text.strip()))


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed_query(query_text: str) -> list[float]:
    return _model().encode(QUERY_PREFIX + query_text, normalize_embeddings=True).tolist()


def _combined_filter(extra_filter: str | None) -> str:
    return LEAF_FILTER if not extra_filter else f"({LEAF_FILTER}) and ({extra_filter})"


def dense_search(query_text: str, limit: int = 10, extra_filter: str | None = None) -> list[dict]:
    """Semantic search over the dense (bge-base) vector field."""
    client = get_client()
    results = client.search(
        collection_name=COLLECTION_NAME,
        data=[embed_query(query_text)],
        anns_field="dense_vector",
        filter=_combined_filter(extra_filter),  # is_leaf is load-bearing; extra_filter (e.g. feature scope) is additive
        limit=limit,
        output_fields=CITATION_FIELDS,
    )
    return results[0]


def sparse_search(query_text: str, limit: int = 10, extra_filter: str | None = None) -> list[dict]:
    """BM25 keyword search over the native sparse vector field.

    Milvus derives the query-side sparse vector from `query_text` itself
    (same analyzer as `raw_text`'s BM25 function) — no embedding call needed.
    """
    client = get_client()
    results = client.search(
        collection_name=COLLECTION_NAME,
        data=[query_text],
        anns_field="sparse_vector",
        filter=_combined_filter(extra_filter),
        limit=limit,
        output_fields=CITATION_FIELDS,
    )
    return results[0]


def hybrid_search(query_text: str, limit: int = 10, fetch_k: int = 20, ranker=None,
                   extra_filter: str | None = None) -> list[dict]:
    """Dense + sparse in parallel, fused with a Milvus native ranker.

    `fetch_k` is how many candidates EACH side contributes to the fusion
    (not the final result count). `ranker` defaults to RRFRanker().

    WeightedRanker was tested as a fix for RRF's Q1/Q4 failures (a confident
    dense win getting displaced by a same-weighted mediocre keyword list)
    and does NOT fix it, at any weight short of (1.0, 0.0) — i.e. dropping
    the sparse side entirely, which isn't hybrid search anymore. Root cause,
    confirmed by inspecting both sides' raw fetch_k=20 candidate pools: the
    correct chunk was ABSENT from the sparse pool entirely for both queries,
    while the wrong chunk that won was present in both pools. A missing side
    contributes exactly 0 to a weighted sum, so any "generalist" chunk that
    appears in both lists gets a bonus a "specialist" present in only the
    dense list can never match, however large its dense-only margin is —
    this held even at WeightedRanker(0.95, 0.05). Milvus's native rankers
    (rank-based RRF or linear WeightedRanker) can't fix this class of
    failure; it needs either per-query routing (dense-only for natural-
    language questions where BM25's own top hits are already off-topic) or
    a cross-encoder reranker (Phase 4) that scores query-vs-passage directly
    instead of combining two independently-computed candidate lists.
    """
    client = get_client()
    combined = _combined_filter(extra_filter)
    dense_req = AnnSearchRequest(
        data=[embed_query(query_text)], anns_field="dense_vector",
        param={"metric_type": "COSINE"}, limit=fetch_k, filter=combined,
    )
    sparse_req = AnnSearchRequest(
        data=[query_text], anns_field="sparse_vector",
        param={"metric_type": "BM25"}, limit=fetch_k, filter=combined,
    )
    results = client.hybrid_search(
        collection_name=COLLECTION_NAME,
        reqs=[dense_req, sparse_req],
        ranker=ranker if ranker is not None else RRFRanker(),
        limit=limit,
        output_fields=CITATION_FIELDS,
    )
    return results[0]


MODES = {"dense": dense_search, "keyword": sparse_search, "hybrid": hybrid_search}


def retrieve(query_text: str, mode: str = "hybrid", limit: int = 10,
             extra_filter: str | None = None) -> list[dict]:
    """Vector/keyword/hybrid search only. `mode`: "dense" | "keyword" | "hybrid".
    Does NOT do bare-id or feature-name routing — call smart_retrieve() for
    that; this stays a pure search dispatcher so its return shape (always a
    ranked hit list) never changes based on query content."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {list(MODES)}, got {mode!r}")
    return MODES[mode](query_text, limit, extra_filter=extra_filter)


def smart_retrieve(query_text: str, mode: str = "hybrid", limit: int = 10) -> dict:
    """The actual Phase 4/5 entry point. Two pre-search checks, cheapest/most
    certain first:
      1. Bare item-id (FR-009, T013, a principle numeral) -> scalar lookup,
         no search at all (see detect_bare_id).
      2. A single named feature (e.g. "the payments feature") -> HARD FILTER
         restricting search to that feature's file_path prefix, applied
         before ranking even happens (see detect_feature). This is the fix
         for the reranker's "right concept, wrong feature" failure mode on
         Q3/Q4 — deterministic name matching, not hoping a bigger model
         weights entity mentions correctly.
    Always returns a dict tagged by "type":
      {"type": "search", "mode": ..., "results": [...], "feature_filter": {...} | None}
      {"type": "unique", "result": {...}}
      {"type": "ambiguous", "item_id": ..., "candidates": [...]}
      {"type": "not_found", "item_id": ...}
    """
    item_id = detect_bare_id(query_text)
    if item_id is not None:
        return lookup_by_item_id(item_id)

    prefix, phrase = detect_feature(query_text)
    extra_filter = f'file_path like "{prefix}%"' if prefix else None
    results = retrieve(query_text, mode, limit, extra_filter=extra_filter)
    return {
        "type": "search", "mode": mode, "results": results,
        "feature_filter": {"phrase": phrase, "prefix": prefix} if prefix else None,
    }
