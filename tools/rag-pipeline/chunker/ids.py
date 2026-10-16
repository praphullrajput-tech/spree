"""Deterministic id/slug helpers shared by the engine and the templates."""
from __future__ import annotations

import re
from pathlib import Path

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def slug(text: str, max_len: int = 60) -> str:
    """Lowercase, ``[a-z0-9]``-only slug. Stable across runs on the same text."""
    s = _NON_ALNUM_RE.sub("_", text.lower()).strip("_")
    if len(s) > max_len:
        s = s[:max_len].rstrip("_")
    return s or "x"


def file_id(relpath: Path) -> str:
    """Full repo-relative path with the extension dropped, flattened to one slug.

    e.g. ``specs/001-cart-and-checkout/tasks.md`` -> ``specs_001_cart_and_checkout_tasks``.
    Keeping every path segment (not just the basename) is what keeps
    ``specs/001-.../spec.md`` and ``specs/002-.../spec.md`` from colliding.
    """
    return slug(str(relpath.with_suffix("")).replace("\\", "/"))
