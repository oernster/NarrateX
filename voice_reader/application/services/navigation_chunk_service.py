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

    def build_chunks(self, *, book_text: str) -> tuple[list[TextChunk], ReadingStart]:
        """Return (chunks, reading_start) in absolute book coordinates."""

        start = self.reading_start_detector.detect_start(book_text)

        slice_start = int(start.start_char)
        slice_text = book_text[slice_start:]

        # Remove Essay Index block BEFORE chunking
        cleaned_slice = self._remove_essay_index(slice_text)

        sliced_chunks = self.chunking_service.chunk_text(cleaned_slice)

        chunks = [
            TextChunk(
                chunk_id=c.chunk_id,
                text=c.text,
                start_char=int(c.start_char) + slice_start,
                end_char=int(c.end_char) + slice_start,
            )
            for c in sliced_chunks
        ]

        return chunks, start

    @staticmethod
    def _remove_essay_index(text: str) -> str:
        """
        Remove Essay Index section if present.

        Structure typically looks like:

        Essay Index
        ...
        Chapter 1
        """

        essay = re.search(r"(?im)^\s*essay index\s*$", text)
        if not essay:
            return text

        chapter_patterns = [
            r"(?im)^\s*chapter\s+1\b",
            r"(?im)^\s*chapter\s+i\b",
            r"(?im)^\s*ch\.\s*1\b",
        ]

        chapter_pos = None
        tail = text[essay.end():]

        for pat in chapter_patterns:
            m = re.search(pat, tail)
            if m:
                pos = essay.end() + m.start()
                if chapter_pos is None or pos < chapter_pos:
                    chapter_pos = pos

        if chapter_pos is None:
            return text

        # Keep everything before Essay Index and everything from Chapter 1 onward
        return text[:essay.start()] + text[chapter_pos:]