"""Phase 4: cross-encoder reranking.

Mechanism, stated up front because it's the whole reason this can fix what
Milvus's native rankers structurally couldn't (see retrieval.py's
hybrid_search docstring for the Q1/Q4 diagnosis): a cross-encoder does NOT
compare two independently-precomputed embeddings/scores. It takes the query
and ONE candidate passage together as a single joint input
("[CLS] query [SEP] passage [SEP]"), runs that pair through a transformer,
and outputs one relevance score for that specific pair — recomputed fresh
per (query, candidate). It never fuses precomputed lists, so a candidate's
absence from BM25's candidate pool (the exact thing that sank Q1/Q4 under
RRF and WeightedRanker) is irrelevant to its cross-encoder score. The cost
is O(candidates) transformer forward passes per query — why this only ever
reranks a fetched top-~20, never the whole collection.
"""
from __future__ import annotations

from functools import lru_cache

from sentence_transformers import CrossEncoder

# v2-m3 over base: fixed Q3/Q4's cross-feature "right concept, wrong
# feature" failure cleanly (base did not, at any WeightedRanker weight);
# confirmed the earlier "IV. Test-Backed" boilerplate-attraction was a
# base-specific weakness, not corpus-wide contamination (v2-m3 doesn't
# exhibit it). Larger/slower to load (~50s vs near-instant) but validated
# as the better default for this corpus.
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"


@lru_cache(maxsize=4)
def _model(model_name: str) -> CrossEncoder:
    return CrossEncoder(model_name)


def rerank(query_text: str, candidates: list[dict], top_k: int = 5,
           model_name: str = RERANKER_MODEL) -> list[dict]:
    """*candidates*: Milvus hit dicts (each with an 'entity' dict containing
    'raw_text'), as returned by retrieval.py's search functions. Returns the
    top_k re-sorted by cross-encoder score, each tagged with
    'rerank_score_raw' — the untouched cross-encoder output (the original
    'distance' is also left untouched for comparison). Named "_raw"
    deliberately: pipeline.py's item_kind boost sorts by a DIFFERENT,
    computed value ('final_score') and must never be confused with this one
    — see pipeline.py's _finalize_scores docstring for why that distinction
    is load-bearing once a score is used for a confidence decision instead
    of just display order. `model_name` lets pipeline.py A/B a different
    reranker without changing the default."""
    if not candidates:
        return []
    pairs = [(query_text, c["entity"]["raw_text"]) for c in candidates]
    scores = _model(model_name).predict(pairs)
    scored = sorted(zip(candidates, scores), key=lambda cs: cs[1], reverse=True)
    out = []
    for c, s in scored[:top_k]:
        c2 = dict(c)
        c2["rerank_score_raw"] = float(s)
        out.append(c2)
    return out
