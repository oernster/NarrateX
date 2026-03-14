from __future__ import annotations

from pathlib import Path

from voice_reader.infrastructure.tts.voice_profile_repository import (
    KokoroVoiceProfileRepository,
)


def test_repo_includes_kokoro_voice_ids(tmp_path: Path) -> None:
    del tmp_path
    repo = KokoroVoiceProfileRepository()
    names = [p.name for p in repo.list_profiles()]
    # One representative ID is enough to prove they're included.
    assert "bm_george" in names
