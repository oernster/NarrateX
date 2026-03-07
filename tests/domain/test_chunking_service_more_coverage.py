from __future__ import annotations

from voice_reader.domain.services.chunking_service import ChunkingService


def test_chunking_hard_wrap_long_sentence() -> None:
    svc = ChunkingService(min_chars=20, max_chars=60)
    text = "A" * 500
    chunks = svc.chunk_text(text)
    assert len(chunks) > 5
    assert all(1 <= len(c.text) <= 60 for c in chunks)


def test_chunking_best_split_prefers_commas() -> None:
    svc = ChunkingService(min_chars=10, max_chars=30)
    text = "Hello, world, this, is, split." * 5
    chunks = svc.chunk_text(text)
    assert chunks
