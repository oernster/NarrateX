"""Idea indexing v1 (local, deterministic, conservative).

This file is intentionally a thin façade:
- public functions are re-exported from smaller helpers under
  `voice_reader.application.services.idea_indexing.*`

Reason: structural guardrail requires every module to be <=400 LOC.
"""

from __future__ import annotations

from voice_reader.application.services.idea_indexing.concepts import (
    extract_top_concepts,
)
from voice_reader.application.services.idea_indexing.doc_builder_v1 import (
    build_idea_index_doc_v1,
    resolve_chunk_index as _resolve_chunk_index,
)
from voice_reader.application.services.idea_indexing.headings import detect_headings
from voice_reader.application.services.idea_indexing.labels import (
    expand_label_from_text as _expand_label_from_text,
)

# Public re-exports (import path stability)
__all__ = [
    "build_idea_index_doc_v1",
    "detect_headings",
    "extract_top_concepts",
    "_expand_label_from_text",
    "_resolve_chunk_index",
]
