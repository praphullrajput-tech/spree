"""Phase 4: the retrieve -> (optional) rerank -> (optional) item_kind-boost
pipeline, each step toggled per call.

Composes retrieval.py (Milvus search + bare-id/feature routing) with
reranker.py (cross-encoder). Kept as its own module so retrieval.py stays a
pure Milvus layer and reranker.py stays a pure cross-encoder layer — this is
the only file that knows about both, plus the item_kind boost, which is a
cross-cutting adjustment over whichever score (raw distance or
rerank_score_raw) the prior step produced.
"""
from __future__ import annotations

from reranker import RERANKER_MODEL, rerank as _rerank
from retrieval import looks_like_specific_question, smart_retrieve

# Calibrated against Q1: FR-005 sat at rerank_score_raw 0.2391 vs the
# untagged winner's 0.8389 (bge-reranker-v2-m3) — roughly a 3.5x gap. 4.0
# clears that with margin without being so large it becomes a de facto
# hard filter.
ITEM_KIND_BOOST = 4.0


def _finalize_scores(query_text: str, scored: list[dict], score_key: str,
                      item_kind_boost: bool, boost_factor: float) -> tuple[list[dict], bool]:
    """Attaches 'final_score' to every result — the actual value used to
    sort, always. This is the field that determines rank; NEVER read
    'rerank_score_raw' or 'distance' for that purpose (they're the honest
    pre-boost inputs, kept for diagnostics/display, but boosting sorts by a
    different, computed value and previously never wrote that value back
    anywhere — score and displayed order could silently disagree). Even
    when boosting doesn't fire (broad query, or item_kind_boost=False),
    'final_score' is still attached, equal to the raw score, so the field
    is always safe to read for a confidence decision without checking which
    path produced it first.
    """
    apply_boost = item_kind_boost and looks_like_specific_question(query_text)
    out = []
    for h in scored:
        h = dict(h)
        bonus = boost_factor if apply_boost and (h["entity"].get("item_kind") or "") else 1.0
        h["final_score"] = h[score_key] * bonus
        out.append(h)
    out.sort(key=lambda h: h["final_score"], reverse=True)
    return out, apply_boost


def answer_candidates(query_text: str, mode: str = "hybrid", fetch_k: int = 20,
                       top_k: int = 5, rerank: bool = True,
                       reranker_model: str = RERANKER_MODEL,
                       item_kind_boost: bool = True, boost_factor: float = ITEM_KIND_BOOST) -> dict:
    """The Phase 5 entry point. `rerank` is the A/B toggle for the cross-
    encoder step; `item_kind_boost` is the A/B toggle for the structured-vs-
    narrative fix (see retrieval.py's docstring on looks_like_specific_question
    for why this only fires on specific factual questions, never on broad
    "tell me about X" queries).

    Bare-id and feature-name routing happen inside smart_retrieve() before
    this even runs — reranking/boosting a scalar lookup makes no sense.

    Every result in the returned "results" list carries 'final_score' — see
    _finalize_scores for why that's the ONLY field Phase 5 should read for
    a confidence decision.
    """
    routed = smart_retrieve(query_text, mode=mode, limit=fetch_k)
    if routed["type"] != "search":
        return routed

    candidates = routed["results"]
    if rerank:
        scored = _rerank(query_text, candidates, top_k=fetch_k, model_name=reranker_model)
        score_key = "rerank_score_raw"
    else:
        scored = candidates
        score_key = "distance"

    scored, boost_applied = _finalize_scores(query_text, scored, score_key, item_kind_boost, boost_factor)

    return {
        "type": "search", "mode": mode, "reranked": rerank,
        "reranker_model": reranker_model if rerank else None,
        "item_kind_boost_applied": boost_applied,
        "feature_filter": routed.get("feature_filter"),
        "results": scored[:top_k],
    }
