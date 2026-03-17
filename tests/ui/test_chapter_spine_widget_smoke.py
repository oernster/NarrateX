from __future__ import annotations


def test_chapter_spine_widget_smoke(qapp) -> None:
    from voice_reader.ui.chapter_spine_widget import ChapterSpineWidget
    from voice_reader.domain.entities.chapter import Chapter

    w = ChapterSpineWidget()
    w.resize(22, 400)
    w.show()
    qapp.processEvents()

    w.set_chapters(
        [
            Chapter(title="Chapter 1", char_offset=0, chunk_index=0),
            Chapter(title="Chapter 2", char_offset=1000, chunk_index=4),
        ]
    )
    w.set_current_chapter(Chapter(title="Chapter 1", char_offset=0, chunk_index=0))
    # Playhead should be independently settable (continuous playback position).
    w.set_playhead_char_offset(250)
    qapp.processEvents()

    # Exercise edge branch: too much padding collapses rail.
    w._set_style_for_tests(padding=10_000)  # noqa: SLF001
    qapp.processEvents()


def test_chapter_spine_widget_y_positions_single_chapter(qapp) -> None:
    del qapp
    from voice_reader.ui.chapter_spine_widget import ChapterSpineWidget
    from voice_reader.domain.entities.chapter import Chapter

    w = ChapterSpineWidget()
    w.set_chapters([Chapter(title="Chapter 1", char_offset=0, chunk_index=0)])
    assert w._y_positions(top=0, bottom=10) == [5]  # noqa: SLF001


def test_chapter_spine_widget_playhead_clamps_to_range(qapp) -> None:
    del qapp
    from voice_reader.ui.chapter_spine_widget import ChapterSpineWidget
    from voice_reader.domain.entities.chapter import Chapter

    w = ChapterSpineWidget()
    w.set_chapters(
        [
            Chapter(title="Chapter 1", char_offset=0, chunk_index=0),
            Chapter(title="Chapter 2", char_offset=1000, chunk_index=1),
        ]
    )

    # Below first chapter -> top.
    assert (
        w._y_for_char_offset(top=10, bottom=110, char_offset=-50) == 10
    )  # noqa: SLF001
    # Above last chapter -> bottom.
    assert (
        w._y_for_char_offset(top=10, bottom=110, char_offset=50_000) == 110
    )  # noqa: SLF001


def test_chapter_spine_widget_y_for_char_offset_single_or_empty_returns_midpoint(
    qapp,
) -> None:
    """Cover the small edge branch in [`ChapterSpineWidget._y_for_char_offset()`](voice_reader/ui/chapter_spine_widget.py:152)."""

    del qapp
    from voice_reader.ui.chapter_spine_widget import ChapterSpineWidget
    from voice_reader.domain.entities.chapter import Chapter

    w = ChapterSpineWidget()

    # No chapters.
    assert w._y_for_char_offset(top=10, bottom=110, char_offset=0) == 60  # noqa: SLF001

    # One chapter.
    w.set_chapters([Chapter(title="Only", char_offset=0, chunk_index=0)])
    assert w._y_for_char_offset(top=10, bottom=110, char_offset=0) == 60  # noqa: SLF001
