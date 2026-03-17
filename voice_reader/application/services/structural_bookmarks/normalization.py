from __future__ import annotations

import re


def normalize_label_for_match(label: str) -> str:
    # Collapse whitespace and lowercase for matching/dedup.
    s = str(label or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_label_for_compare(label: str) -> str:
    return normalize_label_for_match(label).casefold()


def normalize_marker_line(line: str) -> str:
    """Normalization for front-matter marker detection.

    This is intentionally *slightly* more permissive than label matching:
    - collapses whitespace (same as labels)
    - strips common leading/trailing punctuation (e.g. "Table of Contents:")
    - treats hyphens/emdashes as spaces for matching marker phrases
    """

    s = normalize_label_for_match(line).casefold()
    if not s:
        return ""

    # Convert common separators to spaces then re-collapse.
    s = s.replace("-", " ").replace("–", " ").replace("—", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # Strip punctuation at the edges (but don't try to remove internal punctuation
    # beyond the separator replacements above).
    s = re.sub(r"^[\s\W_]+", "", s)
    s = re.sub(r"[\s\W_]+$", "", s)
    return s.strip()
