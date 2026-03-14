"""Application service: deterministic chapter indexing.

This service detects simple chapter headings using a strict regex and maps them
to NarrationService-compatible navigation anchors:

- char_offset: absolute character offset into the book text
- chunk_index: absolute playback index into the narration *candidate list*

The candidate list matches NarrationService playback semantics by skipping
chunks whose sanitized speak_text is empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from voice_reader.domain.entities.chapter import Chapter
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.services.sanitized_text_mapper import SanitizedTextMapper


@dataclass(frozen=True, slots=True)
class ChapterIndexService:
    """Build and query an in-memory chapter index."""

    text_mapper: SanitizedTextMapper = SanitizedTextMapper()

    # Heading rules:
    # - must start at beginning of line (after whitespace)
    # - must contain the word 'chapter'
    # - must contain either arabic numerals or roman numerals
    _chapter_heading_re: re.Pattern[str] = re.compile(
        r"(?im)^[ \t]*chapter\b[ \t]+(?P<num>\d+|[ivxlcdm]+)\b.*$",
        re.IGNORECASE | re.MULTILINE,
    )

    def build_index(
        self,
        book_text: str,
        *,
        chunks: Sequence[TextChunk],
        min_char_offset: int | None = None,
    ) -> list[Chapter]:
        """Detect headings and map them to playback coordinates.

        Args:
            book_text: Full normalized book text.
            chunks: Prepared chunks in absolute book coordinates (typically from
                NarrationService.prepare()).
            min_char_offset: If provided, drop chapters whose resolved jump
                target starts before this offset.

        Returns:
            An ordered list of Chapter objects.
        """

        candidates = list(self._playback_candidates(chunks))
        if not candidates:
            return []

        # Resolve a match offset to a candidate playback index.
        def resolve_chunk_index(char_offset: int) -> int | None:
            # Prefer a containing chunk; otherwise choose the first chunk starting
            # at or after the offset.
            for idx, c in enumerate(candidates):
                if int(c.start_char) <= int(char_offset) < int(c.end_char):
                    return idx
                if int(c.start_char) >= int(char_offset):
                    return idx
            return None

        detected: list[Chapter] = []
        for m in self._chapter_heading_re.finditer(book_text):
            start = int(m.start())
            title = self._line_text_at(book_text, start)
            chunk_index = resolve_chunk_index(start)
            if chunk_index is None:
                continue
            if min_char_offset is not None:
                # More precise deterministic filter: keep headings whose playback
                # jump target intersects or follows the narration start region.
                # This retains Chapter 1 even when narration start offset is
                # computed *after* the heading line.
                try:
                    if int(candidates[int(chunk_index)].end_char) < int(min_char_offset):
                        continue
                except Exception:
                    continue
            detected.append(
                Chapter(title=title, char_offset=start, chunk_index=int(chunk_index))
            )

        if not detected:
            return []

        # Preserve original text order.
        detected.sort(key=lambda c: int(c.char_offset))
        return detected

    def get_current_chapter(
        self, chapters: Sequence[Chapter], *, current_char_offset: int
    ) -> Chapter | None:
        idx = self._current_index(chapters, current_char_offset=current_char_offset)
        return None if idx < 0 else chapters[int(idx)]

    def get_previous_chapter(
        self, chapters: Sequence[Chapter], *, current_char_offset: int
    ) -> Chapter | None:
        idx = self._current_index(chapters, current_char_offset=current_char_offset)
        if idx <= 0:
            return None
        return chapters[int(idx) - 1]

    def get_next_chapter(
        self, chapters: Sequence[Chapter], *, current_char_offset: int
    ) -> Chapter | None:
        if not chapters:
            return None
        idx = self._current_index(chapters, current_char_offset=current_char_offset)
        if idx < 0:
            return chapters[0]
        if idx >= (len(chapters) - 1):
            return None
        return chapters[int(idx) + 1]

    @staticmethod
    def _current_index(chapters: Sequence[Chapter], *, current_char_offset: int) -> int:
        """Return the index of the current chapter, or -1 if before the first."""

        if not chapters:
            return -1
        cur_idx = -1
        for i, ch in enumerate(chapters):
            if int(ch.char_offset) <= int(current_char_offset):
                cur_idx = int(i)
            else:
                break
        return int(cur_idx)

    def _playback_candidates(self, chunks: Sequence[TextChunk]) -> Iterable[TextChunk]:
        """Yield chunks that would be narratable playback candidates."""

        for c in chunks:
            mapped = self.text_mapper.sanitize_with_mapping(original_text=c.text)
            if mapped.speak_text:
                yield c

    @staticmethod
    def _line_text_at(text: str, idx: int) -> str:
        if idx < 0:
            idx = 0
        if idx > len(text):
            idx = len(text)
        line_start = text.rfind("\n", 0, idx)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1
        line_end = text.find("\n", idx)
        if line_end == -1:
            line_end = len(text)
        return text[line_start:line_end].strip()

