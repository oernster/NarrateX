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
        return [
            VoiceProfile(name=v, reference_audio_paths=[]) for v in self._voice_ids()
        ]

    @staticmethod
    def _voice_ids() -> Sequence[str]:
        # The complete Kokoro English inventory. Kokoro voice IDs are stable
        # and do not require reference audio. Kokoro ships no other English
        # regions (no Australian, New Zealand or Canadian voices exist), so
        # the picker's region list is exactly these two.
        return (
            # British female
            "bf_alice",
            "bf_emma",
            "bf_isabella",
            "bf_lily",
            # British male
            "bm_daniel",
            "bm_fable",
            "bm_george",
            "bm_lewis",
            # American female
            "af_alloy",
            "af_aoede",
            "af_bella",
            "af_heart",
            "af_jessica",
            "af_kore",
            "af_nicole",
            "af_nova",
            "af_river",
            "af_sarah",
            "af_sky",
            # American male
            "am_adam",
            "am_echo",
            "am_eric",
            "am_fenrir",
            "am_liam",
            "am_michael",
            "am_onyx",
            "am_puck",
            "am_santa",
        )
