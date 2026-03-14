"""Kokoro TTS adapter.

Implements the domain [`TTSEngine`](voice_reader/domain/interfaces/tts_engine.py:11)
protocol using Kokoro native voices.

Voice profile interpretation:

- Native mode: [`VoiceProfile.reference_audio_paths`](voice_reader/domain/entities/voice_profile.py:10)
  is empty -> use `voice_profile.name` as Kokoro voice ID (e.g. ``bm_george``).
- Reference mode: reference audio is non-empty -> this engine is not suitable.
  Selection is handled by the hybrid engine/factory.

Dependencies:
    pip install kokoro>=0.9.4 soundfile
"""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Iterator

import numpy as np
import soundfile as sf

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.tts_engine import TTSEngine


class KokoroEngine(TTSEngine):
    """Kokoro implementation of [`TTSEngine`](voice_reader/domain/interfaces/tts_engine.py:11)."""

    sample_rate_hz: int = 24_000

    def __init__(self, language: str = "b"):
        """Create a Kokoro engine.

        Args:
            language: Kokoro language code.
                - ``"b"`` = British English
                - ``"a"`` = American English

        Note:
            Pipeline creation is done lazily per synthesis call so the module
            remains importable even when Kokoro isn't installed.
        """

        self._default_lang_code = language
        self._repo_id = "hexgrad/Kokoro-82M"
        # Thread-local pipeline cache so multi-threaded synthesis doesn't share
        # Kokoro state across threads (and avoids re-loading the model per chunk).
        self._tls = threading.local()

    @property
    def engine_name(self) -> str:
        return "kokoro"

    def stream_synthesis(
        self, text: str, voice_profile: VoiceProfile
    ) -> Iterator[np.ndarray]:
        """Yield audio chunks from Kokoro as they are generated.

        This is an optional API (not part of the domain protocol) and is
        intended for low-latency playback.
        """

        yield from self._stream(
            text=text,
            voice_profile=voice_profile,
            lang_code=self._default_lang_code,
        )

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
        device: str,
        language: str,
    ) -> Path:
        """Synthesize speech to a WAV file and return `output_path`."""

        del device  # Kokoro is CPU-only; keep interface compatibility.

        voice_id = voice_profile.name

        lang_code = self._resolve_lang_code(language)
        segments = list(
            self._stream(text=text, voice_profile=voice_profile, lang_code=lang_code)
        )

        if not segments:
            raise RuntimeError("Kokoro produced no audio output")

        audio_data = np.concatenate(segments)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        sf.write(
            str(output_path),
            audio_data,
            int(self.sample_rate_hz),
            format="WAV",
        )

        return output_path

    def _resolve_lang_code(self, language: str | None) -> str:
        if not language:
            return self._default_lang_code

        normalized = language.strip().lower().replace("_", "-")
        if normalized == "en-gb":
            return "b"
        if normalized == "en-us":
            return "a"
        return self._default_lang_code

    def _stream(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        lang_code: str,
    ) -> Iterator[np.ndarray]:
        # Import lazily so the rest of the app can run without Kokoro installed.
        try:
            from kokoro import KPipeline  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Kokoro is not installed. Install with `pip install kokoro soundfile`."
            ) from exc

        pipeline = self._get_pipeline(
            KPipeline=KPipeline,
            lang_code=lang_code,
            repo_id=self._repo_id,
        )

        generator = pipeline(
            text,
            voice=voice_profile.name,
            speed=1.0,
        )

        for _, _, audio in generator:
            # Kokoro yields numpy arrays already; normalize to 1D float32.
            yield np.asarray(audio, dtype=np.float32).reshape(-1)

    def _get_pipeline(self, *, KPipeline, lang_code: str, repo_id: str):
        cache = getattr(self._tls, "pipelines", None)
        if cache is None:
            cache = {}
            self._tls.pipelines = cache
        pipeline = cache.get(lang_code)
        if pipeline is None:
            # Pin the default repo_id to suppress noisy Kokoro warnings.
            # Keep compatibility with older Kokoro versions / test fakes that
            # don't accept the `repo_id` kwarg.
            try:
                pipeline = KPipeline(lang_code=lang_code, repo_id=repo_id)
            except TypeError:
                pipeline = KPipeline(lang_code=lang_code)
            cache[lang_code] = pipeline
        return pipeline
