"""Application service: build navigation chunks for a loaded book."""

from __future__ import annotations

import re
from dataclasses import dataclass

from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.interfaces.reading_start_detector import ReadingStartDetector
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.services.reading_start_service import ReadingStart


@dataclass(frozen=True, slots=True)
class NavigationChunkService:
    reading_start_detector: ReadingStartDetector
    chunking_service: ChunkingService

    @staticmethod
    def _looks_like_essay_index_line(line: str) -> bool:
        """Heuristic: decide whether a line is part of an Essay Index list.

        This is intentionally conservative: it should match title-like / TOC-like
        index entries, but avoid consuming real prose.
        """

        s = line.strip()
        if not s:
            return True

        # Dotted leaders / page numbers.
        if re.search(r"\.{2,}\s*(\d+|[ivxlcdm]+)\s*$", s, re.I):
            return True

        # Outline-ish numbering like "3" or "3.1".
        if re.match(r"^\d+(?:\.\d+)*$", s):
            return True

        # Very short title lines (non-sentences).
        if len(s.split()) <= 6 and not re.search(r"[.!?]\s*$", s):
            return True

        # ALL CAPS headings inside the list.
        if not any(ch.islower() for ch in s) and len(s.split()) <= 8:
            return True

        return False

    def build_chunks(
        self,
        *,
        book_text: str,
        force_start_char: int | None = None,
        skip_essay_index: bool = True,
    ) -> tuple[list[TextChunk], ReadingStart]:
        """Return (chunks, reading_start) in absolute book coordinates."""

        if force_start_char is not None:
            slice_start = max(0, int(force_start_char))
            start = ReadingStart(
                start_char=slice_start,
                reason="Forced start",
            )
        else:
            start = self.reading_start_detector.detect_start(book_text)
            slice_start = int(start.start_char)
        slice_text = book_text[slice_start:]

        # IMPORTANT: never remove/alter text before chunking.
        # Chunk offsets must remain in the same coordinate system as `book_text`.
        sliced_chunks = self.chunking_service.chunk_text(slice_text)

        chunks = [
            TextChunk(
                chunk_id=c.chunk_id,
                text=c.text,
                start_char=int(c.start_char) + slice_start,
                end_char=int(c.end_char) + slice_start,
            )
            for c in sliced_chunks
        ]

        # If present, exclude chunks fully contained in the Essay Index block.
        # This preserves original offsets (we are only filtering the candidate list).
        if skip_essay_index:
            essay_span = self._detect_essay_index_span(slice_text=slice_text)
            if essay_span is not None:
                span_start, span_end = essay_span
                abs_start = slice_start + int(span_start)
                abs_end = slice_start + int(span_end)
                filtered = [
                    c
                    for c in chunks
                    if not (
                        int(c.start_char) >= abs_start and int(c.end_char) <= abs_end
                    )
                ]
                # Safety: never return an empty list (would stall playback).
                # Filtering is still important; retain unfiltered list if we'd drop all.
                if filtered:
                    chunks = filtered
                else:  # pragma: no cover
                    chunks = chunks
            else:
                # No Essay Index detected: keep chunks unchanged.
                chunks = chunks

        return chunks, start

    @staticmethod
    def _detect_essay_index_span(*, slice_text: str) -> tuple[int, int] | None:
        """Return (start, end) span of the Essay Index block in slice coordinates.

        The span is defined as:
        - start: the beginning of the line matching "Essay Index" (case-insensitive)
        - end: the beginning of the first real Chapter-1 heading following it

        This is used only to *filter* chunks; it must not mutate the text buffer
        or adjust offsets.
        """

        essay = re.search(r"(?im)^\s*essay index\s*$", slice_text)
        if not essay:
            return None

        tail = slice_text[essay.end() :]

        # HARD REQUIREMENT: skip from "Essay Index" up to the first real Chapter 1
        # heading, so narration/highlighting jumps Prologue -> Chapter 1.
        #
        # Support numeric prefixes like "3.1 Chapter 1: ..." and roman numeral
        # variants "CHAPTER I". Reject dotted-leader TOC/index lines.
        chapter_heading_patterns = [
            r"(?im)^\s*(?:\d+(?:\.\d+)*)?\s*chapter\s+(?:1|i)\b(?!.*\.{2,}).*$",
            r"(?im)^\s*ch\.\s*1\b(?!.*\.{2,}).*$",
        ]

        chapter_pos: int | None = None
        for pat in chapter_heading_patterns:
            m = re.search(pat, tail)
            if not m:
                continue
            pos = int(essay.end()) + int(m.start())
            if chapter_pos is None or pos < chapter_pos:
                chapter_pos = pos

        if chapter_pos is None or chapter_pos <= int(essay.end()):
            return None

        return int(essay.start()), int(chapter_pos)
