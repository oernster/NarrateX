from __future__ import annotations

from typing import Sequence
from voice_reader.application.services.structural_bookmarks.candidate_scan import (
    extract_heading_labels_from_text,
)
from voice_reader.application.services.structural_bookmarks.resolve_pipeline import (
    resolve_structural_bookmarks,
)
from voice_reader.application.services.structural_bookmarks.types import (
    RawHeadingCandidate,
)
from voice_reader.domain.document.model import Document
from voice_reader.domain.document.reading_start import (
    body_opening_offset,
    contents_end_offset,
)
from voice_reader.domain.entities.structural_bookmark import StructuralBookmark
from voice_reader.domain.entities.text_chunk import TextChunk


class StructuralBookmarkService:
    """Build deterministic section landmarks for a loaded book."""

    def build_for_loaded_book(
        self,
        *,
        book_id: str,
        normalized_text: str,
        document: Document,
        chapter_candidates: list[object] | None = None,
        chunks: Sequence[TextChunk] | None = None,
        min_char_offset: int | None = None,
    ) -> list[StructuralBookmark]:
        """Resolve section landmarks, bounded by where the body begins.

        The boundaries come from the document model, which is the same answer
        narration and the reading pane use. They were previously re-derived here
        by scanning the text, which gave the book two answers to one question
        and needed reconciling whenever they disagreed.
        """

        del book_id  # reserved for future caching/telemetry

        text = str(normalized_text or "")
        if not text:
            return []

        # The model places the body opening at or after the contents, so a
        # single boundary serves both: anchors never resolve inside the
        # contents, and the opening heading itself stays reachable.
        body_start_offset = body_opening_offset(document)
        toc_end_offset = contents_end_offset(document) or None
        front_matter_present = body_start_offset > 0

        prefer_min_offset = body_start_offset
        if min_char_offset is not None:
            try:
                prefer_min_offset = max(prefer_min_offset, int(min_char_offset))
            except Exception:
                # Defensive: treat invalid min_char_offset as unset.
                pass

        min_anchor_offset = body_start_offset

        raw: list[RawHeadingCandidate] = []
        if chapter_candidates:
            raw.extend(self._adapt_chapter_like_candidates(chapter_candidates))

        # Text candidates are used only to discover labels. Anchors are resolved
        # via exact-full-line occurrences with body-aware scoring.
        text_labels = extract_heading_labels_from_text(normalized_text=text)
        raw.extend(
            [
                RawHeadingCandidate(
                    label=lab,
                    char_offset=None,
                    chunk_index=None,
                    source="text_scan",
                )
                for lab in text_labels
            ]
        )

        return resolve_structural_bookmarks(
            text=text,
            raw_candidates=raw,
            chunks=chunks,
            min_char_offset=min_char_offset,
            body_start_offset=int(body_start_offset),
            front_matter_present=bool(front_matter_present),
            toc_end_offset=(
                int(toc_end_offset) if toc_end_offset is not None else None
            ),
            prefer_min_offset=int(prefer_min_offset),
            min_anchor_offset=int(min_anchor_offset),
        )

    @staticmethod
    def _adapt_chapter_like_candidates(
        chapters: Sequence[object],
    ) -> list[RawHeadingCandidate]:
        out: list[RawHeadingCandidate] = []
        for ch in chapters:
            # Support existing Chapter entity (title/char_offset/chunk_index)
            label = getattr(ch, "title", None) or getattr(ch, "label", None)
            if not label:
                continue
            char_offset = getattr(ch, "char_offset", None)
            chunk_index = getattr(ch, "chunk_index", None)
            try:
                char_offset_i = int(char_offset) if char_offset is not None else None
            except Exception:
                char_offset_i = None
            try:
                chunk_index_i = int(chunk_index) if chunk_index is not None else None
            except Exception:
                chunk_index_i = None
            out.append(
                RawHeadingCandidate(
                    label=str(label),
                    char_offset=char_offset_i,
                    chunk_index=chunk_index_i,
                    source="chapter_parser",
                )
            )
        return out
