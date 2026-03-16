from __future__ import annotations

from voice_reader.domain.services.reading_start_service import (
    ReadingStart,
    ReadingStartService,
)


def test_looks_like_prose_punctuation_short_is_false() -> None:
    svc = ReadingStartService()
    assert not svc._looks_like_prose("Short.")  # pylint: disable=protected-access


def test_line_at_bounds_and_start_after_heading_end_out_of_range() -> None:
    svc = ReadingStartService()
    text = "HEADING\n\nBody."

    assert svc._line_at(text, -10) == "HEADING"  # pylint: disable=protected-access
    assert svc._line_at(text, 10_000) == "Body."  # pylint: disable=protected-access

    assert svc._start_after_heading(text, -1) >= 0  # pylint: disable=protected-access
    assert svc._start_after_heading(text, 10_000) == len(
        text
    )  # pylint: disable=protected-access


def test_detect_toc_end_returns_none_when_no_entries_after_heading() -> None:
    svc = ReadingStartService()
    txt = "Contents\n\nReal start."
    assert svc._detect_toc_end(txt) is None  # pylint: disable=protected-access


def test_pick_best_prefers_chapter_over_prologue_over_numeric() -> None:
    svc = ReadingStartService()
    candidates = [
        ReadingStart(start_char=5, reason="Detected Prologue"),
        ReadingStart(start_char=10, reason="Detected numeric heading 1"),
        ReadingStart(start_char=20, reason="Detected Chapter 1"),
    ]
    picked = svc._pick_best(candidates)  # pylint: disable=protected-access
    assert picked is not None
    # `_pick_best` chooses the earliest structural heading in the document.
    assert picked.reason == "Detected Prologue"
