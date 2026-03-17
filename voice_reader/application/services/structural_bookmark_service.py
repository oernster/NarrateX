"""Application service: build deterministic structural bookmarks.

This module is a thin façade that re-exports the stable API from
`voice_reader.application.services.structural_bookmarks.*`.

Reason: structural guardrail requires every module to be <=400 LOC.
"""

from __future__ import annotations

# Public re-exports (import path stability)
from voice_reader.application.services.structural_bookmarks.classification import (
    classify_heading,
)
from voice_reader.application.services.structural_bookmarks.dedupe import (
    dedupe_candidates,
)
from voice_reader.application.services.structural_bookmarks.front_matter import (
    detect_body_start_offset,
    detect_toc_end_offset,
)
from voice_reader.application.services.structural_bookmarks.text_scan import (
    scan_structural_headings,
)
from voice_reader.application.services.structural_bookmarks.types import (
    RawHeadingCandidate,
)
from voice_reader.application.services.structural_bookmarks.service import (
    StructuralBookmarkService,
)

# Public re-exports (import path stability)
__all__ = [
    "RawHeadingCandidate",
    "StructuralBookmarkService",
    "classify_heading",
    "dedupe_candidates",
    "detect_body_start_offset",
    "detect_toc_end_offset",
    "scan_structural_headings",
]


def _touch_exports_for_coverage() -> None:  # pragma: no cover
    """Touch re-exports so flake8 doesn't treat facade imports as unused."""

    _ = (
        RawHeadingCandidate,
        StructuralBookmarkService,
        classify_heading,
        dedupe_candidates,
        detect_body_start_offset,
        detect_toc_end_offset,
        scan_structural_headings,
    )
