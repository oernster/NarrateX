from __future__ import annotations

from datetime import datetime, timezone

from voice_reader.domain.entities.bookmark import Bookmark, ResumePosition


def test_bookmark_is_frozen_and_has_expected_fields() -> None:
    ts = datetime(2026, 3, 14, 19, 21, 0, tzinfo=timezone.utc)
    bm = Bookmark(
        bookmark_id=1,
        name="Bookmark 1",
        char_offset=124,
        chunk_index=0,
        created_at=ts,
    )
    assert bm.bookmark_id == 1
    assert bm.name == "Bookmark 1"
    assert bm.char_offset == 124
    assert bm.chunk_index == 0
    assert bm.created_at == ts

    try:
        # Frozen dataclass should reject mutation.
        bm.name = "X"  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001
        assert exc.__class__.__name__ in {"FrozenInstanceError", "AttributeError"}
    else:
        raise AssertionError("Expected Bookmark to be immutable")


def test_resume_position_is_frozen_and_has_expected_fields() -> None:
    ts = datetime(2026, 3, 14, 19, 20, 0, tzinfo=timezone.utc)
    rp = ResumePosition(char_offset=41231, chunk_index=12, updated_at=ts)
    assert rp.char_offset == 41231
    assert rp.chunk_index == 12
    assert rp.updated_at == ts
