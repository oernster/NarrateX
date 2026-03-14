from __future__ import annotations

import json
from pathlib import Path

from voice_reader.domain.alignment.alignment_io import AlignmentIO
from voice_reader.domain.alignment.model import ChunkAlignment, TimedTextSpan


def test_alignment_io_load_returns_none_on_bad_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.align.json"
    p.write_text("{not-json", encoding="utf-8")

    io = AlignmentIO()
    assert io.load(p) is None


def test_alignment_io_load_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "a" / "x.align.json"
    alignment = ChunkAlignment(
        chunk_id=3,
        duration_ms=1200,
        spans=[
            TimedTextSpan(
                start_char=1,
                end_char=5,
                audio_start_ms=0,
                audio_end_ms=400,
                confidence=0.5,
            )
        ],
    )

    io = AlignmentIO()
    io.save(path=p, alignment=alignment)

    loaded = io.load(p)
    assert loaded == alignment

    # Ensure file is valid JSON.
    raw = p.read_text(encoding="utf-8")
    json.loads(raw)

