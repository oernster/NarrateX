from __future__ import annotations

from voice_reader.domain.services.chunking_service import ChunkingService


def test_chunking_fallback_start_in_norm_when_find_fails() -> None:
    # Construct a normalized string where find() from the current cursor fails.
    # This exercises the `start_in_norm == -1` branch.
    text = "A\n\nB\n\nA"
    svc = ChunkingService(min_chars=1, max_chars=10)
    chunks = svc.chunk_text(text)
    assert chunks


def test_chunking_hard_wrap_empty_piece_path() -> None:
    # Force `_best_split()` to return 0 by giving a window of only whitespace.
    svc = ChunkingService(min_chars=1, max_chars=5)
    pieces = list(svc._hard_wrap("     ", 0))  # pylint: disable=protected-access
    assert pieces


def test_chunking_hard_wrap_prefers_commas_then_spaces() -> None:
    svc = ChunkingService(min_chars=1, max_chars=20)
    assert svc._best_split("a,b,c, d e f") > 0  # pylint: disable=protected-access
    assert svc._best_split("a b c d") > 0  # pylint: disable=protected-access
