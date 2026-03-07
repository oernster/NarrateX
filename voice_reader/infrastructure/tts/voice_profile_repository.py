"""Filesystem-based voice profile repository.

Expected layout:

voices/<voice_name>/*.wav
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
from typing import List, Sequence

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.voice_profile_repository import (
    VoiceProfileRepository,
)


@dataclass(frozen=True, slots=True)
class FilesystemVoiceProfileRepository(VoiceProfileRepository):
    voices_dir: Path

    def list_profiles(self) -> Sequence[VoiceProfile]:
        # Always provide a functional default profile for fallback engines.
        profiles: List[VoiceProfile] = [VoiceProfile(name="system", reference_audio_paths=[])]

        # If Kokoro is installed, expose its native voices as selectable profiles.
        # These are *native-mode* profiles (no reference audio) and will be routed
        # to the native engine by the hybrid engine.
        if self._kokoro_available():
            profiles.extend(
                [
                    VoiceProfile(name=v, reference_audio_paths=[])
                    for v in self._kokoro_voice_ids()
                ]
            )

        if not self.voices_dir.exists():
            return profiles
        voice_dirs = sorted([p for p in self.voices_dir.iterdir() if p.is_dir()])
        for voice_dir in voice_dirs:
            # XTTS reference WAV preprocessing historically wrote "*.ref.wav"
            # next to the original. Those derived files must NOT be treated as
            # user-provided reference samples, otherwise the voice can drift and
            # the folder can explode with ref.ref.ref.wav variants.
            wavs = []
            for p in sorted(list(voice_dir.glob("*.wav"))):
                name = p.name.lower()
                if name.endswith(".ref.wav") or ".ref.ref" in name:
                    continue
                # Historical artifacts: we previously wrote multiple derived
                # PCM16 copies into the voice directory. They are not suitable
                # as *reference* samples and can degrade voice similarity.
                if ".pcm16" in name:
                    continue
                wavs.append(p)
            if not wavs:
                continue
            # If a filesystem voice collides with a Kokoro voice ID, the
            # filesystem voice wins because it is explicitly user-provided
            # reference mode.
            profiles = [p for p in profiles if p.name != voice_dir.name]
            profiles.append(VoiceProfile(name=voice_dir.name, reference_audio_paths=wavs))

        # Keep dropdown stable and deterministic. Deduplicate by name, allowing
        # later entries to override earlier ones (filesystem voices should win
        # over built-in/native IDs).
        unique_by_name: dict[str, VoiceProfile] = {}
        for p in profiles:
            unique_by_name[p.name] = p
        return list(unique_by_name.values())

    @staticmethod
    def _kokoro_available() -> bool:
        try:
            return importlib.util.find_spec("kokoro") is not None
        except Exception:
            return False

    @staticmethod
    def _kokoro_voice_ids() -> Sequence[str]:
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
