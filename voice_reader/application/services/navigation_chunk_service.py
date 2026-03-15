"""Application service: build navigation chunks for a loaded book.

This is a small extraction of the chunking logic used by
[`NarrationService.prepare()`](voice_reader/application/services/narration_service.py:200)
so other UI features (e.g. chapter navigation) can compute stable chunk mappings
without starting playback.
"""

from __future__ import annotations

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
        slice_text = book_text[int(start.start_char) :]
        sliced_chunks = self.chunking_service.chunk_text(slice_text)
        chunks = [
            TextChunk(
                chunk_id=c.chunk_id,
                text=c.text,
                start_char=int(c.start_char) + int(start.start_char),
                end_char=int(c.end_char) + int(start.start_char),
            )
            for c in sliced_chunks
        ]
        return chunks, start
