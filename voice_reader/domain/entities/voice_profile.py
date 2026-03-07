"""Domain entity: VoiceProfile."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    name: str
    reference_audio_paths: Sequence[Path]
