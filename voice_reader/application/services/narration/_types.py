from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.entities.text_chunk import TextChunk


@dataclass(frozen=True, slots=True)
class PlaybackCandidate:
    chunk: TextChunk
    speak_text: str
    speak_to_original: list[int]
    audio_path: Path
