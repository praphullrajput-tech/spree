#!/usr/bin/env python3
"""Rebuild the target project's RAG index end to end: discover the corpus,
chunk it into a fresh output/<project_slug>/ tree, recreate the Milvus
collection, and embed + insert.

Usage:
    python3 build_index.py [--project-root PATH] [--chunk-only] [--list] [--specs-only]

The corpus is more than specs/: the questions developers actually ask
("how do I run this locally", "where do tests live") are answered by the
project's CLAUDE.md, developer docs, and architecture plans, which the
specs-only index could never retrieve.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

CORPUS_GLOBS = [
    "specs/*/spec.md",
    "specs/*/plan.md",
    "specs/*/tasks.md",
    ".specify/memory/constitution.md",
    "CLAUDE.md",
    "docs/developer/**/*.md",
    "docs/developer/**/*.mdx",
    "docs/plans/*.md",
]
SPECS_ONLY_GLOBS = CORPUS_GLOBS[:4]
EXCLUDED_NAMES = {"_template.md"}


def discover(root: Path, globs: list[str] = CORPUS_GLOBS) -> list[Path]:
    found = set()
    for pattern in globs:
        for p in root.glob(pattern):
            if p.is_file() and p.name not in EXCLUDED_NAMES:
                found.add(p.relative_to(root))
    return sorted(found)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--chunk-only", action="store_true", help="chunk to output/ but don't touch Milvus")
    parser.add_argument("--list", action="store_true", help="print the discovered corpus and exit")
    parser.add_argument("--specs-only", action="store_true",
                        help="index only specs/ + constitution (the original corpus, for A/B runs)")
    args = parser.parse_args(argv)

    # config/milvus_schema resolve the project at import time, so pin it first.
    if args.project_root:
        os.environ["RAG_PROJECT_ROOT"] = str(Path(args.project_root).resolve())
    import config
    root = config.resolve_project_root()

    relpaths = discover(root, SPECS_ONLY_GLOBS if args.specs_only else CORPUS_GLOBS)
    if args.list:
        print("\n".join(map(str, relpaths)))
        print(f"\n{len(relpaths)} files", file=sys.stderr)
        return 0

    out = config.output_dir(root)
    if out.exists():
        shutil.rmtree(out)

    import chunk_docs
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        chunk_docs.main([str(root), *map(str, relpaths)])
    n_files = len(list(out.glob("*.json")))
    print(f"Chunked {len(relpaths)} files -> {n_files} chunk trees in {out}")
    if args.chunk_only:
        return 0

    import embed_and_insert
    from milvus_schema import create_collection, get_client
    create_collection(get_client(), recreate=True)
    embed_and_insert.main()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
