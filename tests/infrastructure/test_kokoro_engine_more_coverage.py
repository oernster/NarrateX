from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.infrastructure.tts.kokoro_engine import KokoroEngine


class _FakePipeline:
    def __init__(self, *, lang_code: str, repo_id: str | None = None) -> None:
        self.lang_code = lang_code
        self.repo_id = repo_id
        self.calls: list[dict] = []

    def __call__(self, text: str, *, voice: str, speed: float):
        self.calls.append({"text": text, "voice": voice, "speed": speed})
        # Kokoro yields tuples (_, _, audio)
        yield (None, None, np.ones(100, dtype=np.float32))


def test_kokoro_resolve_lang_code_defaults_and_known_variants() -> None:
    k = KokoroEngine(language="b")
    assert k._resolve_lang_code(None) == "b"  # pylint: disable=protected-access
    assert k._resolve_lang_code("") == "b"  # pylint: disable=protected-access
    assert k._resolve_lang_code("en_gb") == "b"  # pylint: disable=protected-access
    assert k._resolve_lang_code("en-US") == "a"  # pylint: disable=protected-access
    assert k._resolve_lang_code("fr") == "b"  # pylint: disable=protected-access


def test_kokoro_pipeline_is_cached_per_thread_and_lang(
    monkeypatch, tmp_path: Path
) -> None:
    # Provide a fake `kokoro.KPipeline`.
    fake_kokoro = SimpleNamespace(KPipeline=_FakePipeline)
    monkeypatch.setitem(__import__("sys").modules, "kokoro", fake_kokoro)

    out1 = tmp_path / "a.wav"
    out2 = tmp_path / "b.wav"
    vp = VoiceProfile(name="bf_emma", reference_audio_paths=[])

    k = KokoroEngine(language="b")
    k.synthesize_to_file(
        text="hello", voice_profile=vp, output_path=out1, device="cpu", language="en-gb"
    )
    k.synthesize_to_file(
        text="hello", voice_profile=vp, output_path=out2, device="cpu", language="en-gb"
    )

    # Pipeline should be cached in TLS.
    cache = getattr(k._tls, "pipelines")  # pylint: disable=protected-access
    assert "b" in cache
    assert isinstance(cache["b"], _FakePipeline)
    assert len(cache["b"].calls) == 2


def test_kokoro_pipeline_fallback_when_repo_id_kw_not_supported(monkeypatch) -> None:
    class _OldPipeline:
        def __init__(self, *, lang_code: str):
            self.lang_code = lang_code

    fake_kokoro = SimpleNamespace(KPipeline=_OldPipeline)
    monkeypatch.setitem(__import__("sys").modules, "kokoro", fake_kokoro)

    k = KokoroEngine(language="b")
    p = k._get_pipeline(
        KPipeline=_OldPipeline, lang_code="b", repo_id="x"
    )  # pylint: disable=protected-access
    assert isinstance(p, _OldPipeline)
