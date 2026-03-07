"""Hybrid TTS engine.

Motivation:

- When Coqui XTTS is available we want voice cloning for profiles that have
  reference audio.
- But we also want a functional "system voice" option (no reference audio)
  without forcing users to switch environments.

This engine delegates:

- to the cloning engine when `voice_profile.reference_audio_paths` is non-empty
- otherwise to the native engine (e.g. Kokoro)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.tts_engine import TTSEngine


@dataclass(frozen=True, slots=True)
class HybridTTSEngine(TTSEngine):
    cloning_engine: TTSEngine
    native_engine: TTSEngine

    @property
    def engine_name(self) -> str:
        return (
            f"Hybrid ({self.cloning_engine.engine_name} + {self.native_engine.engine_name})"
        )

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
            return self.cloning_engine.synthesize_to_file(
                text=text,
                voice_profile=voice_profile,
                output_path=output_path,
                device=device,
                language=language,
            )
        return self.native_engine.synthesize_to_file(
            text=text,
            voice_profile=voice_profile,
            output_path=output_path,
            device=device,
            language=language,
        )
