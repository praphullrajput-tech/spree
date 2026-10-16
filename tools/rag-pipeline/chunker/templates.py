"""File-type-specific child-chunk rules.

Each function below knows exactly one thing: which heading a file type's
numbered/labeled items live under, and what an item line looks like. All of
them delegate line-range and continuation-line handling to
``engine.scan_bullets`` — that logic is generic and lives in one place.

If a file's structure changes (e.g. tasks.md stops using `T###` ids), only
the relevant function here needs to change; engine.py is untouched.
"""
from __future__ import annotations

import re

from .engine import Chunk, Heading, scan_bullets, scan_paragraphs
from .ids import slug

_FR_ITEM_RE = re.compile(r"^-\s+\*\*(FR-\d+)\*\*:?\s*(.*)$")
_TASK_ITEM_RE = re.compile(r"^-\s+\[([ xX])\]\s+(T\d+)\b\s*(.*)$")
_PRINCIPLE_ITEM_RE = re.compile(r"^-\s+\*\*([IVXLC]+)\.\s+([^*]+)\*\*:?\s*(.*)$")
_LABELED_BULLET_RE = re.compile(r"^-\s+\*\*([^*]+)\*\*:?\s*(.*)$")
# Technical Context fields are bold-label PARAGRAPHS, not bullets:
# "**Language/Version**: Ruby..." with no leading "- ".
_LABELED_PARAGRAPH_RE = re.compile(r"^\*\*([^*]+)\*\*:?\s*(.*)$")


def _headings_matching(headings: list[Heading], title_pattern: str) -> list[Heading]:
    rx = re.compile(title_pattern, re.IGNORECASE)
    return [h for h in headings if rx.search(h.title)]


def _child_chunk(lines: list[str], heading: Heading, file_path: str,
                  item_id: str, breadcrumb_label: str,
                  start_line: int, end_line: int, extra: dict) -> Chunk:
    text = "\n".join(lines[start_line - 1:end_line])
    return Chunk(
        chunk_id=f"{heading.chunk_id}__{item_id}",
        file_path=file_path,
        heading_path=f"{heading.heading_path} > {breadcrumb_label}",
        start_line=start_line, end_line=end_line, chunk_type="child",
        parent_chunk_id=heading.chunk_id, raw_text=text, extra=extra,
    )


def spec_children(lines: list[str], headings: list[Heading], file_path: str) -> list[Chunk]:
    """spec.md: one child per ``- **FR-XXX**: ...`` under "Functional Requirements"."""
    out = []
    for h in _headings_matching(headings, r"functional requirements"):
        for item in scan_bullets(lines, h.start_line + 1, h.body_end_line, _FR_ITEM_RE):
            req_id, desc = item["match"].group(1), item["match"].group(2)
            out.append(_child_chunk(
                lines, h, file_path, req_id.lower().replace("-", "_"), req_id,
                item["start_line"], item["end_line"],
                {"item_id": req_id, "item_kind": "functional_requirement"},
            ))
    return out


def tasks_children(lines: list[str], headings: list[Heading], file_path: str) -> list[Chunk]:
    """tasks.md: one child per ``- [x] T### ...`` line, under whatever "## Component: ..."
    (or other) heading it physically sits under — no heading-title filter needed,
    since the ``T\\d+`` id format doesn't appear anywhere else in this file type."""
    out = []
    for h in headings:
        for item in scan_bullets(lines, h.start_line + 1, h.body_end_line, _TASK_ITEM_RE):
            checked, task_id, desc = item["match"].groups()
            out.append(_child_chunk(
                lines, h, file_path, task_id.lower(), task_id,
                item["start_line"], item["end_line"],
                {"item_id": task_id, "item_kind": "task",
                 "done": checked.strip().lower() == "x"},
            ))
    return out


def plan_children(lines: list[str], headings: list[Heading], file_path: str) -> list[Chunk]:
    """plan.md: one child per ``- **I. Principle Name**: ...`` under "Constitution Check",
    plus one child per ``**Field**: ...`` paragraph under "Technical Context"."""
    out = []
    for h in _headings_matching(headings, r"constitution check"):
        for item in scan_bullets(lines, h.start_line + 1, h.body_end_line, _PRINCIPLE_ITEM_RE):
            numeral, name, desc = item["match"].groups()
            label = f"{numeral}. {name.strip()}"
            out.append(_child_chunk(
                lines, h, file_path, f"principle_{numeral.lower()}", label,
                item["start_line"], item["end_line"],
                {"item_id": numeral, "item_kind": "constitution_check_principle"},
            ))
    for h in _headings_matching(headings, r"technical context"):
        for item in scan_paragraphs(lines, h.start_line + 1, h.body_end_line, _LABELED_PARAGRAPH_RE):
            label, desc = item["match"].groups()
            label = label.strip()
            out.append(_child_chunk(
                lines, h, file_path, f"field_{slug(label)}", label,
                item["start_line"], item["end_line"],
                {"item_id": label, "item_kind": "technical_context_field"},
            ))
    return out


def constitution_children(lines: list[str], headings: list[Heading], file_path: str) -> list[Chunk]:
    """constitution.md: Core Principles are already H3 headings (the generic
    engine covers those as parent chunks on its own). The one place this file
    still needs a child rule is "## Quality Gates", whose bullets are
    ``- **Category**: ...`` labeled items, not numbered principles."""
    out = []
    for h in _headings_matching(headings, r"quality gates"):
        for item in scan_bullets(lines, h.start_line + 1, h.body_end_line, _LABELED_BULLET_RE):
            label, desc = item["match"].groups()
            label = label.strip()
            out.append(_child_chunk(
                lines, h, file_path, f"quality_gate_{slug(label)}", label,
                item["start_line"], item["end_line"],
                {"item_id": label, "item_kind": "quality_gate"},
            ))
    return out


# file basename -> its child-chunk rule. `chunk_docs.py` dispatches on this.
TEMPLATES = {
    "spec.md": spec_children,
    "tasks.md": tasks_children,
    "plan.md": plan_children,
    "constitution.md": constitution_children,
}
