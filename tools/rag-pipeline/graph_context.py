"""Code-side context for RAG answers, from the project's graphify knowledge
graph (graphify-out/graph.json).

Seeds come ONLY from backticked code symbols in the retrieved spec chunks —
never from free-text queries against the graph — so code context is always
anchored to something a cited spec actually names. Each seed is expanded
1-2 hops over EXTRACTED edges (AST-derived; INFERRED edges are opt-in).

Symbol -> node resolution uses only the rules that cleared a ~95% precision
gate on sampled resolutions (checked against the cited file:line):
  exact_qualified  `Spree::Cart::AddItem`        -> label match
  spree_prefix     `Cart::AddItem`               -> `Spree::Cart::AddItem`
  end_of_name      `Rules::MinimizeSplits`       -> the one label ending in it
  class#method     `Order#finalize` / `X.match`  -> `.finalize()` in X's file(s)
  collapse         one name reopened in N files  -> the canonical-path file
Bare exact names (`BulkAction`, `SCOPES`) are deliberately NOT resolved:
they measured ~90% because the graph has no nodes for Ruby constants or
inner classes, so a same-named TypeScript node silently stands in for the
Ruby symbol the spec meant.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import config

STOPLIST = {"spree", "base", "basecontroller", "client", "default", "types", "url"}
MAX_CANDIDATES = 5

_SOURCE_EXT = re.compile(r"\.(rb|tsx?|m?jsx?)$")
_EXCLUDED_DIR = re.compile(r"(^|/)(vendor|templates|node_modules)/")
_TEST_PATH = re.compile(r"(^|/)(spec|specs|test|tests|e2e|__tests__)/|_spec\.rb$|\.(test|spec)\.[jt]sx?$")
_FILE_LABEL = re.compile(r"\.(rb|tsx?|jsx?|mjs|json|ya?ml|md|mdx)$")
_TICK = re.compile(r"`([^`\n]{2,120})`")
_CLASS_METHOD = re.compile(r"^([A-Z][\w:]*)[#.](\w+[?!]?)$")
_CONST = re.compile(r"^[A-Z][\w:]*$")

# Callers first, then type relations, then outbound calls/imports. `method`
# edges mostly enumerate a class's own body, so they're capped; `contains`
# (file/namespace nesting) is never useful as context and is skipped.
REL_PRIORITY = {
    ("calls", "in"): 0, ("indirect_call", "in"): 0,
    "inherits": 1, "mixes_in": 1, "extends": 1, "implements": 1,
    ("calls", "out"): 2, ("indirect_call", "out"): 2, "references": 3,
    "imports_from": 4, "imports": 4, "re_exports": 5, "method": 6,
}
SKIP_RELATIONS = {"contains"}
MAX_METHOD_EDGES = 2


def _is_method(n: dict) -> bool:
    return n["label"].startswith(".") and n["label"].endswith("()")


def _same_file_method_call(a: dict, b: dict, edge: dict) -> bool:
    """graphify resolves `receiver.foo` to a same-named method in the current
    file (e.g. `store.orders` -> this class's #orders); measured 87% precise,
    so these edges are never shown."""
    return (edge["relation"] in ("calls", "indirect_call") and _is_method(a) and _is_method(b)
            and a.get("source_file") == b.get("source_file"))


def _priority(relation: str, direction: str) -> int:
    return REL_PRIORITY.get((relation, direction), REL_PRIORITY.get(relation, 9))


def _snake(s: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", s).lower()


def _canonical_suffix(label: str) -> str:
    """`Spree::Cart::AddItem` -> `spree/cart/add_item.rb`."""
    return "/".join(_snake(p) for p in label.split("::")) + ".rb"


def _line(node: dict) -> int | None:
    loc = node.get("source_location") or ""
    return int(loc[1:]) if loc[:1] == "L" and loc[1:].isdigit() else None


def _citable(n: dict) -> bool:
    f = n.get("source_file") or ""
    return (n.get("file_type") == "code" and bool(f) and _line(n) is not None
            and bool(_SOURCE_EXT.search(f)) and not _EXCLUDED_DIR.search(f)
            and not _TEST_PATH.search(f) and not f.endswith("_decorator.rb")
            and n["label"] != Path(f).name and not _FILE_LABEL.search(n["label"]))


class _Graph:
    def __init__(self, path: Path):
        data = json.loads(path.read_text())
        self.path = path
        self.built_at_commit = data.get("built_at_commit")
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.by_norm: dict[str, list[dict]] = defaultdict(list)
        self.by_suffix: dict[str, set[str]] = defaultdict(set)
        for n in self.nodes.values():
            if not _citable(n):
                continue
            label = n["label"]
            self.by_norm[(n.get("norm_label") or label.lower())].append(n)
            if "::" in label:
                parts = label.lower().split("::")
                for i in range(1, len(parts)):
                    self.by_suffix["::".join(parts[i:])].add(label)
        self.adj: dict[str, list[tuple[str, dict, str]]] = defaultdict(list)
        for e in data["links"]:
            self.adj[e["source"]].append((e["target"], e, "out"))
            self.adj[e["target"]].append((e["source"], e, "in"))

    def lookup(self, name: str) -> list[dict]:
        """Citable candidates for a label, with the stoplist and candidate cap
        applied. A qualified name over the cap survives only if exactly one
        candidate sits at its canonical path (a class reopened across files,
        e.g. Spree::Order in order.rb + order/*.rb), never a bare namespace."""
        key = name.lower()
        if key in STOPLIST:
            return []
        hits = self.by_norm.get(key, [])
        if len(hits) <= MAX_CANDIDATES:
            return hits
        if "::" in name and self._collapse(hits) is not None:
            return hits
        return []

    @staticmethod
    def _collapse(hits: list[dict]) -> dict | None:
        if len({n["label"] for n in hits}) != 1 or "::" not in hits[0]["label"]:
            return None
        canon = [n for n in hits if n["source_file"].endswith(_canonical_suffix(n["label"]))]
        return canon[0] if len(canon) == 1 else None

    def _single(self, hits: list[dict], rule: str) -> tuple[dict, str] | None:
        if len(hits) == 1:
            return hits[0], rule
        c = self._collapse(hits)
        return (c, "collapse") if c else None

    def resolve(self, symbol: str) -> tuple[dict, str] | None:
        """(node, rule) if every enabled rule that fires agrees on one node."""
        s = symbol.strip()
        s = s[:-2] if s.endswith("()") else s
        if not s or " " in s or "/" in s or s.lower() in STOPLIST:
            return None
        found: list[tuple[dict, str]] = []
        m = _CLASS_METHOD.match(s)
        if m:
            cls, meth = m.groups()
            for c in (cls, f"Spree::{cls}"):
                files = {n["source_file"] for n in self.lookup(c)}
                hits = [n for n in self.by_norm.get(f".{meth.lower()}()", []) if n["source_file"] in files]
                if len(hits) == 1:
                    found.append((hits[0], "class#method"))
                    break
        elif _CONST.match(s):
            if "::" in s:
                r = self._single(self.lookup(s), "exact_qualified")
                if r: found.append(r)
                # Never prefix a bare word: `Digital` (a stock splitter) would
                # silently become the unrelated Spree::Digital model.
                if not s.startswith("Spree::"):
                    r = self._single(self.lookup(f"Spree::{s}"), "spree_prefix")
                    if r: found.append(r)
            if "::" in s or len(re.findall(r"[A-Z]", s)) >= 3:
                labels = self.by_suffix.get(s.lower(), set())
                if len(labels) == 1:
                    r = self._single(self.lookup(next(iter(labels))), "end_of_name")
                    if r: found.append(r)
        if not found or len({n["id"] for n, _ in found}) > 1:
            return None
        # A bare name that also matches a different unique node on its own
        # (`Role`: Spree::Role vs the admin-sdk `Role` type) is ambiguous —
        # the spec may mean either.
        if "::" not in s and not m:
            bare = self._single([n for n in self.lookup(s) if n["label"] == s], "exact_bare")
            if bare and bare[0]["id"] != found[0][0]["id"]:
                return None
        return found[0]

    def display_name(self, node: dict) -> str:
        """`.call()` -> `Spree::Cart::AddItem#call` via its owning class's `method` edge."""
        label = node["label"]
        if not (label.startswith(".") and label.endswith("()")):
            return label
        for other, e, direction in self.adj.get(node["id"], []):
            if e["relation"] == "method" and direction == "in":
                return f"{self.nodes[other]['label']}#{label[1:-2]}"
        return label


@lru_cache(maxsize=4)
def _load(path_str: str) -> _Graph:
    return _Graph(Path(path_str))


def _chunk_fields(chunk: dict) -> tuple[str, str]:
    e = chunk.get("entity", chunk)
    return e["chunk_id"], e["raw_text"]


def _changed_since(project_root: Path, commit: str | None, files: set[str]) -> set[str] | None:
    """Files among `files` that differ between `commit` and the working tree.
    None when that can't be determined (no commit recorded, no git)."""
    if not commit or not files:
        return set() if commit else None
    try:
        out = subprocess.run(["git", "diff", "--name-only", commit, "--", *sorted(files)],
                             cwd=project_root, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return set(out.stdout.split()) if out.returncode == 0 else None


def _node_out(g: _Graph, n: dict) -> dict:
    return {"name": g.display_name(n), "source_file": n["source_file"],
            "source_location": n["source_location"], "line": _line(n)}


_WHERE_Q = re.compile(
    r"\b(where\s+(is|are|does|do|did)|which\s+(file|class|module|method|service|controller)s?|"
    r"implemented|implementation\s+of|defined|definition\s+of|lives?\s+in)\b", re.IGNORECASE)
_CALLS_Q = re.compile(
    r"\b(what|who|which)\s+(\w+\s+){0,2}(calls?|invokes?|uses?|triggers?|references?|depends?\s+on)\b|"
    r"\bcall(er|ers|ed\s+by|s)\b|\bdepend(s|ency|encies|ents)\b|\bused\s+by\b", re.IGNORECASE)

CALLER_NOTE = ("Graph call edges are partial. Calls through variables (order.foo) are not "
               "captured. Absence of a caller is NOT evidence that none exists.")


def code_question_kind(query: str) -> str | None:
    """'calls' for what-calls / what-depends questions, 'where' for
    where-is-it-implemented questions, else None."""
    if _CALLS_Q.search(query):
        return "calls"
    if _WHERE_Q.search(query):
        return "where"
    return None


def _words(text: str) -> set[str]:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return {w[:6] for w in re.findall(r"[a-z]{4,}", spaced.lower())}


def _named_in_query(raw: str, name: str, query: str) -> bool:
    """The query names this symbol: its chunk spelling, or any qualified tail
    of its resolved name (`Calculator::DefaultTax`, `Coordinator#packages`)
    — never a bare single word like `Update`."""
    parts = re.split(r"(::|#)", name)
    tails = {"".join(parts[i:]) for i in range(0, len(parts), 2)}
    candidates = {raw.strip().removesuffix("()")} | {t for t in tails if "::" in t or "#" in t}
    return any(re.search(rf"(?<![\w:]){re.escape(c)}(?![\w])", query) for c in candidates)


def _round_robin(groups: list[list[dict]]) -> list[dict]:
    out, i = [], 0
    while any(i < len(gr) for gr in groups):
        out.extend(gr[i] for gr in groups if i < len(gr))
        i += 1
    return out


def code_context(chunks: list[dict], *, query: str = "", project_root: Path | None = None,
                 hops: int = 1, include_inferred: bool = False, max_nodes: int = 12,
                 max_neighbors_per_seed: int = 8, max_hop2_per_node: int = 3) -> dict:
    """Resolve code symbols named in `chunks` (ranked retrieval results, either
    flattened or raw Milvus hits) to graph nodes and expand them. `query` only
    orders the output and selects the caller note; it is never resolved
    against the graph itself.

    Returns {"available": False, "note": ...} if the graph file is missing.
    Otherwise seeds (definitions of chunk-named symbols) and neighbors, capped
    at `max_nodes` in priority order: query-named seeds each followed by their
    neighbors, then the other seeds (by word overlap with the query, then
    chunk rank), then their neighbors round-robin. `budget` reports what each
    limit dropped.
    """
    root = project_root or config.resolve_project_root()
    path = config.graph_path(root)
    if not path.is_file():
        return {"available": False, "note": f"No knowledge graph at {path}; code context skipped."}
    g = _load(str(path))
    allowed = {"EXTRACTED", "INFERRED"} if include_inferred else {"EXTRACTED"}

    seeds: dict[str, dict] = {}
    for chunk in chunks:
        chunk_id, text = _chunk_fields(chunk)
        for raw in _TICK.findall(text):
            r = g.resolve(raw)
            if r is None:
                continue
            node, rule = r
            if node["id"] in seeds:
                if chunk_id not in seeds[node["id"]]["chunk_ids"]:
                    seeds[node["id"]]["chunk_ids"].append(chunk_id)
                continue
            callers = {o for o, e, d in g.adj.get(node["id"], [])
                       if d == "in" and e["relation"] in ("calls", "indirect_call")
                       and e.get("confidence") in allowed and _citable(g.nodes.get(o, {}))
                       and not _same_file_method_call(g.nodes[o], node, e)}
            seeds[node["id"]] = {"symbol": raw.strip(), "rule": rule,
                                 "query_named": _named_in_query(raw, g.display_name(node), query),
                                 "chunk_ids": [chunk_id], **_node_out(g, node),
                                 "callers_recorded": bool(callers), "callers_recorded_count": len(callers)}

    def expand(node_id: str, exclude: set[str]) -> list[tuple[str, dict, str]]:
        edges = [(other, e, d) for other, e, d in g.adj.get(node_id, [])
                 if e.get("confidence") in allowed and e["relation"] not in SKIP_RELATIONS
                 and other not in exclude and _citable(g.nodes.get(other, {}))
                 and not _same_file_method_call(g.nodes[node_id], g.nodes[other], e)]
        edges.sort(key=lambda t: (_priority(t[1]["relation"], t[2]),
                                  g.nodes[t[0]]["source_file"], _line(g.nodes[t[0]]) or 0))
        out, seen, method_edges = [], set(), 0
        for other, e, d in edges:
            if other in seen:
                continue
            if e["relation"] == "method":
                if method_edges >= MAX_METHOD_EDGES:
                    continue
                method_edges += 1
            seen.add(other)
            out.append((other, e, d))
        return out

    def neighbor(other: str, e: dict, d: str, seed_id: str, via: str, hop: int) -> dict:
        return {**_node_out(g, g.nodes[other]), "seed": seeds[seed_id]["name"], "via": via,
                "relation": e["relation"], "direction": d, "confidence": e.get("confidence"),
                "edge_location": e.get("source_location"), "hop": hop, "_seed_id": seed_id}

    qwords = _words(query)
    rank = {sid: i for i, sid in enumerate(seeds)}
    ordered_seeds = sorted(seeds, key=lambda sid: (not seeds[sid]["query_named"],
                                                   -len(qwords & _words(seeds[sid]["name"])), rank[sid]))
    per_seed: dict[str, list[dict]] = {}
    dropped_per_seed = 0
    visited = set(seeds)
    for seed_id in ordered_seeds:
        hop1 = expand(seed_id, visited)
        dropped_per_seed += max(0, len(hop1) - max_neighbors_per_seed)
        hop1 = hop1[:max_neighbors_per_seed]
        group = []
        for other, e, d in hop1:
            visited.add(other)
            group.append(neighbor(other, e, d, seed_id, seeds[seed_id]["name"], 1))
        if hops >= 2:
            for mid, _, _ in hop1:
                hop2 = expand(mid, visited)
                dropped_per_seed += max(0, len(hop2) - max_hop2_per_node)
                for other, e, d in hop2[:max_hop2_per_node]:
                    visited.add(other)
                    group.append(neighbor(other, e, d, seed_id, g.display_name(g.nodes[mid]), 2))
        per_seed[seed_id] = group

    named = [s for s in ordered_seeds if seeds[s]["query_named"]]
    others = [s for s in ordered_seeds if not seeds[s]["query_named"]]
    ranked = ([("seed", s) for s in named] + [("nbr", n) for s in named for n in per_seed[s]]
              + [("seed", s) for s in others] + [("nbr", n) for n in _round_robin([per_seed[s] for s in others])])
    kept = ranked[:max_nodes]
    kept_seeds = [x for k, x in kept if k == "seed"]
    kept_ids = set(kept_seeds)
    kept_neighbors = [{k: v for k, v in n.items() if k != "_seed_id"}
                      for kind_, n in kept if kind_ == "nbr" and n["_seed_id"] in kept_ids]
    total_neighbors = sum(len(v) for v in per_seed.values())

    kind = code_question_kind(query)
    files = {seeds[s]["source_file"] for s in kept_seeds} | {n["source_file"] for n in kept_neighbors}
    changed = _changed_since(root, g.built_at_commit, files)
    return {
        "available": True,
        "graph_path": str(path),
        "built_at_commit": g.built_at_commit,
        "stale_files": sorted(changed) if changed is not None else "unknown",
        "edge_confidence": sorted(allowed),
        "hops": hops,
        **({"caller_note": CALLER_NOTE} if kind == "calls" else {}),
        "budget": {
            "max_nodes": max_nodes,
            "returned": len(kept_seeds) + len(kept_neighbors),
            "dropped_seeds": len(ordered_seeds) - len(kept_seeds),
            "dropped_neighbors_by_total_cap": total_neighbors - len(kept_neighbors),
            "dropped_neighbors_by_per_seed_cap": dropped_per_seed,
        },
        "seeds": [seeds[s] for s in kept_seeds],
        "neighbors": kept_neighbors,
    }
