"""Factory for creating the TTS engine.

This project is intentionally **Kokoro-only**.

Important packaging note:
Kokoro imports a dependency chain (e.g. misaki, spaCy and a spaCy model) that
may not be detected by static analysis when packaged.

If anything in that import chain is missing at runtime (e.g. ``spacy`` or
``en_core_web_sm``), we fail fast with an actionable message.
"""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass

from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.infrastructure.tts.kokoro_engine import KokoroEngine


@dataclass(frozen=True, slots=True)
class TTSEngineFactory:
    """Create a Kokoro engine instance."""

    def create(self) -> TTSEngine:
        # find_spec() is not sufficient here: it can succeed even when importing
        # `kokoro` fails later due to missing transitive dependencies.
        try:
            if importlib.util.find_spec("kokoro") is None:
                raise ModuleNotFoundError("kokoro")
            importlib.import_module("kokoro")
        except ModuleNotFoundError as exc:
            missing = exc.name or "<unknown>"
            raise RuntimeError(
                "Kokoro is not available (import failed). "
                f"Missing dependency: {missing!r}. "
                "This app supports Kokoro voices only. Ensure Kokoro and its dependencies "
                "are installed, e.g. `pip install kokoro soundfile spacy` and install the "
                "spaCy model `en_core_web_sm`."
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                "Kokoro is not available (import failed). " f"Reason: {exc!r}"
            ) from exc

        return KokoroEngine()
