#!/usr/bin/env python3
"""CLI entrypoint for the /speckit.assist.ask command (and anything else
that wants a one-shot query against the current project's RAG collection).
Wraps pipeline.answer_candidates() — which itself wraps
retrieval.smart_retrieve() for bare-id/feature-name routing plus the
rerank + item_kind-boost steps — and prints one JSON object to stdout.
This script only does retrieval; the calling command does prose synthesis.

Usage:
    python3 cli_ask.py "<question>" [--mode hybrid|dense|keyword]
                        [--top-k 5] [--fetch-k 20]
                        [--no-rerank] [--no-boost]
                        [--no-graph] [--graph-always] [--graph-hops 1|2] [--graph-max-nodes 12]
                        [--sub "<sub-question>" ...] [--expand] [--expand-max-chars 6000]
                        [--project-root PATH]

--sub adds sub-questions that are retrieved independently (one process, so
models load once) and merged rank-by-rank with the main question's results,
so a multi-part question doesn't collapse onto whichever part dominates a
single embedding. "coverage" reports each query's top score so the caller
can tell which parts the corpus answers and which it doesn't.

--expand attaches each hit's enclosing section ("section"), so the caller
gets the requirement block or doc section around a matched line instead of
the line alone. "files" groups hits by file for follow-up reading.

The target project defaults per config.py's resolution order (explicit
--project-root, then RAG_PROJECT_ROOT env var, then CWD) — invoke this
with CWD set to the project being asked about, which is what happens
naturally when a command's Bash tool call runs inside that project.

Exits 1 with a one-line message on stderr if the target project's
collection doesn't exist yet (chunk_docs.py/embed_and_insert.py haven't
been run for it) or Milvus isn't reachable — the caller should treat that
as "knowledge base not available" and fall back accordingly, not crash.

Spec chunks are in "results"; code-side context from the project's graphify
knowledge graph is a separate "code_context" block that never alters,
reorders or adds to "results". The graph step runs only when the query is a
where / what-calls / what-depends question; "code_context.trigger" records
which fired (or why it was skipped). A missing graph yields {"available": false, "note": ...}.
"""
from __future__ import annotations

import argparse
import json
import sys

import config
import graph_context
from milvus_schema import COLLECTION_NAME, MILVUS_URI, get_client
from pipeline import answer_candidates


def _collection_ready(project_root) -> tuple[bool, str]:
    name = config.collection_name(project_root)
    try:
        client = get_client()
        exists = client.has_collection(name)
    except Exception as e:
        return False, f"Cannot reach Milvus at {MILVUS_URI}: {e}"
    if not exists:
        return False, (
            f"Collection '{name}' doesn't exist for project "
            f"'{config.project_slug(project_root)}' — run chunk_docs.py "
            f"and embed_and_insert.py for this project first."
        )
    return True, ""


def _flatten_search_results(results: list[dict]) -> list[dict]:
    """Milvus hit dicts nest citation fields under 'entity'; flatten for a
    simpler, stable JSON shape for callers to consume."""
    out = []
    for h in results:
        e = h["entity"]
        out.append({
            "final_score": h.get("final_score"),
            "chunk_id": e["chunk_id"],
            "file_path": e["file_path"],
            "heading_path": e["heading_path"],
            "start_line": e["start_line"],
            "end_line": e["end_line"],
            "item_kind": e.get("item_kind") or None,
            "item_id": e.get("item_id") or None,
            "raw_text": e["raw_text"],
        })
    return out


def _merge(per_query: list[tuple[str, dict]], top_k: int) -> tuple[list[dict], list[dict]]:
    """Round-robin by rank across queries, deduped by chunk_id, so every
    sub-question keeps its best hits regardless of score scale differences."""
    lists, coverage = [], []
    for q, res in per_query:
        if res["type"] == "search":
            hits = _flatten_search_results(res["results"])
        elif res["type"] == "unique":
            hits = _flatten_search_results([{"entity": res["result"], "final_score": None}])
        else:
            hits = []
        coverage.append({"query": q, "type": res["type"], "results": len(hits),
                         "top_score": hits[0]["final_score"] if hits else None,
                         "feature_filter": res.get("feature_filter")})
        lists.append([{**h, "matched_queries": [q]} for h in hits])
    merged, seen = [], {}
    for i in range(max((len(l) for l in lists), default=0)):
        for l in lists:
            if i >= len(l):
                continue
            h = l[i]
            if h["chunk_id"] in seen:
                seen[h["chunk_id"]]["matched_queries"] += h["matched_queries"]
                continue
            seen[h["chunk_id"]] = h
            merged.append(h)
    return merged[:top_k * len(per_query)], coverage


def _expand_sections(results: list[dict], max_chars: int) -> None:
    """Attach the enclosing section of each hit. A hit whose parent is a
    whole-file root (or that has no parent) is already a section and
    expands to itself. A section over max_chars is cut to a window around
    the hit and flagged, with the full span in "section_lines" for the
    caller to read from the file."""
    rows = {}
    try:
        client = get_client()
        ids = sorted({r["chunk_id"] for r in results})
        for i in range(0, len(ids), 100):
            batch = ids[i:i + 100]
            for row in client.query(collection_name=COLLECTION_NAME,
                                    filter=f"chunk_id in {json.dumps(batch)}",
                                    output_fields=["chunk_id", "parent_chunk_id"]):
                rows[row["chunk_id"]] = row
        parent_ids = sorted({r["parent_chunk_id"] for r in rows.values() if r["parent_chunk_id"]})
        parents = {}
        for i in range(0, len(parent_ids), 100):
            for row in client.query(collection_name=COLLECTION_NAME,
                                    filter=f"chunk_id in {json.dumps(parent_ids[i:i + 100])}",
                                    output_fields=["chunk_id", "parent_chunk_id", "heading_path",
                                                   "file_path", "start_line", "end_line", "raw_text"]):
                parents[row["chunk_id"]] = row
    except Exception as e:  # expansion is best-effort; hits are still usable
        for r in results:
            r["section"] = {"error": f"expansion failed: {e}"}
        return
    emitted = set()
    for r in results:
        pid = rows.get(r["chunk_id"], {}).get("parent_chunk_id") or ""
        p = parents.get(pid)
        # Expanding to a file root would hand back the whole document.
        src = p if p and p.get("parent_chunk_id") else None
        sec = src or {"chunk_id": r["chunk_id"], "heading_path": r["heading_path"], "file_path": r["file_path"],
                      "start_line": r["start_line"], "end_line": r["end_line"], "raw_text": r["raw_text"]}
        if sec["chunk_id"] in emitted:
            r["section"] = {"same_as": sec["chunk_id"]}
            continue
        emitted.add(sec["chunk_id"])
        lines = sec["raw_text"].splitlines()
        lo, hi = 0, len(lines)
        # Too big: keep a window of whole lines centred on the hit, so the
        # matched lines are never the part that gets cut.
        if len(sec["raw_text"]) > max_chars:
            lo = hi = max(0, min(r["start_line"] - sec["start_line"], len(lines) - 1))
            size = 0
            while (lo > 0 or hi < len(lines)) and size < max_chars:
                if hi < len(lines):
                    size += len(lines[hi]) + 1
                    hi += 1
                if lo > 0 and size < max_chars:
                    lo -= 1
                    size += len(lines[lo]) + 1
        r["section"] = {"chunk_id": sec["chunk_id"], "heading_path": sec["heading_path"],
                        "file_path": sec["file_path"],
                        "start_line": sec["start_line"] + lo, "end_line": sec["start_line"] + hi - 1,
                        "truncated": (lo, hi) != (0, len(lines)),
                        "section_lines": [sec["start_line"], sec["end_line"]],
                        "text": "\n".join(lines[lo:hi])}


def _files(results: list[dict]) -> list[dict]:
    by_file: dict[str, dict] = {}
    for rank, r in enumerate(results):
        f = by_file.setdefault(r["file_path"], {"file_path": r["file_path"], "first_rank": rank,
                                                "hits": 0, "headings": []})
        f["hits"] += 1
        if r["heading_path"] not in f["headings"]:
            f["headings"].append(r["heading_path"])
    return sorted(by_file.values(), key=lambda f: (f["first_rank"], -f["hits"]))


def _code_context(args, result: dict, project_root) -> dict:
    if args.no_graph:
        return {"ran": False, "trigger": "disabled", "reason": "--no-graph"}
    if result["type"] != "search":
        return {"ran": False, "trigger": "not_applicable",
                "reason": f"'{result['type']}' item-id lookup returns no chunks to seed from"}
    kind = graph_context.code_question_kind(args.query) or ("always" if args.graph_always else None)
    if kind:
        ctx = graph_context.code_context(result["results"], query=args.query, project_root=project_root,
                                         hops=args.graph_hops, max_nodes=args.graph_max_nodes)
        if not ctx["available"]:
            return {"ran": False, "trigger": f"query_{kind}", **ctx}
        return {"ran": True, "trigger": f"query_{kind}", **ctx}
    return {"ran": False, "trigger": "none", "reason": "not a where / what-calls / what-depends question"}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query")
    parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--fetch-k", type=int, default=20)
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--no-boost", action="store_true")
    parser.add_argument("--no-graph", action="store_true")
    parser.add_argument("--graph-always", action="store_true",
                        help="run the code-graph step even when the question isn't a where/calls question")
    parser.add_argument("--sub", action="append", default=[], help="additional sub-question (repeatable)")
    parser.add_argument("--expand", action="store_true", help="attach each hit's enclosing section")
    parser.add_argument("--expand-max-chars", type=int, default=6000)
    parser.add_argument("--graph-hops", type=int, choices=[1, 2], default=1)
    parser.add_argument("--graph-max-nodes", type=int, default=12)
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)

    project_root = config.resolve_project_root(args.project_root)
    ok, msg = _collection_ready(project_root)
    if not ok:
        print(msg, file=sys.stderr)
        return 1

    def run(q: str) -> dict:
        return answer_candidates(q, mode=args.mode, fetch_k=args.fetch_k, top_k=args.top_k,
                                 rerank=not args.no_rerank, item_kind_boost=not args.no_boost)

    result = run(args.query)
    if args.sub:
        per_query = [(args.query, result)] + [(q, run(q)) for q in args.sub]
        merged, coverage = _merge(per_query, args.top_k)
        result = {"type": "search", "mode": args.mode, "reranked": not args.no_rerank,
                  "results": merged, "coverage": coverage}
    elif result["type"] == "search":
        result["results"] = _flatten_search_results(result["results"])
    if result["type"] == "search":
        if args.expand:
            _expand_sections(result["results"], args.expand_max_chars)
        result["files"] = _files(result["results"])
    result["code_context"] = _code_context(args, result, project_root)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
