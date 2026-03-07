from __future__ import annotations

import importlib.util
import types

from voice_reader.application.services.tts_engine_factory import TTSEngineFactory


def test_factory_prefers_kokoro_when_available(monkeypatch) -> None:
    """Kokoro should be chosen as the default engine when importable."""

    def fake_find_spec(name: str):
        if name == "kokoro":
            return object()
        return None

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    engine = TTSEngineFactory(model_name="x").create()
    assert engine.engine_name == "kokoro"


def test_factory_uses_xtts_hybrid_when_tts_available_and_kokoro_missing(monkeypatch) -> None:
    """If XTTS is available but Kokoro isn't, keep the old behavior."""

    def fake_find_spec(name: str):
        if name == "TTS":
            return object()
        return None

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    engine = TTSEngineFactory(model_name="model").create()
    assert "xtts" in engine.engine_name.lower()


def test_factory_falls_back_to_pyttsx3_when_no_engines_available(monkeypatch) -> None:
    def fake_find_spec(name: str):
        return None

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    engine = TTSEngineFactory(model_name="x").create()
    assert engine.engine_name.lower().startswith("pyttsx3")
