"""Application service: build navigation chunks for a loaded book."""

from __future__ import annotations

import re
from dataclasses import dataclass

from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.interfaces.reading_start_detector import ReadingStartDetector
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.services.reading_start_service import ReadingStart

from voice_reader.application.text_patterns import contains_dotted_leader, normalize_dotlikes


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

        s = normalize_dotlikes(line).strip()
        if not s:
            return True

        # Dotted leaders / page numbers.
        if contains_dotted_leader(s) and re.search(r"\s*(\d+|[ivxlcdm]+)\s*$", s, re.I):
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
            # Defensive: reading start detectors should never return negative.
            # Clamp to preserve slicing semantics.
            if slice_start < 0:
                slice_start = 0
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
        - end: the beginning of the first *clean structural heading* following it.

        Rationale:
        - The Essay Index block often contains ToC-like list entries, including
          "Chapter 1 .... 1" or "Introduction .... v" which must be treated as
          part of the index list (not as terminators).
        - Some books include an Introduction section after the Essay Index.
          We must not skip that; therefore we end the span at Introduction (or
          any other structural heading), not always at Chapter 1.

        This is used only to *filter* chunks; it must not mutate the text buffer
        or adjust offsets.
        """

        essay = re.search(r"(?im)^\s*essay index\s*$", slice_text)
        if not essay:
            return None

        tail = slice_text[essay.end() :]

        def looks_like_toc_entry(line: str) -> bool:
            s = normalize_dotlikes(str(line or "")).strip()
            if not s:
                return False

            # Dotted leaders (with or without explicit page numbers).
            if contains_dotted_leader(s):
                return True

            # Trailing page number / roman numeral.
            if re.match(r"^.+\s+(\d+|[ivxlcdm]+)\s*$", s, re.I):
                if len(s) <= 120:
                    return True

            return False

        def looks_like_clean_structural_heading(line: str) -> bool:
            """True for headings that should end the Essay Index span."""

            s = normalize_dotlikes(str(line or "")).strip()
            if not s:
                return False

            # Never treat dotted-leader lines as body headings.
            # Example false positives we must reject:
            # - "Chapter 1 .... 1"
            # - "Introduction .... v"
            if contains_dotted_leader(s):
                return False

            # Allow outline numbering prefixes like "3" or "3.1".
            prefix = r"(?:\d+(?:\.\d+)*)?"
            # Keep this intentionally narrow; it's used only to terminate
            # skipping behavior.
            patterns = [
                rf"(?im)^\s*{prefix}\s*(introduction|intro|about this book)\s*$",
                rf"(?im)^\s*{prefix}\s*(prologue)\s*$",
                (
                    rf"(?im)^\s*{prefix}\s*"
                    rf"(foreword|preface|acknowledgements?|acknowledgments)\s*$"
                ),
                rf"(?im)^\s*{prefix}\s*(afterword|epilogue|conclusion)\s*$",
                rf"(?im)^\s*{prefix}\s*appendix\b.*$",
                # Chapters/parts (support subtitles), reject dotted leaders above.
                (
                    rf"(?im)^\s*{prefix}\s*chapter\s+[0-9ivxlcdm]+\b"
                    rf"(?:\s*[.:\-–—]\s*\S.+)?\s*$"
                ),
                rf"(?im)^\s*{prefix}\s*ch\.\s*[0-9ivxlcdm]+\b.*$",
                (
                    rf"(?im)^\s*{prefix}\s*part\s+[ivxlcdm0-9]+\b"
                    rf"(?:\s*[.:\-–—]\s*\S.+)?\s*$"
                ),
            ]

            # If a line is a clean structural heading, accept it even if it
            # resembles a "title + roman numeral" TOC entry (e.g. "CHAPTER I").
            return any(re.match(pat, s) for pat in patterns)

        # Find the earliest clean structural heading after the Essay Index line.
        # This ensures we don't accidentally skip an Introduction section that
        # appears between the index and Chapter 1.
        offset = int(essay.end())
        for raw_line in tail.splitlines(keepends=True):
            line_start = int(offset)
            offset += len(raw_line)
            stripped = raw_line.strip()

            if looks_like_clean_structural_heading(stripped):
                return int(essay.start()), int(line_start)

            # Ignore ToC/index-like list entries.
            if looks_like_toc_entry(stripped):
                continue

            if not stripped:
                continue

        return None
