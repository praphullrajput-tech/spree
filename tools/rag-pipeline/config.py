"""Per-project configuration: which spec-kit project this pipeline run
targets, and the names/paths derived from it (Milvus collection, specs/
directory, chunk-output directory). Generic across any spec-kit project —
nothing here names a specific project.

Resolution order for the target project's root:
  1. an explicit path passed by the caller (e.g. chunk_docs.py's CLI arg)
  2. the RAG_PROJECT_ROOT environment variable
  3. the current working directory

This lets one pipeline installation serve multiple spec-kit projects: run
it from inside each project's root (the zero-config path), or point
RAG_PROJECT_ROOT at a project without cd'ing into it.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def resolve_project_root(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).resolve()
    env = os.environ.get("RAG_PROJECT_ROOT")
    return Path(env).resolve() if env else Path.cwd().resolve()


def project_slug(project_root: Path | None = None) -> str:
    """Stable, Milvus-collection-name-safe id derived from the project
    root's directory name (e.g. 'spree' -> 'spree', 'My Client App' ->
    'my_client_app'). Collisions between two differently-located but
    identically-named checkouts are possible (accepted trade-off — a
    readable collection name over a path hash)."""
    root = project_root or resolve_project_root()
    return _SLUG_RE.sub("_", root.name.lower()).strip("_") or "project"


def specs_dir(project_root: Path | None = None) -> Path:
    return (project_root or resolve_project_root()) / "specs"


def collection_name(project_root: Path | None = None) -> str:
    return f"{project_slug(project_root)}_speckit_rag_chunks"


def graph_path(project_root: Path | None = None) -> Path:
    """The project's graphify knowledge graph. RAG_GRAPH_PATH overrides the
    default `<project_root>/graphify-out/graph.json`."""
    env = os.environ.get("RAG_GRAPH_PATH")
    if env:
        return Path(env).resolve()
    return (project_root or resolve_project_root()) / "graphify-out" / "graph.json"


def output_dir(project_root: Path | None = None) -> Path:
    """Per-project chunk-tree cache — kept under the pipeline's own
    directory (not the target project) but namespaced by project_slug so
    one shared pipeline install serving several projects never mixes their
    chunks in the same folder."""
    return Path(__file__).parent / "output" / project_slug(project_root)
