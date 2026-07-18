"""Click-to-seek across the render plan's coordinate boundary."""

from __future__ import annotations

from types import SimpleNamespace

from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.ui._ui_controller_seek import seek_to_char_offset

from tests.ui._seek_testkit import NavFake, make_controller


def _controller(*, text: str = "x", nav=None, svc=None, voice=None):
    return make_controller(text=text, nav=nav, svc=svc, voice=voice)


def _plan_from(source: str):
    from voice_reader.domain.document.plain_text import build_document
    from voice_reader.domain.document.render_plan import build_render_plan

    return build_render_plan(build_document(source=source))


def test_seek_translates_pane_coordinates_into_book_offsets() -> None:
    # The pane hides the contents and folios, so a click position is not a
    # book offset. Without translation the seek lands in the wrong place.
    source = (
        "CONTENTS\n\nPrologue . . . . . . . . . . 2\n\nChapter 1\n\nThe real text.\n"
    )
    plan = _plan_from(source)

    chunks = [TextChunk(chunk_id=0, text="The real text.", start_char=0, end_char=14)]
    c = _controller(text=source, nav=NavFake(chunks=chunks))
    c.window.render_plan = plan
    c.window.reader_positions = None
    c.narration_service.book = SimpleNamespace(normalized_text=source)
    c.narration_service.loaded_book = lambda: c.narration_service.book

    target = plan.blocks[-1]
    seek_to_char_offset(c, target.render_start)

    assert c.narration_service.prepare_calls != []


def test_seek_without_a_render_plan_uses_the_pane_text_directly() -> None:
    chunks = [TextChunk(chunk_id=0, text="hello", start_char=0, end_char=5)]
    c = _controller(text="hello", nav=NavFake(chunks=chunks))
    c.window.render_plan = None

    seek_to_char_offset(c, 1)

    assert c.narration_service.prepare_calls != []


def test_seek_converts_utf16_positions_before_consulting_the_plan() -> None:
    source = "Chapter 1\n\nThe real text.\n"
    plan = _plan_from(source)

    class Positions:
        def __init__(self) -> None:
            self.seen: list[int] = []

        def to_index(self, position: int) -> int:
            self.seen.append(position)
            return position

    positions = Positions()
    chunks = [TextChunk(chunk_id=0, text="The real text.", start_char=0, end_char=14)]
    c = _controller(text=source, nav=NavFake(chunks=chunks))
    c.window.render_plan = plan
    c.window.reader_positions = positions
    c.narration_service.loaded_book = lambda: SimpleNamespace(normalized_text=source)

    seek_to_char_offset(c, 3)

    assert positions.seen == [3]


def test_seek_survives_a_narration_service_with_no_loaded_book() -> None:
    source = "Chapter 1\n\nThe real text.\n"
    c = _controller(text=source, nav=NavFake(chunks=[]))
    c.window.render_plan = _plan_from(source)
    c.window.reader_positions = None

    seek_to_char_offset(c, 0)

    assert c.narration_service.prepare_calls == []
