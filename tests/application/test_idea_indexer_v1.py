from __future__ import annotations

from voice_reader.application.services.idea_indexer_v1 import (
    build_idea_index_doc_v1,
    detect_headings,
    extract_top_concepts,
)


def test_detect_headings_finds_chapter_lines_with_offsets() -> None:
    text = "Intro\n\nChapter I The Beginning\nSome text\n\nCHAPTER 2 Next\n"
    hs = detect_headings(text=text)
    assert hs
    labels = [h[0] for h in hs]
    assert any("Chapter" in s or "CHAPTER" in s for s in labels)
    assert all(isinstance(h[1], int) for h in hs)


def test_detect_headings_skips_unreasonable_lines() -> None:
    # Too long and ends with '.' should be ignored.
    long = "X" * 200
    text = f"{long}.\n\nCHAPTER 1 Start\n"
    hs = detect_headings(text=text)
    assert any("CHAPTER" in h[0] for h in hs)


def test_extract_top_concepts_ignores_stopwords_and_short_tokens() -> None:
    text = "the the the and and to to of in a an is are be been"
    assert extract_top_concepts(text=text, max_concepts=5) == []


def test_extract_top_concepts_is_bounded_and_has_offsets() -> None:
    text = "Decision decision decision fatigue fatigue choices choices choices."
    concepts = extract_top_concepts(text=text, max_concepts=3)
    assert 1 <= len(concepts) <= 3
    assert all(isinstance(off, int) for _label, off in concepts)


def test_build_doc_v1_has_minimal_schema_and_navigable_anchor() -> None:
    doc = build_idea_index_doc_v1(
        book_id="b1",
        book_title="T",
        normalized_text="Chapter 1 Start\n\nDecision fatigue is real.",
    )

    assert doc["schema_version"] == 1
    assert doc["status"]["state"] == "completed"
    assert isinstance(doc["nodes"], list)
    assert isinstance(doc["anchors"], list)
    assert doc["nodes"], "expected at least the Top Concepts node"
    assert doc["anchors"], "expected at least one anchor"
    # Validate cross-reference.
    aid = doc["nodes"][0]["primary_anchor_id"]
    assert any(a["anchor_id"] == aid for a in doc["anchors"])


def test_build_doc_v1_handles_no_playback_candidates() -> None:
    """If the text sanitizes to nothing, doc should still be well-formed."""

    doc = build_idea_index_doc_v1(book_id="b1", book_title=None, normalized_text="   \n\n   ")
    assert doc["schema_version"] == 1
    assert doc["status"]["state"] == "completed"
    assert doc["anchors"] == []
    assert doc["nodes"] == []


def test_resolve_chunk_index_fallback_path_is_used_when_offset_before_first_chunk() -> None:
    # Import the private helper intentionally for coverage: it encodes a key
    # navigation guarantee.
    from voice_reader.application.services.idea_indexer_v1 import _resolve_chunk_index
    from voice_reader.domain.entities.text_chunk import TextChunk

    candidates = [TextChunk(chunk_id=0, text="Hello", start_char=10, end_char=15)]
    assert _resolve_chunk_index(char_offset=0, candidates=candidates) == 0


def test_resolve_chunk_index_path_for_offsets_before_start_is_reachable() -> None:
    # Ensure the resolver path "start_char >= char_offset" is exercised.
    from voice_reader.application.services.idea_indexer_v1 import _resolve_chunk_index
    from voice_reader.domain.entities.text_chunk import TextChunk

    candidates = [
        TextChunk(chunk_id=0, text="a", start_char=10, end_char=11),
        TextChunk(chunk_id=1, text="b", start_char=20, end_char=21),
    ]
    assert _resolve_chunk_index(char_offset=0, candidates=candidates) == 0


def test_resolve_chunk_index_returns_none_when_offset_after_last_chunk() -> None:
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

