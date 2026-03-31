from __future__ import annotations

from voice_reader.application.text_patterns import looks_like_wrapped_toc_entry


def test_looks_like_wrapped_toc_entry_true_for_leader_only_next_line() -> None:
    assert looks_like_wrapped_toc_entry(line="Experience", next_line=". . . . .") is True


def test_looks_like_wrapped_toc_entry_true_for_page_only_next_line() -> None:
    assert looks_like_wrapped_toc_entry(line="Experience", next_line="11") is True


def test_looks_like_wrapped_toc_entry_false_for_blank_next_line() -> None:
    assert looks_like_wrapped_toc_entry(line="Experience", next_line="") is False


def test_looks_like_wrapped_toc_entry_false_for_blank_label() -> None:
    assert looks_like_wrapped_toc_entry(line="", next_line="11") is False


def test_looks_like_wrapped_toc_entry_false_for_normal_text_next_line() -> None:
    assert (
        looks_like_wrapped_toc_entry(line="Experience", next_line="This is normal prose")
        is False
    )

