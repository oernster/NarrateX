"""Kokoro voice profile repository.

This project is Kokoro-only and intentionally does not support voice cloning.
The available voices are the built-in Kokoro voice IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.voice_profile_repository import (
    VoiceProfileRepository,
)


@dataclass(frozen=True, slots=True)
class KokoroVoiceProfileRepository(VoiceProfileRepository):
    def list_profiles(self) -> Sequence[VoiceProfile]:
        return [VoiceProfile(name=v, reference_audio_paths=[]) for v in self._voice_ids()]

    @staticmethod
    def _voice_ids() -> Sequence[str]:
        # Keep in sync with documentation/examples. Kokoro voice IDs are stable
        # and do not require reference audio.
        return (
            # British
            "bf_emma",
            "bf_isabella",
            "bf_lily",
            "bm_daniel",
            "bm_fable",
            "bm_george",
            "bm_lewis",
            # American
            "af_heart",
            "af_bella",
            "af_nicole",
            "af_sarah",
            "am_adam",
            "am_michael",
        )
