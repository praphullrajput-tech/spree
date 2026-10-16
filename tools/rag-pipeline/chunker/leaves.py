"""Embedding-eligibility ("leaf") detection.

A chunk is embedding-eligible iff no other chunk in its file names it as a
parent — i.e. it has no children. This is independent of ``chunk_type``:

- Most ``child`` chunks are leaves by construction (a template rule never
  gives its own items further children).
- A ``parent`` (heading) chunk that turned out to have no sub-heading and no
  template-rule children — plan.md's "Summary", spec.md's "Edge Cases" — is
  ALSO a leaf and must be embedded, since nothing else represents its text.
- Conversely a ``parent`` chunk that DOES have children ("Technical
  Context", "Constitution Check", "Project Structure") is excluded from
  embedding: its content is already covered by its children. It stays in
  the collection (see Phase 2 schema) purely for parent-expansion context
  at answer time, never as a search target itself.

``chunk_type == "child"`` was the wrong proxy for this and has been dropped
in favor of computing it directly from the parent/child links every chunk
already carries.
"""
from __future__ import annotations


def leaf_ids(chunks: list[dict]) -> set[str]:
    """The chunk_ids in *chunks* (one file's tree) that have no children."""
    has_children = {c["parent_chunk_id"] for c in chunks if c["parent_chunk_id"]}
    return {c["chunk_id"] for c in chunks} - has_children


def leaves(chunks: list[dict]) -> list[dict]:
    """The subset of *chunks* that are embedding-eligible."""
    eligible = leaf_ids(chunks)
    return [c for c in chunks if c["chunk_id"] in eligible]
