from __future__ import annotations

import importlib.util
import types

from voice_reader.infrastructure.tts.tts_engine_factory import TTSEngineFactory


def test_factory_prefers_kokoro_when_available(monkeypatch) -> None:
    """Kokoro should be chosen as the default engine when importable."""

    def fake_find_spec(name: str):
        if name == "kokoro":
            return object()
        return None

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    engine = TTSEngineFactory().create()
    assert engine.engine_name == "kokoro"


def test_factory_raises_when_kokoro_missing(monkeypatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    try:
        TTSEngineFactory().create()
        assert False, "Expected RuntimeError when Kokoro is missing"
    except RuntimeError as exc:
        assert "Kokoro" in str(exc)
