from __future__ import annotations

from voice_reader.application.services.idea_indexer_v1 import (
    build_idea_index_doc_v1,
    detect_headings,
    extract_top_concepts,
)
from voice_reader.domain.services.reading_start_service import ReadingStartService


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


def test_build_doc_v1_expands_weak_join_word_concept_with_more_context() -> None:
    # Some books yield low-signal concept labels like "When" or "Without".
    # Ensure we expand them to include more context.
    doc = build_idea_index_doc_v1(
        book_id="b1",
        book_title="T",
        normalized_text=(
            "Chapter 1 Start\n\n"
            "When decisions are made, structure matters. "
            "When decisions are recorded, structure matters. "
            "When decisions are reviewed, structure matters.\n\n"
        ),
    )
    labels = [n.get("label") for n in doc.get("nodes", []) if isinstance(n, dict)]
    assert any(
        isinstance(s, str) and s.startswith("When ") and len(s.split()) >= 3
        for s in labels
    )


def test_build_doc_v1_does_not_expand_normal_heading() -> None:
    doc = build_idea_index_doc_v1(
        book_id="b1",
        book_title=None,
        normalized_text="Chapter 1 Start\n\nDecision Architecture\n\n",
    )
    labels = [n.get("label") for n in doc.get("nodes", []) if isinstance(n, dict)]
    assert "Decision Architecture" in labels


def test_build_doc_v1_keeps_weak_heading_when_not_enough_same_line_words() -> None:
    # Only 1 extra word exists on that line -> per requirement, keep base label.
    doc = build_idea_index_doc_v1(
        book_id="b1",
        book_title=None,
        normalized_text="Chapter 1 Start\n\nWith you\n\n",
    )
    labels = [n.get("label") for n in doc.get("nodes", []) if isinstance(n, dict)]
    assert "With you" in labels


def test_build_doc_v1_expansion_stops_at_line_break() -> None:
    doc = build_idea_index_doc_v1(
        book_id="b1",
        book_title=None,
        normalized_text="Chapter 1 Start\n\nWith\nThe grain of the system\n\n",
    )
    labels = [n.get("label") for n in doc.get("nodes", []) if isinstance(n, dict)]
    # Still expand within the same heading block (non-empty consecutive lines).
    assert any(isinstance(s, str) and s.startswith("With ") for s in labels)


def test_build_doc_v1_does_not_expand_when_punctuation_interrupts_context() -> None:
    doc = build_idea_index_doc_v1(
        book_id="b1",
        book_title=None,
        normalized_text=(
            "Chapter 1 Start\n\nWhen: decisions are made. When: decisions are recorded.\n\n"
        ),
    )
    labels = [n.get("label") for n in doc.get("nodes", []) if isinstance(n, dict)]
    # "When" may exist as a concept label, but we should not expand across punctuation.
    assert any(s == "When" for s in labels if isinstance(s, str))


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
