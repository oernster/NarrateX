"""Filesystem-based voice profile repository.

Expected layout:

voices/<voice_name>/*.wav
"""

from __future__ import annotations

from dataclasses import dataclass
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
        profiles: List[VoiceProfile] = [
            VoiceProfile(name="system", reference_audio_paths=[])
        ]

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
            profiles.append(
                VoiceProfile(name=voice_dir.name, reference_audio_paths=wavs)
            )
        return profiles
