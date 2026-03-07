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
            wavs = sorted(list(voice_dir.glob("*.wav")))
            if not wavs:
                continue
            profiles.append(
                VoiceProfile(name=voice_dir.name, reference_audio_paths=wavs)
            )
        return profiles
