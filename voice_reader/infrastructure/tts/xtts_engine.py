"""Coqui XTTS adapter.

This module is intentionally lazy-loading to avoid heavy initialization in tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.shared.errors import TTSError


@dataclass
class XTTSCoquiEngine(TTSEngine):
    model_name: str

    def __post_init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._tts: Any | None = None
        self._gpu: bool | None = None

    @property
    def engine_name(self) -> str:
        return "Coqui XTTS"

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
        device: str,
        language: str,
    ) -> Path:
        try:
            tts = self._get_or_create(device=device)
            speaker_wav = [str(p) for p in voice_profile.reference_audio_paths]
            if not speaker_wav:
                raise TTSError(
                    "XTTS requires reference audio samples. Add WAVs under "
                    "voices/<voice_name>/*.wav"
                )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            tts.tts_to_file(
                text=text,
                speaker_wav=speaker_wav,
                language=language,
                file_path=str(output_path),
            )
            return output_path
        except TTSError:
            raise
        except Exception as exc:  # pragma: no cover
            raise TTSError(str(exc)) from exc

    def _get_or_create(self, *, device: str) -> Any:
        use_gpu = device == "cuda"
        if self._tts is not None and self._gpu == use_gpu:
            return self._tts

        self._log.info("Loading TTS model %s (gpu=%s)", self.model_name, use_gpu)
        try:
            from TTS.api import TTS

            self._tts = TTS(self.model_name, gpu=use_gpu)
            self._gpu = use_gpu
            return self._tts
        except Exception as exc:  # pragma: no cover
            raise TTSError(f"Failed to load TTS model: {exc}") from exc
