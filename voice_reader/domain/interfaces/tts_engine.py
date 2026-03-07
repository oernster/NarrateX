"""Domain interface: Text-to-speech engine."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from voice_reader.domain.entities.voice_profile import VoiceProfile


class TTSEngine(Protocol):
    @property
    def engine_name(self) -> str:  # pragma: no cover
        ...

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
        device: str,
        language: str,
    ) -> Path:
        """Synthesize speech to a WAV file and return the output path."""
