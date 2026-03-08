from __future__ import annotations

import importlib.util
from pathlib import Path

from voice_reader.infrastructure.tts.voice_profile_repository import (
    FilesystemVoiceProfileRepository,
)


def test_repo_includes_kokoro_voice_ids_when_available(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    repo = FilesystemVoiceProfileRepository(voices_dir=tmp_path / "voices")
    profiles = list(repo.list_profiles())
    assert any(p.name == "bf_emma" for p in profiles)


def test_repo_filters_ref_and_pcm16_and_overrides_collision(monkeypatch, tmp_path: Path) -> None:
    # Make kokoro available so we have a native voice ID present.
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())

    voices = tmp_path / "voices"
    (voices / "bf_emma").mkdir(parents=True)
    # Real reference
    (voices / "bf_emma" / "a.wav").write_bytes(b"x")
    # Derived artifacts that must be ignored
    (voices / "bf_emma" / "a.ref.wav").write_bytes(b"x")
    (voices / "bf_emma" / "a.pcm16.wav").write_bytes(b"x")

    repo = FilesystemVoiceProfileRepository(voices_dir=voices)
    profiles = list(repo.list_profiles())
    # Ensure the filesystem profile wins and includes only the real wav.
    chosen = [p for p in profiles if p.name == "bf_emma"][0]
    assert [Path(p).name for p in chosen.reference_audio_paths] == ["a.wav"]


def test_repo_handles_kokoro_find_spec_error(monkeypatch, tmp_path: Path) -> None:
    def _boom(name: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(importlib.util, "find_spec", _boom)
    repo = FilesystemVoiceProfileRepository(voices_dir=tmp_path / "voices")
    profiles = list(repo.list_profiles())
    assert profiles and profiles[0].name == "system"

