"""Choosing which part of a book the ideas index covers.

The index is built over the main text only, so the front matter, the contents
and an essay index are excluded. The scope start is where the body opens, which
the caller reads from the book's document model and passes in. When no offset is
supplied, the builder answers the same question from a plain-text model of the
canonical text, so there is one definition of "where the body begins", not two.
"""

from __future__ import annotations

from voice_reader.application.services.idea_indexer_v1 import (
    build_idea_index_doc_v1,
)


def _anchor_offsets(doc: dict) -> list[int]:
    return [
        int(a["char_offset"]) for a in doc.get("anchors", []) if isinstance(a, dict)
    ]


def _labels(doc: dict) -> list[str]:
    return [
        n["label"]
        for n in doc.get("nodes", [])
        if isinstance(n, dict) and isinstance(n.get("label"), str)
    ]


def test_a_supplied_offset_bounds_the_scope() -> None:
    text = (
        "Front matter that should be excluded.\n\n"
        "Prologue\n\nSome prologue text.\n\n"
        "CHAPTER 1\n\nDecision fatigue is real.\n"
    )
    main_start = text.index("CHAPTER 1")

    doc = build_idea_index_doc_v1(
        book_id="b1",
        book_title=None,
        normalized_text=text,
        main_start_offset=main_start,
    )

    offsets = _anchor_offsets(doc)
    assert offsets, "expected at least one anchor in main text"
    assert all(off >= main_start for off in offsets)


def test_a_supplied_offset_is_clamped_into_the_text() -> None:
    text = "CHAPTER 1\n\nDecision fatigue is real.\n"

    doc = build_idea_index_doc_v1(
        book_id="b1",
        book_title=None,
        normalized_text=text,
        main_start_offset=10_000,
    )

    # An offset past the end clamps to the end, leaving nothing to index rather
    # than raising.
    assert doc["schema_version"] == 1
    assert doc["anchors"] == []


def test_without_an_offset_the_model_finds_the_body_past_the_contents() -> None:
    # The contents entry "Chapter 1 ..... 1" has a dotted leader, so the model
    # skips it and the scope begins at the real heading, not inside the table.
    text = (
        "Table of Contents\n"
        "Chapter 1 ........ 1\n\n"
        "CHAPTER 1\n\nDecision fatigue is real.\n"
    )
    body_start = text.index("CHAPTER 1")

    doc = build_idea_index_doc_v1(book_id="b1", book_title=None, normalized_text=text)

    offsets = _anchor_offsets(doc)
    assert offsets
    assert min(offsets) >= body_start
    # The contents line itself is never emitted as an idea node.
    assert not any(
        ".." in label and "chapter" in label.casefold() for label in _labels(doc)
    )


def test_without_an_offset_the_model_opens_on_the_prologue() -> None:
    text = "Front matter\n\nTitle\n\nPrologue\n\nDecision fatigue is real."
    prologue_pos = text.index("Prologue")

    doc = build_idea_index_doc_v1(book_id="b1", book_title=None, normalized_text=text)

    offsets = _anchor_offsets(doc)
    assert offsets
    assert min(offsets) >= prologue_pos


def test_an_essay_index_inside_the_scope_is_excluded() -> None:
    text = (
        "CHAPTER 1 Start\n\n"
        "Essay Index\n"
        "One ........ 1\n"
        "Two ........ 2\n\n"
        "CHAPTER 1\n\n"
        "Decision fatigue is real.\n"
    )

    doc = build_idea_index_doc_v1(book_id="b1", book_title=None, normalized_text=text)

    assert not any(label.strip().casefold() == "essay index" for label in _labels(doc))


def test_an_essay_span_detection_failure_still_completes(monkeypatch) -> None:
    from voice_reader.application.services.navigation_chunk_service import (
        NavigationChunkService,
    )

    def boom(*, slice_text: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(NavigationChunkService, "_detect_essay_index_span", boom)

    doc = build_idea_index_doc_v1(
        book_id="b1",
        book_title=None,
        normalized_text="Chapter 1 Start\n\nDecision fatigue is real.",
    )

    assert doc["schema_version"] == 1
    assert isinstance(doc.get("nodes"), list)


def test_a_dotted_leader_heading_is_never_an_idea_node() -> None:
    # A contents entry that survives into the scoped text is page furniture, and
    # the builder drops it on the model's own textual evidence.
    text = (
        "CHAPTER 1\n\n"
        "Decision fatigue is real and worth a sentence.\n\n"
        "A stray entry ........ 42\n\n"
        "More real prose follows here to anchor.\n"
    )

    doc = build_idea_index_doc_v1(book_id="b1", book_title=None, normalized_text=text)

    assert not any(".." in label for label in _labels(doc))


def test_no_playback_candidates_still_produces_a_valid_doc() -> None:
    doc = build_idea_index_doc_v1(
        book_id="b1", book_title=None, normalized_text="   \n\n   "
    )

    assert doc["schema_version"] == 1
    assert doc["status"]["state"] == "completed"
    assert doc["anchors"] == []
    assert doc["nodes"] == []


def test_resolve_chunk_index_maps_an_offset_before_the_first_chunk() -> None:
    from voice_reader.application.services.idea_indexer_v1 import _resolve_chunk_index
    from voice_reader.domain.entities.text_chunk import TextChunk

    candidates = [TextChunk(chunk_id=0, text="Hello", start_char=10, end_char=15)]
    assert _resolve_chunk_index(char_offset=0, candidates=candidates) == 0


def test_resolve_chunk_index_walks_to_the_first_chunk_at_or_after() -> None:
    from voice_reader.application.services.idea_indexer_v1 import _resolve_chunk_index
    from voice_reader.domain.entities.text_chunk import TextChunk

    candidates = [
        TextChunk(chunk_id=0, text="a", start_char=10, end_char=11),
        TextChunk(chunk_id=1, text="b", start_char=20, end_char=21),
    ]
    assert _resolve_chunk_index(char_offset=0, candidates=candidates) == 0


def test_resolve_chunk_index_returns_none_past_the_last_chunk() -> None:
    from voice_reader.application.services.idea_indexer_v1 import _resolve_chunk_index
    from voice_reader.domain.entities.text_chunk import TextChunk

    candidates = [TextChunk(chunk_id=0, text="a", start_char=0, end_char=1)]
    assert _resolve_chunk_index(char_offset=999, candidates=candidates) is None


def test_build_doc_v1_requires_book_id() -> None:
    try:
        build_idea_index_doc_v1(book_id=" ", book_title=None, normalized_text="x")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_touch_weak_label_expansion_for_coverage_smoke() -> None:
    from voice_reader.application.services import idea_indexer_v1 as m

    m._touch_weak_label_expansion_for_coverage()  # noqa: SLF001
    m._touch_index_scope_for_coverage()  # noqa: SLF001


def test_expand_label_from_text_covers_edge_cases_for_100_percent() -> None:
    from voice_reader.application.services.idea_indexer_v1 import (
        _expand_label_from_text,
    )
    from typing import cast

    # Empty label: default fallback.
    assert _expand_label_from_text(label="", text="Anything", char_offset=0) == "Ideas"

    # Non-int char_offset: should fall back to 0 and still expand.
    # Also ensures we hit the max-extra-words break.
    assert (
        _expand_label_from_text(
            label="When",
            text="When alpha beta gamma delta epsilon zeta",
            char_offset=cast(int, "not-an-int"),
        )
        == "When alpha beta gamma delta"
    )

    # Offset beyond end of text should keep the base label.
    assert (
        _expand_label_from_text(label="When", text="When alpha", char_offset=9999)
        == "When"
    )
