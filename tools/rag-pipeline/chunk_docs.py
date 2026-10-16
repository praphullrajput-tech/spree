#!/usr/bin/env python3
"""Phase 1 CLI: chunk speckit markdown docs into a parent/child tree.

Usage:
    python3 chunk_docs.py <repo_root> <relpath> [<relpath> ...]

Writes one JSON file per input doc to ./output/<project_slug>/<file_id>.json
(project_slug derived from repo_root, see config.py) containing the full
chunk tree (parents = headings, children = template-specific items), and
prints a few sample chunks to stdout for inspection.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import config
from chunker.engine import Chunk, _split_frontmatter, parse_headings, headings_to_chunks
from chunker.ids import file_id
from chunker.templates import TEMPLATES

_FM_FIELD_RE = re.compile(r"^(title|description):\s*['\"]?(.*?)['\"]?\s*$")


def _frontmatter(lines: list[str], body_start: int) -> dict:
    out = {}
    for line in lines[1:max(body_start - 1, 1)]:
        m = _FM_FIELD_RE.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _add_doc_context(chunks: list[Chunk], lines: list[str], relpath: Path, file_path: str) -> None:
    """Developer docs (.mdx) carry their title in frontmatter and have no H1,
    so their sections would otherwise be indexed as context-free "Overview"
    chunks and the intro text before the first heading would be dropped.
    Prefix every heading_path with the doc title and add a preamble chunk
    (title + description + intro) as its own leaf."""
    if any(lines[c.start_line - 1].startswith("# ") for c in chunks if c.chunk_type == "parent"):
        return
    body_start = _split_frontmatter(lines)
    fm = _frontmatter(lines, body_start)
    title = fm.get("title") or relpath.stem.replace("-", " ").replace("_", " ")
    for c in chunks:
        c.heading_path = f"{title} > {c.heading_path}"
    first_heading = min((c.start_line for c in chunks), default=len(lines) + 1)
    intro = [l for l in lines[body_start:first_heading - 1]
             if l.strip() and not l.lstrip().startswith(("import ", "<Since"))]
    text = "\n".join([f"# {title}"] + ([fm["description"]] if fm.get("description") else []) + intro)
    if len(text) > len(title) + 2:
        chunks.append(Chunk(
            chunk_id=f"{file_id(relpath)}__preamble", file_path=file_path, heading_path=title,
            start_line=1, end_line=max(first_heading - 1, 1), chunk_type="parent",
            parent_chunk_id=None, raw_text=text,
        ))


def chunk_file(repo_root: Path, relpath: Path) -> list[dict]:
    abspath = repo_root / relpath
    lines = abspath.read_text(encoding="utf-8").splitlines()
    file_path = str(relpath)

    headings = parse_headings(lines, relpath)
    chunks = headings_to_chunks(headings, lines, file_path)

    rule = TEMPLATES.get(relpath.name)
    if rule is not None:
        chunks.extend(rule(lines, headings, file_path))
    else:
        _add_doc_context(chunks, lines, relpath, file_path)

    # Stable, readable ordering: by start_line, so the JSON reads top-to-bottom.
    chunks.sort(key=lambda c: (c.start_line, 0 if c.chunk_type == "parent" else 1))
    return [c.to_dict() for c in chunks]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    repo_root = Path(argv[0]).resolve()
    relpaths = [Path(p) for p in argv[1:]]

    output_dir = config.output_dir(repo_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_chunks: list[dict] = []
    for relpath in relpaths:
        chunks = chunk_file(repo_root, relpath)
        out_path = output_dir / f"{file_id(relpath)}.json"
        out_path.write_text(json.dumps(chunks, indent=2, ensure_ascii=False), encoding="utf-8")
        parents = sum(1 for c in chunks if c["chunk_type"] == "parent")
        children = sum(1 for c in chunks if c["chunk_type"] == "child")
        print(f"{relpath}: {parents} parent chunks, {children} child chunks -> {out_path}")
        all_chunks.extend(chunks)

    print(f"\nTotal: {len(all_chunks)} chunks across {len(relpaths)} files\n")
    print("=== 5 sample chunks ===")
    # Bias the sample toward children so it's not just headings.
    sample = [c for c in all_chunks if c["chunk_type"] == "child"][:3] + \
             [c for c in all_chunks if c["chunk_type"] == "parent"][:2]
    for c in sample[:5]:
        print(json.dumps(c, indent=2, ensure_ascii=False)[:1200])
        print("---")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
