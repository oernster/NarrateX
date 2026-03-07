from __future__ import annotations


def test_voice_profile_repository_protocol_importable() -> None:
    from voice_reader.domain.interfaces.voice_profile_repository import (  # noqa: F401
        VoiceProfileRepository,
    )
