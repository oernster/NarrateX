"""Factory for choosing an available TTS engine.

Keeps app wiring simple while supporting optional heavy dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.infrastructure.tts.pyttsx3_engine import Pyttsx3Engine
from voice_reader.infrastructure.tts.xtts_engine import XTTSCoquiEngine


@dataclass(frozen=True, slots=True)
class TTSEngineFactory:
    model_name: str

    def create(self) -> TTSEngine:
        """Create best available engine.

        Preference order:
        1) Coqui XTTS (voice cloning) when `TTS` is importable.
        2) pyttsx3 fallback when not.
        """

        try:
            import TTS  # noqa: F401

            return XTTSCoquiEngine(model_name=self.model_name)
        except Exception:
            return Pyttsx3Engine()
