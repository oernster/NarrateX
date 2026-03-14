from __future__ import annotations

import types
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.infrastructure.tts.kokoro_engine import KokoroEngine


def _install_fake_kokoro(
    monkeypatch, *, expected_lang_code: str, yielded_audio
) -> dict:
    """Install a fake `kokoro` module exposing `KPipeline`.

    Returns a dict capturing constructor args and pipeline call args.
    """

    calls: dict = {
        "lang_code": None,
        "voice": None,
        "text": None,
        "speed": None,
    }

    class FakePipeline:
        def __init__(self, *, lang_code: str) -> None:
            calls["lang_code"] = lang_code
            assert lang_code == expected_lang_code

        def __call__(self, text: str, *, voice: str, speed: float):
            calls["text"] = text
            calls["voice"] = voice
            calls["speed"] = speed
            return iter(yielded_audio)

    fake_kokoro = types.SimpleNamespace(KPipeline=FakePipeline)
    monkeypatch.setitem(__import__("sys").modules, "kokoro", fake_kokoro)
    return calls


def test_engine_initialization_uses_default_language_code() -> None:
    engine = KokoroEngine(language="b")
    assert engine.engine_name == "kokoro"


def test_engine_name_property_returns_kokoro() -> None:
    assert KokoroEngine().engine_name == "kokoro"


def test_synthesize_to_file_writes_wav_and_creates_output_dir(
    monkeypatch, tmp_path: Path
) -> None:
    out_dir = tmp_path / "nested" / "dir"
    out = out_dir / "out.wav"

    audio1 = np.zeros(240, dtype=np.float32)
    audio2 = np.ones(120, dtype=np.float32)
    yielded = [(None, None, audio1), (None, None, audio2)]

    calls = _install_fake_kokoro(
        monkeypatch,
        expected_lang_code="b",
        yielded_audio=yielded,
    )

    engine = KokoroEngine(language="b")
    vp = VoiceProfile(name="bm_george", reference_audio_paths=[])
    engine.synthesize_to_file(
        text="hello",
        voice_profile=vp,
        output_path=out,
        device="cpu",
        language="en-GB",
    )

    assert out.exists()
    assert out_dir.exists()
    assert calls["voice"] == "bm_george"


def test_synthesize_to_file_uses_24000_sample_rate(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    audio = np.zeros(100, dtype=np.float32)

    _install_fake_kokoro(
        monkeypatch,
        expected_lang_code="b",
        yielded_audio=[(None, None, audio)],
    )

    engine = KokoroEngine(language="b")
    engine.synthesize_to_file(
        text="x",
        voice_profile=VoiceProfile(name="bf_emma", reference_audio_paths=[]),
        output_path=out,
        device="cpu",
        language="en-GB",
    )

    info = sf.info(str(out))
    assert info.samplerate == 24000


def test_correct_voice_id_passed_to_pipeline(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "o.wav"

    calls = _install_fake_kokoro(
        monkeypatch,
        expected_lang_code="a",
        yielded_audio=[(None, None, np.zeros(10, dtype=np.float32))],
    )

    engine = KokoroEngine(language="b")
    vp = VoiceProfile(name="af_heart", reference_audio_paths=[])
    engine.synthesize_to_file(
        text="hello",
        voice_profile=vp,
        output_path=out,
        device="cpu",
        language="en-US",
    )
    assert calls["voice"] == "af_heart"


def test_empty_audio_generator_raises_error(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "o.wav"
    _install_fake_kokoro(monkeypatch, expected_lang_code="b", yielded_audio=[])

    engine = KokoroEngine(language="b")
    with pytest.raises(RuntimeError, match="no audio"):
        engine.synthesize_to_file(
            text="hello",
            voice_profile=VoiceProfile(name="bm_george", reference_audio_paths=[]),
            output_path=out,
            device="cpu",
            language="en-GB",
        )


def test_synthesize_to_file_concatenates_segments_correctly(
    monkeypatch, tmp_path: Path
) -> None:
    out = tmp_path / "out.wav"
    seg1 = np.array([0.0, 0.5], dtype=np.float32)
    seg2 = np.array([1.0], dtype=np.float32)
    seg3 = np.array([-1.0, -0.5, 0.25], dtype=np.float32)

    _install_fake_kokoro(
        monkeypatch,
        expected_lang_code="b",
        yielded_audio=[(None, None, seg1), (None, None, seg2), (None, None, seg3)],
    )

    engine = KokoroEngine(language="b")
    engine.synthesize_to_file(
        text="hello",
        voice_profile=VoiceProfile(name="bm_george", reference_audio_paths=[]),
        output_path=out,
        device="cpu",
        language="en-GB",
    )

    data, sr = sf.read(str(out), dtype="float32")
    assert sr == 24000
    # soundfile defaults to PCM_16, so 1.0 becomes ~0.99997 after quantization.
    assert np.allclose(
        data,
        np.concatenate([seg1, seg2, seg3]),
        atol=1e-4,
        rtol=0.0,
    )


def test_stream_synthesis_yields_audio_chunks(monkeypatch) -> None:
    seg1 = np.zeros(3, dtype=np.float32)
    seg2 = np.ones(2, dtype=np.float32)

    _install_fake_kokoro(
        monkeypatch,
        expected_lang_code="b",
        yielded_audio=[(None, None, seg1), (None, None, seg2)],
    )

    engine = KokoroEngine(language="b")
    vp = VoiceProfile(name="bf_emma", reference_audio_paths=[])
    chunks = list(engine.stream_synthesis("hello", vp))
    assert len(chunks) == 2
    assert np.array_equal(chunks[0], seg1)
    assert np.array_equal(chunks[1], seg2)
