from __future__ import annotations

from pathlib import Path

from voice_reader.infrastructure.tts.voice_profile_repository import (
    KokoroVoiceProfileRepository,
)


def test_repo_includes_kokoro_voice_ids(tmp_path: Path) -> None:
    del tmp_path
    repo = KokoroVoiceProfileRepository()
    profiles = list(repo.list_profiles())
    assert any(p.name == "bf_emma" for p in profiles)


def test_repo_has_no_reference_audio_paths(tmp_path: Path) -> None:
    del tmp_path
    repo = KokoroVoiceProfileRepository()
    profiles = list(repo.list_profiles())
    assert profiles
    assert all(not p.reference_audio_paths for p in profiles)
