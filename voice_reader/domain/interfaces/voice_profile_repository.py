"""Domain interface: voice profile listing and loading."""

from __future__ import annotations

from typing import Protocol, Sequence

from voice_reader.domain.entities.voice_profile import VoiceProfile


class VoiceProfileRepository(Protocol):
    def list_profiles(self) -> Sequence[VoiceProfile]: ...
