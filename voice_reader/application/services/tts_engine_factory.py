"""Factory for choosing an available TTS engine.

Keeps app wiring simple while supporting optional heavy dependencies.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.infrastructure.tts.hybrid_engine import HybridTTSEngine
from voice_reader.infrastructure.tts.kokoro_engine import KokoroEngine
from voice_reader.infrastructure.tts.pyttsx3_engine import Pyttsx3Engine
from voice_reader.infrastructure.tts.xtts_engine import XTTSCoquiEngine


@dataclass(frozen=True, slots=True)
class TTSEngineFactory:
    model_name: str

    def create(self) -> TTSEngine:
        """Create best available engine.

        Preference order:
        1) Kokoro native voices when `kokoro` is importable.
        2) Coqui XTTS (voice cloning) when `TTS` is importable.
        3) pyttsx3 fallback.
        """

        def _has_module(name: str) -> bool:
            try:
                return importlib.util.find_spec(name) is not None
            except Exception:
                return False

        has_kokoro = _has_module("kokoro")
        has_tts = _has_module("TTS")

        if has_kokoro and has_tts:
            return HybridTTSEngine(
                cloning_engine=XTTSCoquiEngine(model_name=self.model_name),
                native_engine=KokoroEngine(),
            )
        if has_kokoro:
            return KokoroEngine()
        if has_tts:
            return HybridTTSEngine(
                cloning_engine=XTTSCoquiEngine(model_name=self.model_name),
                native_engine=Pyttsx3Engine(),
            )
        return Pyttsx3Engine()
