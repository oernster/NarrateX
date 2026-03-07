from __future__ import annotations

from pathlib import Path

from voice_reader.infrastructure.tts.voice_profile_repository import (
    FilesystemVoiceProfileRepository,
)


def test_repo_always_includes_system_profile(tmp_path: Path) -> None:
    repo = FilesystemVoiceProfileRepository(voices_dir=tmp_path / "missing")
    profiles = list(repo.list_profiles())
    assert profiles
    assert profiles[0].name == "system"


def test_repo_loads_wavs(tmp_path: Path) -> None:
    voices = tmp_path / "voices"
    (voices / "bob").mkdir(parents=True)
    (voices / "bob" / "a.wav").write_bytes(b"x")
    repo = FilesystemVoiceProfileRepository(voices_dir=voices)
    profiles = list(repo.list_profiles())
    assert any(p.name == "bob" for p in profiles)
