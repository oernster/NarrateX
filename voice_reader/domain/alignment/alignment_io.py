"""Infrastructure-agnostic helpers for reading/writing alignment JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.alignment.model import ChunkAlignment


@dataclass(frozen=True, slots=True)
class AlignmentIO:
    def load(self, path: Path) -> ChunkAlignment | None:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            d = json.loads(raw)
            return ChunkAlignment.from_dict(d)
        except Exception:
            return None

    def save(self, *, path: Path, alignment: ChunkAlignment) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = alignment.to_dict()
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
