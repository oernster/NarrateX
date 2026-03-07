from __future__ import annotations

import types
from pathlib import Path

import pytest

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.infrastructure.tts.pyttsx3_engine import Pyttsx3Engine
from voice_reader.infrastructure.tts.xtts_engine import XTTSCoquiEngine
from voice_reader.shared.errors import TTSError


def test_pyttsx3_engine_writes_file(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "out.wav"

    class FakeVoice:
        def __init__(self, name: str, vid: str) -> None:
            self.name = name
            self.id = vid

    class FakeEngine:
        def __init__(self) -> None:
            self._props = {}

        def setProperty(self, k: str, v):
            self._props[k] = v

        def getProperty(self, k: str):
            if k == "voices":
                return [FakeVoice("System", "1"), FakeVoice("Alice", "2")]
            raise KeyError(k)

        def save_to_file(self, text: str, path: str) -> None:
            Path(path).write_bytes(text.encode("utf-8"))

        def runAndWait(self) -> None:
            return

    fake_pyttsx3 = types.SimpleNamespace(init=lambda: FakeEngine())
    monkeypatch.setitem(__import__("sys").modules, "pyttsx3", fake_pyttsx3)

    engine = Pyttsx3Engine()
    vp = VoiceProfile(name="alice", reference_audio_paths=[])
    engine.synthesize_to_file(
        text="hello",
        voice_profile=vp,
        output_path=out,
        device="cpu",
        language="en",
    )
    assert out.exists()


def test_xtts_engine_requires_reference_audio(tmp_path: Path) -> None:
    engine = XTTSCoquiEngine(model_name="x")
    out = tmp_path / "o.wav"
    with pytest.raises(TTSError):
        engine.synthesize_to_file(
            text="hi",
            voice_profile=VoiceProfile(name="v", reference_audio_paths=[]),
            output_path=out,
            device="cpu",
            language="en",
        )


def test_xtts_engine_loads_tts_api_when_available(monkeypatch, tmp_path: Path) -> None:
    class FakeTTS:
        def __init__(self, model_name: str, gpu: bool) -> None:
            self.model_name = model_name
            self.gpu = gpu

        def tts_to_file(self, text, speaker_wav, language, file_path):
            Path(file_path).write_bytes(b"wav")

    fake_api = types.SimpleNamespace(TTS=FakeTTS)
    fake_pkg = types.SimpleNamespace(api=fake_api)
    monkeypatch.setitem(__import__("sys").modules, "TTS", fake_pkg)
    monkeypatch.setitem(__import__("sys").modules, "TTS.api", fake_api)

    engine = XTTSCoquiEngine(model_name="m")
    vp = VoiceProfile(name="v", reference_audio_paths=[tmp_path / "r.wav"])
    (tmp_path / "r.wav").write_bytes(b"x")
    out = tmp_path / "o.wav"
    engine.synthesize_to_file(
        text="hi",
        voice_profile=vp,
        output_path=out,
        device="cpu",
        language="en",
    )
    assert out.exists()
