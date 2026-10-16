"""Generic, file-type-agnostic markdown chunker.

Splits any markdown file into heading-bounded "parent" chunks (one per
``#``-``######`` line), each carrying:
- a full-section line span (heading down to the line before the next
  heading at the same or shallower level — i.e. including its own
  subheadings), used to expand a matched child chunk to fuller context
- a direct-body line span (heading down to the line before the *next*
  heading at ANY level), used only internally to scope which body text
  belongs to this heading and not to one of its subheadings
- a heading-path breadcrumb built by walking the enclosing heading stack

This module knows nothing about spec.md/tasks.md/plan.md/constitution.md
structure — that lives in templates.py, which calls back into
``scan_bullets`` with a file-type-specific item regex.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from .ids import file_id, slug

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET_START_RE = re.compile(r"^-\s+")
_FRONTMATTER_CLOSE = ("---", "...")
_FRONTMATTER_MAX_LINES = 200


@dataclass
class Heading:
    chunk_id: str
    level: int
    title: str
    heading_path: str
    parent_chunk_id: Optional[str]
    start_line: int
    end_line: Optional[int] = None       # full-section span (incl. subheadings)
    body_end_line: Optional[int] = None  # direct-body span (excl. subheadings)


@dataclass
class Chunk:
    chunk_id: str
    file_path: str
    heading_path: str
    start_line: int
    end_line: int
    chunk_type: str  # "parent" | "child"
    parent_chunk_id: Optional[str]
    raw_text: str
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if k != "extra"}
        d.update(self.extra)
        return d


def _split_frontmatter(lines: list[str]) -> int:
    """0-based index where the body starts (0 if the file has no frontmatter)."""
    if not lines or lines[0].strip() != "---":
        return 0
    limit = min(len(lines), _FRONTMATTER_MAX_LINES + 1)
    for i in range(1, limit):
        if lines[i].strip() in _FRONTMATTER_CLOSE:
            return i + 1
    return 0


def parse_headings(lines: list[str], relpath: Path) -> list[Heading]:
    """One Heading per heading line, with both line spans resolved."""
    fid = file_id(relpath)
    body_start = _split_frontmatter(lines)
    headings: list[Heading] = []
    stack: list[Heading] = []
    seen_ids: set[str] = set()

    def mint_id(title: str) -> str:
        base = f"{fid}__{slug(title)}"
        cid, n = base, 2
        while cid in seen_ids:
            cid = f"{base}_{n}"
            n += 1
        seen_ids.add(cid)
        return cid

    in_fence = False
    for idx in range(body_start, len(lines)):
        line = lines[idx]
        stripped = line.strip()
        # A `#`-prefixed line inside a fenced code block (a tree diagram's
        # comment, a shell "# ..." example) is content, never a heading —
        # toggle on the fence delimiter itself and skip everything between.
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if not m:
            continue
        line_num = idx + 1
        level = len(m.group(1))
        title = m.group(2).strip()

        # The immediately preceding heading's direct-body span ends right
        # before this one, whatever its level.
        if headings and headings[-1].body_end_line is None:
            headings[-1].body_end_line = line_num - 1

        # Close full-section spans for every open heading at this level or shallower.
        while stack and stack[-1].level >= level:
            closed = stack.pop()
            closed.end_line = line_num - 1

        parent = stack[-1] if stack else None
        heading_path = f"{parent.heading_path} > {title}" if parent else title
        h = Heading(
            chunk_id=mint_id(title), level=level, title=title,
            heading_path=heading_path,
            parent_chunk_id=parent.chunk_id if parent else None,
            start_line=line_num,
        )
        headings.append(h)
        stack.append(h)

    for h in headings:
        if h.end_line is None:
            h.end_line = len(lines)
        if h.body_end_line is None:
            h.body_end_line = len(lines)

    return headings


def headings_to_chunks(headings: list[Heading], lines: list[str], file_path: str) -> list[Chunk]:
    chunks = []
    for h in headings:
        text = "\n".join(lines[h.start_line - 1:h.end_line])
        chunks.append(Chunk(
            chunk_id=h.chunk_id, file_path=file_path, heading_path=h.heading_path,
            start_line=h.start_line, end_line=h.end_line, chunk_type="parent",
            parent_chunk_id=h.parent_chunk_id, raw_text=text,
        ))
    return chunks


def scan_bullets(lines: list[str], body_start_line: int, body_end_line: int,
                  item_re: re.Pattern) -> list[dict]:
    """Yield one dict per top-level bullet matching *item_re* inside
    ``[body_start_line, body_end_line]`` (1-indexed, inclusive).

    A bullet's span starts at its own ``item_re``-matching line and grows one
    line at a time: an indented, non-blank line (a wrapped/continued line of
    the same bullet, e.g. constitution.md's Quality Gates entries) extends
    it; a blank line is held pending without deciding anything yet; a sibling
    ``item_re`` match or any other top-level ``- `` bullet closes it
    immediately. Critically, an UNINDENTED non-blank, non-bullet line (a
    following paragraph — e.g. tasks.md's ``**Checkpoint**: ...`` notes
    between phases) also closes it, at its last real content line — the same
    rule CommonMark uses for when a paragraph breaks out of a list. Without
    this, the last item in a section would swallow every line up to the next
    heading, including notes and dividers that aren't part of the item.
    """
    items: list[dict] = []
    current: Optional[dict] = None
    in_fence = False

    def close(end_line: int) -> None:
        nonlocal current
        current["end_line"] = end_line
        items.append(current)
        current = None

    for idx in range(body_start_line - 1, body_end_line):
        line = lines[idx]
        line_num = idx + 1
        stripped = line.strip()
        # A fenced code block can contain a line that starts with "- " (a
        # YAML/shell example) — never mistake it for a real bullet or item.
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            if current is not None:
                current["end_line"] = line_num
            continue
        if in_fence:
            if current is not None:
                current["end_line"] = line_num
            continue
        m = item_re.match(line)
        if m:
            if current is not None:
                close(current["end_line"])
            current = {"match": m, "start_line": line_num, "end_line": line_num}
            continue
        if _BULLET_START_RE.match(line):
            if current is not None:
                close(current["end_line"])
            continue
        if current is None:
            continue
        if not line.strip():
            continue  # blank: hold, don't extend or close yet
        if line[:1] in (" ", "\t"):
            current["end_line"] = line_num  # indented continuation
        else:
            close(current["end_line"])  # unindented paragraph -> item already ended
    if current is not None:
        close(current["end_line"])
    return items


def scan_paragraphs(lines: list[str], body_start_line: int, body_end_line: int,
                     item_re: re.Pattern) -> list[dict]:
    """Yield one dict per blank-line-separated paragraph whose FIRST line
    matches *item_re*, inside ``[body_start_line, body_end_line]``
    (1-indexed, inclusive).

    Unlike ``scan_bullets`` there's no ``- `` marker to key off — plan.md's
    Technical Context fields are plain paragraphs (``**Language/Version**:
    ...``) separated by blank lines, not a list. A match only starts a new
    item when it opens a fresh paragraph (preceded by a blank line, or the
    very first line of the span); a line wrapped onto the next line with no
    blank in between extends the current item; a blank line followed by a
    paragraph that does NOT match *item_re* closes the current item without
    absorbing that unrelated paragraph.
    """
    items: list[dict] = []
    current: Optional[dict] = None
    prev_blank = True  # the span boundary itself counts as a paragraph break
    in_fence = False

    for idx in range(body_start_line - 1, body_end_line):
        line = lines[idx]
        line_num = idx + 1
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            if current is not None:
                current["end_line"] = line_num
            prev_blank = False
            continue
        if in_fence:
            if current is not None:
                current["end_line"] = line_num
            continue
        if not stripped:
            prev_blank = True
            continue
        m = item_re.match(line) if prev_blank else None
        if m:
            if current is not None:
                items.append(current)
            current = {"match": m, "start_line": line_num, "end_line": line_num}
        elif prev_blank:
            if current is not None:
                items.append(current)
                current = None
        elif current is not None:
            current["end_line"] = line_num  # same-paragraph wrapped line
        prev_blank = False

    if current is not None:
        items.append(current)
    return items
