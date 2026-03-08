from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.infrastructure.tts.xtts_engine import XTTSCoquiEngine
from voice_reader.shared.errors import TTSError


def test_xtts_engine_select_reference_window_returns_input_on_none() -> None:
    eng = XTTSCoquiEngine(model_name="m")
    assert eng._select_reference_window(data=None, sample_rate=1, max_seconds=1.0) is None  # pylint: disable=protected-access


def test_xtts_engine_select_reference_window_short_clip_passthrough() -> None:
    eng = XTTSCoquiEngine(model_name="m", max_reference_seconds=2.0)
    data = np.zeros((10, 1), dtype=np.float32)
    out = eng._select_reference_window(data=data, sample_rate=100, max_seconds=2.0)  # pylint: disable=protected-access
    assert out is data


def test_xtts_engine_select_reference_window_trims_and_picks_segment(monkeypatch) -> None:
    monkeypatch.setenv("NARRATEX_REF_DROP_START_SECONDS", "0")
    eng = XTTSCoquiEngine(model_name="m", max_reference_seconds=0.05)
    sr = 1000

    # 0.2s of audio. Put energy in the middle.
    mono = np.zeros(200, dtype=np.float32)
    mono[80:120] = 0.5
    data = mono.reshape(-1, 1)
    out = eng._select_reference_window(data=data, sample_rate=sr, max_seconds=0.05)  # pylint: disable=protected-access
    assert out.shape[1] == 1
    assert out.shape[0] <= int(0.05 * sr) + 1
    assert float(np.max(out)) > 0.0


def test_xtts_engine_apply_deterministic_seed_per_chunk(monkeypatch) -> None:
    monkeypatch.setenv("NARRATEX_TTS_SEED", "123")
    monkeypatch.setenv("NARRATEX_TTS_SEED_MODE", "per_chunk")
    eng = XTTSCoquiEngine(model_name="m")
    eng._apply_deterministic_seed(text="hi", voice_profile=VoiceProfile(name="v", reference_audio_paths=[]))  # pylint: disable=protected-access


def test_xtts_engine_get_or_create_reuses_cached_instance(monkeypatch) -> None:
    eng = XTTSCoquiEngine(model_name="m")
    # Pre-seed internal cache.
    obj = object()
    eng._tts = obj  # pylint: disable=protected-access
    eng._gpu = False  # pylint: disable=protected-access
    assert eng._get_or_create(device="cpu") is obj  # pylint: disable=protected-access


def test_xtts_engine_get_or_create_wraps_load_errors(monkeypatch) -> None:
    # Force the import of TTS.api.TTS to fail.
    monkeypatch.setitem(__import__("sys").modules, "TTS", None)
    monkeypatch.setitem(__import__("sys").modules, "TTS.api", None)
    eng = XTTSCoquiEngine(model_name="m")
    with pytest.raises(TTSError):
        eng._get_or_create(device="cpu")  # pylint: disable=protected-access
