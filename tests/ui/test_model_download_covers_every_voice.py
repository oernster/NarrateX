"""Every voice the picker offers must be fetched by the first-run download.

Kokoro's pipeline calls hf_hub_download for any voice file not already in the
HuggingFace cache, so a voice that is offered but not pre-fetched reaches the
network mid-read. The README promises narration is offline after the first run.

These tests build a fake HuggingFace cache under a tmp directory and never
download anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app
from voice_reader.infrastructure.tts.voice_profile_repository import (
    KokoroVoiceProfileRepository,
)
from voice_reader.ui import model_download_dialog

_OFFERED = tuple(p.name for p in KokoroVoiceProfileRepository().list_profiles())
_SNAPSHOT = "snap"


def _fake_cache(root: Path, voice_ids: tuple[str, ...]) -> None:
    snap = root / "hub" / "models--hexgrad--Kokoro-82M" / "snapshots" / _SNAPSHOT
    (snap / "voices").mkdir(parents=True)
    (snap / "config.json").write_text("{}", encoding="utf-8")
    (snap / "kokoro-v1_0.pth").write_bytes(b"")
    for v in voice_ids:
        (snap / "voices" / f"{v}.pt").write_bytes(b"")


@pytest.mark.parametrize("missing", _OFFERED)
def test_cache_missing_an_offered_voice_is_not_ready(
    monkeypatch, tmp_path: Path, missing: str
) -> None:
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    _fake_cache(tmp_path, tuple(v for v in _OFFERED if v != missing))

    # The voice set the entrypoint hands the first-run download, unchanged.
    ready = model_download_dialog.model_is_ready(app._preflight_voice_ids())

    assert not ready, f"{missing} is offered but the first-run download skips it"


def test_cache_holding_every_offered_voice_is_ready(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    _fake_cache(tmp_path, _OFFERED)

    assert model_download_dialog.model_is_ready(app._preflight_voice_ids())


def test_download_steps_fill_the_bar_and_fetch_every_offered_voice() -> None:
    steps = model_download_dialog.download_steps(app._preflight_voice_ids())
    voices = {name for name, _ in steps if name.startswith("voices/")}

    assert voices == {f"voices/{v}.pt" for v in _OFFERED}
    assert steps[-1][1] == model_download_dialog._FULL_PCT
