from __future__ import annotations


def test_bookmark_repository_protocol_importable() -> None:
    from voice_reader.domain.interfaces.bookmark_repository import (  # noqa: F401
        BookmarkRepository,
    )
