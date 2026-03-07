"""Application service for voice profile listing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.voice_profile_repository import (
    VoiceProfileRepository,
)


@dataclass(frozen=True, slots=True)
class VoiceProfileService:
    repo: VoiceProfileRepository

    def list_profiles(self) -> Sequence[VoiceProfile]:
        return self.repo.list_profiles()
