"""Fallback offline TTS engine using pyttsx3.

This is a CPU-only, local engine that works on Windows without ML dependencies.
It does **not** perform voice cloning; it is intended as a functional fallback
when Coqui XTTS cannot be installed (e.g., Python 3.13).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.shared.errors import TTSError


@dataclass
class Pyttsx3Engine(TTSEngine):
    voice_rate_wpm: int = 170

    def __post_init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)

    @property
    def engine_name(self) -> str:
        return "pyttsx3 (fallback)"

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
        device: str,
        language: str,
    ) -> Path:
        del device, language
        try:
            import pyttsx3

            output_path.parent.mkdir(parents=True, exist_ok=True)
            engine = pyttsx3.init()
            engine.setProperty("rate", int(self.voice_rate_wpm))

            # Best-effort: choose a system voice by name match.
            desired = voice_profile.name.lower()
            for v in engine.getProperty("voices"):
                name = getattr(v, "name", "")
                if desired and desired in str(name).lower():
                    engine.setProperty("voice", v.id)
                    break

            # NOTE: pyttsx3 writes through SAPI5; wav output is supported.
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
            return output_path
        except Exception as exc:  # pragma: no cover
            self._log.exception("pyttsx3 synthesis failed")
            raise TTSError(str(exc)) from exc
