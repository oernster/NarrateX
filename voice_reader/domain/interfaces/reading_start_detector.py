"""Domain interface: reading start detection.

This port allows the application layer to customize where narration begins
without coupling to a concrete heuristic implementation.
"""

from __future__ import annotations

from typing import Protocol

from voice_reader.domain.services.reading_start_service import ReadingStart


class ReadingStartDetector(Protocol):
    def detect_start(self, text: str) -> ReadingStart: ...
