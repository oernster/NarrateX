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


def _best_torch_device() -> str:
    """Return the fastest available torch device: cuda > mps > cpu."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _normalise_for_tts(text: str) -> str:
    """Pre-process text to avoid misaki G2P failures on non-American content.

    misaki 0.7.x uses a CMU American-English dictionary.  Two classes of input
    produce token.phonemes=None (silent audio after our crash-fix):

    1. Non-breaking / typographic hyphens (U+2011-U+2014).
    2. British English spellings absent from the CMU dictionary.
    """
    import re

    # ── Typographic punctuation ───────────────────────────────────────────────
    # Non-breaking hyphen (U+2011) between letters = hyphenation artefact → join
    text = re.sub(r"([a-zA-Z])‑([a-z])", r"\1\2", text)
    text = text.replace("‑", "-")   # remaining non-breaking hyphens → plain
    text = text.replace("‒", "-")   # figure dash
    text = text.replace("–", " - ") # en dash
    text = text.replace("—", " - ") # em dash

    def sub(pat: str, repl: str, t: str) -> str:
        return re.sub(pat, repl, t, flags=re.IGNORECASE)

    # ── British -isation family (ORDER: longest suffix first) ─────────────────
    # "organisational" ends in -isational, NOT -isation, so needs its own rule.
    text = sub(r"\b(\w+)isationally\b", r"\1izationally", text)
    text = sub(r"\b(\w+)isational\b",   r"\1izational",   text)
    text = sub(r"\b(\w+)isations\b",    r"\1izations",    text)
    text = sub(r"\b(\w+)isation\b",     r"\1ization",     text)
    text = sub(r"\b(\w+)isers\b",       r"\1izers",       text)
    text = sub(r"\b(\w+)iser\b",        r"\1izer",        text)
    text = sub(r"\b(\w+)ising\b",       r"\1izing",       text)
    text = sub(r"\b(\w+)ised\b",        r"\1ized",        text)
    # -ise → -ize: only for stems ≥ 4 chars to avoid "rise"→"rize", "wise"→"wize"
    # "promise", "surprise" etc. are in CMU already so any slight mispronunciation
    # from converting them is better than silence.
    text = sub(r"\b(\w{4,})ise\b",      r"\1ize",         text)

    # ── British -our words (word list to avoid "four"→"for" etc.) ────────────
    _our = {
        "behaviour": "behavior", "behaviours": "behaviors",
        "behavioural": "behavioral", "behaviourally": "behaviorally",
        "colour": "color", "colours": "colors", "coloured": "colored",
        "colouring": "coloring", "colourful": "colorful",
        "favour": "favor", "favours": "favors", "favoured": "favored",
        "favouring": "favoring", "favourite": "favorite", "favourites": "favorites",
        "honour": "honor", "honours": "honors", "honoured": "honored",
        "honourable": "honorable", "dishonour": "dishonor",
        "humour": "humor", "humours": "humors", "humourless": "humorless",
        "labour": "labor", "labours": "labors", "laboured": "labored",
        "labourer": "laborer", "labourers": "laborers",
        "neighbour": "neighbor", "neighbours": "neighbors",
        "neighbourhood": "neighborhood", "neighbouring": "neighboring",
        "rumour": "rumor", "rumours": "rumors", "rumoured": "rumored",
        "flavour": "flavor", "flavours": "flavors", "flavoured": "flavored",
        "endeavour": "endeavor", "endeavours": "endeavors",
        "harbour": "harbor", "harbours": "harbors",
        "armour": "armor", "glamour": "glamor", "valour": "valor",
        "odour": "odor", "odours": "odors", "candour": "candor",
        "vigour": "vigor", "rigour": "rigor", "ardour": "ardor",
        "fervour": "fervor", "splendour": "splendor",
        "tumour": "tumor", "tumours": "tumors",
    }
    for brit, am in _our.items():
        text = re.sub(r"\b" + re.escape(brit) + r"\b", am, text,
                      flags=re.IGNORECASE)

    # ── British -re → -er ─────────────────────────────────────────────────────
    _re = {
        "centre": "center", "centres": "centers", "centred": "centered",
        "theatre": "theater", "theatres": "theaters",
        "litre": "liter", "litres": "liters",
        "fibre": "fiber", "fibres": "fibers",
        "calibre": "caliber", "lustre": "luster",
        "metre": "meter", "metres": "meters",
        "kilometre": "kilometer", "kilometres": "kilometers",
    }
    for brit, am in _re.items():
        text = re.sub(r"\b" + re.escape(brit) + r"\b", am, text,
                      flags=re.IGNORECASE)

    return text


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
        # Engine-level pipeline cache, shared across synthesis threads.
        # Using threading.local() caused a full model reload (and MPS JIT
        # recompilation, ~11 s) on every play press because each new synthesis
        # thread starts with an empty thread-local store.  A shared dict with a
        # lock is safe for sequential synthesis (one thread at a time) and
        # still correct for parallel synthesis (threads share one pipeline
        # instance, which kokoro supports for concurrent read-only inference).
        self._pipeline_cache: dict = {}
        self._pipeline_lock = threading.Lock()
        # Pre-load the pipeline at engine-creation time so the model is ready
        # before the user presses play (avoids a 4-11 s cold-start stall that
        # would otherwise land during the first synthesis call).
        self._start_prewarm()

    def _start_prewarm(self) -> None:
        def _load() -> None:
            try:
                from kokoro import KPipeline  # type: ignore
                self._get_pipeline(
                    KPipeline=KPipeline,
                    lang_code=self._default_lang_code,
                    repo_id=self._repo_id,
                )
            except Exception:
                pass  # Best-effort; synthesis retries on first use.

        threading.Thread(target=_load, name="kokoro-prewarm", daemon=True).start()

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
            text=_normalise_for_tts(text),
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

        lang_code = self._resolve_lang_code(language)
        segments = list(
            self._stream(
                text=_normalise_for_tts(text),
                voice_profile=voice_profile,
                lang_code=lang_code,
            )
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
        # Fast path: already cached.
        pipeline = self._pipeline_cache.get(lang_code)
        if pipeline is not None:
            return pipeline
        # Slow path: first call — create and cache under the lock so concurrent
        # threads don't each pay the model-load cost.
        with self._pipeline_lock:
            pipeline = self._pipeline_cache.get(lang_code)
            if pipeline is None:
                # Pin the default repo_id to suppress noisy Kokoro warnings.
                # Keep compatibility with older Kokoro versions / test fakes
                # that don't accept the `repo_id` kwarg.
                try:
                    pipeline = KPipeline(lang_code=lang_code, repo_id=repo_id)
                except TypeError:
                    # repo_id not accepted (kokoro <0.8.x). Pass the best
                    # available device: CUDA > MPS (Apple Silicon) > CPU.
                    device = _best_torch_device()
                    try:
                        pipeline = KPipeline(lang_code=lang_code, device=device)
                    except TypeError:
                        pipeline = KPipeline(lang_code=lang_code)
                self._pipeline_cache[lang_code] = pipeline
        return pipeline
