from __future__ import annotations

import importlib.util

from voice_reader.application.services.tts_engine_factory import TTSEngineFactory
from voice_reader.infrastructure.tts.hybrid_engine import HybridTTSEngine
from voice_reader.infrastructure.tts.kokoro_engine import KokoroEngine
from voice_reader.infrastructure.tts.pyttsx3_engine import Pyttsx3Engine


def test_factory_prefers_hybrid_when_both_kokoro_and_tts_available(monkeypatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    eng = TTSEngineFactory(model_name="m").create()
    assert isinstance(eng, HybridTTSEngine)


def test_factory_returns_kokoro_when_only_kokoro_available(monkeypatch) -> None:
    def _find(name: str):
        if name == "kokoro":
            return object()
        return None

    monkeypatch.setattr(importlib.util, "find_spec", _find)
    eng = TTSEngineFactory(model_name="m").create()
    assert isinstance(eng, KokoroEngine)


def test_factory_returns_hybrid_when_only_tts_available(monkeypatch) -> None:
    def _find(name: str):
        if name == "TTS":
            return object()
        return None

    monkeypatch.setattr(importlib.util, "find_spec", _find)
    eng = TTSEngineFactory(model_name="m").create()
    assert isinstance(eng, HybridTTSEngine)


def test_factory_returns_pyttsx3_when_neither_available(monkeypatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    eng = TTSEngineFactory(model_name="m").create()
    assert isinstance(eng, Pyttsx3Engine)


def test_factory_handles_find_spec_errors(monkeypatch) -> None:
    def _boom(name: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(importlib.util, "find_spec", _boom)
    eng = TTSEngineFactory(model_name="m").create()
    assert isinstance(eng, Pyttsx3Engine)


def test_factory_hybrid_engine_name(monkeypatch) -> None:
    # Purely to cover the Hybrid.engine_name property formatting.
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    hybrid = HybridTTSEngine(cloning_engine=Pyttsx3Engine(), native_engine=Pyttsx3Engine())
    assert "Hybrid" in hybrid.engine_name

