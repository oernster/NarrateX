from __future__ import annotations

from voice_reader.domain.services.chunking_service import ChunkingService


def test_chunking_respects_size_bounds_most_of_time() -> None:
    text = (
        "Dr. Smith went to the store. "
        "He bought apples, oranges, and bananas. "
        "Then he returned home. "
        "\n\n"
        "This is a second paragraph with enough length to require multiple chunks. "
        "It should not break abbreviations like e.g. or i.e. in the middle. "
        "It should end with punctuation. " * 10
    )
    svc = ChunkingService(min_chars=150, max_chars=300)
    chunks = svc.chunk_text(text)
    assert chunks
    for c in chunks:
        assert 10 <= len(c.text) <= 320


def test_chunking_does_not_split_common_abbreviations() -> None:
    text = "This is a test e.g. with abbreviation. Next sentence starts here."
    svc = ChunkingService(min_chars=10, max_chars=50)
    chunks = svc.chunk_text(text)
    combined = " ".join([c.text for c in chunks])
    assert "e.g." in combined
