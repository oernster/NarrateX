from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.voice_profile_repository import (
    VoiceProfileRepository,
)


@dataclass(frozen=True, slots=True)
class FakeRepo(VoiceProfileRepository):
    profiles: Sequence[VoiceProfile]

    def list_profiles(self) -> Sequence[VoiceProfile]:
        return self.profiles


def test_voice_profile_service_lists_profiles(tmp_path: Path) -> None:
    profiles = [VoiceProfile(name="a", reference_audio_paths=[tmp_path / "x.wav"])]
    svc = VoiceProfileService(repo=FakeRepo(profiles=profiles))
    assert list(svc.list_profiles()) == profiles
