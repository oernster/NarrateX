"""Hybrid TTS engine.

Motivation:

- When Coqui XTTS is available we want voice cloning for profiles that have
  reference audio.
- But we also want a functional "system voice" option (no reference audio)
  without forcing users to switch environments.

This engine delegates:

- to XTTS when `voice_profile.reference_audio_paths` is non-empty
- otherwise to pyttsx3
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.tts_engine import TTSEngine


@dataclass(frozen=True, slots=True)
class HybridTTSEngine(TTSEngine):
    xtts: TTSEngine
    pyttsx3: TTSEngine

    @property
    def engine_name(self) -> str:
        return f"Hybrid ({self.xtts.engine_name} + {self.pyttsx3.engine_name})"

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
        device: str,
        language: str,
    ) -> Path:
        if voice_profile.reference_audio_paths:
            return self.xtts.synthesize_to_file(
                text=text,
                voice_profile=voice_profile,
                output_path=output_path,
                device=device,
                language=language,
            )
        return self.pyttsx3.synthesize_to_file(
            text=text,
            voice_profile=voice_profile,
            output_path=output_path,
            device=device,
            language=language,
        )
