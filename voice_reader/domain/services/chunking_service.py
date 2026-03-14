"""Domain service: ChunkingService.

Splits text into ~sentence-aware chunks suitable for TTS.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List

from voice_reader.domain.entities.text_chunk import TextChunk

_ABBREVIATIONS = {
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "sr.",
    "jr.",
    "st.",
    "vs.",
    "etc.",
    "e.g.",
    "i.e.",
    "u.s.",
    "u.k.",
}


@dataclass(frozen=True, slots=True)
class ChunkingService:
    min_chars: int = 150
    max_chars: int = 300

    def chunk_text(self, text: str) -> List[TextChunk]:
        normalized = self._normalize(text)
        paragraphs = [p for p in normalized.split("\n\n") if p.strip()]

        chunks: List[TextChunk] = []
        cursor = 0
        chunk_id = 0

        for para in paragraphs:
            para = para.strip()
            start_in_norm = normalized.find(para, cursor)
            # Defensive fallback: `para` comes from splitting `normalized`, so
            # this should not happen. Keep this guard anyway for resilience.
            if start_in_norm == -1:  # pragma: no cover
                start_in_norm = cursor

            for part, rel_start, rel_end in self._chunk_paragraph(para):
                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        text=part,
                        start_char=start_in_norm + rel_start,
                        end_char=start_in_norm + rel_end,
                    )
                )
                chunk_id += 1

            cursor = start_in_norm + len(para)

        return chunks

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[\t\u00A0]+", " ", text)
        text = re.sub(r"[ ]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _chunk_paragraph(self, para: str) -> Iterable[tuple[str, int, int]]:
        sentences = self._split_sentences(para)
        current = ""
        current_start = 0
        consumed = 0

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue

            if not current:
                current = sent
                current_start = consumed
            elif len(current) + 1 + len(sent) <= self.max_chars:
                current = f"{current} {sent}"
            else:
                if len(current) < self.min_chars and len(sent) > self.min_chars:
                    # BUGFIX: the previous logic dropped `current` entirely,
                    # causing audible sentence omissions.
                    yield current, current_start, current_start + len(current)
                    yield from self._hard_wrap(sent, consumed)
                    current = ""
                else:
                    yield current, current_start, current_start + len(current)
                    current = sent
                    current_start = consumed

            consumed += len(sent) + 1

        if current:
            if len(current) > self.max_chars:
                yield from self._hard_wrap(current, current_start)
            else:
                yield current, current_start, current_start + len(current)

    def _split_sentences(self, text: str) -> List[str]:
        # Conservative sentence splitting: split on .!? followed by whitespace.
        # Avoid splitting on common abbreviations.
        parts: List[str] = []
        start = 0
        for match in re.finditer(r"[.!?]+\s+", text):
            end = match.end()
            candidate = text[start:end].strip()
            if self._ends_with_abbreviation(candidate):
                continue
            parts.append(candidate)
            start = end
        tail = text[start:].strip()
        if tail:
            parts.append(tail)
        return parts

    @staticmethod
    def _ends_with_abbreviation(candidate: str) -> bool:
        lowered = candidate.lower().strip()
        for abbr in _ABBREVIATIONS:
            if lowered.endswith(abbr):
                return True
        return False

    def _hard_wrap(
        self, text: str, absolute_start: int
    ) -> Iterable[tuple[str, int, int]]:
        # Wrap on punctuation or spaces to keep within bounds.
        i = 0
        while i < len(text):
            end = min(i + self.max_chars, len(text))
            window = text[i:end]
            split_at = self._best_split(window)
            piece = window[:split_at].strip()
            if not piece:
                split_at = min(len(window), self.max_chars)
                piece = window[:split_at].strip()
            start = absolute_start + i
            yield piece, start - absolute_start, start - absolute_start + len(piece)
            i += split_at

    @staticmethod
    def _best_split(window: str) -> int:
        # Prefer last punctuation/space near the end.
        for pattern in [r"[,;:]\s+", r"\s+"]:
            matches = list(re.finditer(pattern, window))
            if matches:
                return matches[-1].end()
        return len(window)
