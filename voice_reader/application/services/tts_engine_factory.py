"""Factory for choosing an available TTS engine.

Keeps app wiring simple while supporting optional heavy dependencies.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass

from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.infrastructure.tts.hybrid_engine import HybridTTSEngine
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

        # Prefer checking availability without importing heavy modules.
        try:
            has_tts = (
                "TTS" in sys.modules or importlib.util.find_spec("TTS") is not None
            )
        except Exception:
            has_tts = False

        # If XTTS is available, keep pyttsx3 as a functional fallback for the
        # special "system" voice (no reference audio).
        if has_tts:
            return HybridTTSEngine(
                xtts=XTTSCoquiEngine(model_name=self.model_name),
                pyttsx3=Pyttsx3Engine(),
            )
        return Pyttsx3Engine()
