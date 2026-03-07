from __future__ import annotations

import types

from voice_reader.application.services.tts_engine_factory import TTSEngineFactory


def test_factory_falls_back_when_tts_missing(monkeypatch) -> None:
    monkeypatch.delitem(__import__("sys").modules, "TTS", raising=False)
    engine = TTSEngineFactory(model_name="x").create()
    assert engine.engine_name.lower().startswith("pyttsx3")


def test_factory_uses_xtts_when_tts_importable(monkeypatch) -> None:
    fake_tts = types.ModuleType("TTS")
    monkeypatch.setitem(__import__("sys").modules, "TTS", fake_tts)
    engine = TTSEngineFactory(model_name="model").create()
    assert engine.engine_name == "Coqui XTTS"
