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

