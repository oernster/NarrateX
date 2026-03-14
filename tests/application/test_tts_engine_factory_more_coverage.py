from __future__ import annotations

import importlib.util

from voice_reader.application.services.tts_engine_factory import TTSEngineFactory
from voice_reader.infrastructure.tts.kokoro_engine import KokoroEngine


def test_factory_returns_kokoro_when_only_kokoro_available(monkeypatch) -> None:
    def _find(name: str):
        if name == "kokoro":
            return object()
        return None

    monkeypatch.setattr(importlib.util, "find_spec", _find)
    eng = TTSEngineFactory().create()
    assert isinstance(eng, KokoroEngine)


def test_factory_handles_find_spec_errors(monkeypatch) -> None:
    def _boom(name: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(importlib.util, "find_spec", _boom)
    try:
        TTSEngineFactory().create()
        assert False, "Expected RuntimeError when Kokoro is missing"
    except RuntimeError as exc:
        assert "Kokoro" in str(exc)

