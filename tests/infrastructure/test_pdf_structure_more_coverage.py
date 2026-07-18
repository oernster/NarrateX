"""Cover the layout-aware PDF walk without opening a real PDF.

PyMuPDF's `dict` mode is a plain nested dictionary, so the walk can be driven
by hand-built pages. The classifier it feeds is pure and tested separately.
"""

from __future__ import annotations

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.infrastructure.books import pdf_structure

_PAGE_HEIGHT = 100.0
_BOLD_FLAG = 1 << 4


class FakeRect:
    def __init__(self, height: float) -> None:
        self.height = height


class FakePage:
    """One page, returning the `dict` payload it was built with."""

    def __init__(self, content, *, height: float = _PAGE_HEIGHT) -> None:
        self.rect = FakeRect(height)
        self._content = content

    def get_text(self, mode: str):
        assert mode == "dict"
        return self._content


def _span(text: str, *, size: float = 10.0, bold: bool = False) -> dict:
    return {"text": text, "size": size, "flags": _BOLD_FLAG if bold else 0}


def _line(spans: list[dict], *, bbox=(0.0, 40.0, 0.0, 50.0)) -> dict:
    return {"spans": spans, "bbox": bbox}


def _text_block(lines: list[dict]) -> dict:
    return {"type": 0, "lines": lines}


def test_line_carries_size_weight_and_position() -> None:
    page = FakePage(
        {"blocks": [_text_block([_line([_span("Deci", size=10.0), _span("sion")])])]}
    )

    (line,) = pdf_structure.lines_from_document([page])

    assert line.text == "Decision"
    assert line.size == 10.0
    assert line.bold is False
    assert line.top == 40.0
    assert line.bottom == 50.0
    assert line.page_index == 0
    assert line.page_height == _PAGE_HEIGHT
    assert line.block_index == 0


def test_largest_span_size_and_any_bold_span_win() -> None:
    page = FakePage(
        {
            "blocks": [
                _text_block(
                    [
                        _line(
                            [
                                _span("small", size=9.0),
                                _span(" big", size=18.0, bold=True),
                            ]
                        )
                    ]
                )
            ]
        }
    )

    (line,) = pdf_structure.lines_from_document([page])

    assert line.size == 18.0
    assert line.bold is True


def test_blank_lines_are_dropped() -> None:
    page = FakePage(
        {"blocks": [_text_block([_line([_span("   ")]), _line([_span("kept")])])]}
    )

    lines = pdf_structure.lines_from_document([page])

    assert [line.text for line in lines] == ["kept"]


def test_span_without_text_contributes_nothing() -> None:
    page = FakePage({"blocks": [_text_block([_line([{"size": 12.0}, _span("only")])])]})

    (line,) = pdf_structure.lines_from_document([page])

    assert line.text == "only"
    assert line.size == 12.0


def test_line_without_bbox_sits_at_the_origin() -> None:
    page = FakePage({"blocks": [_text_block([{"spans": [_span("bare")]}])]})

    (line,) = pdf_structure.lines_from_document([page])

    assert (line.top, line.bottom) == (0.0, 0.0)


def test_image_blocks_are_skipped() -> None:
    image_block = {"type": 1, "lines": [_line([_span("caption baked into art")])]}
    page = FakePage({"blocks": [image_block, _text_block([_line([_span("prose")])])]})

    lines = pdf_structure.lines_from_document([page])

    assert [line.text for line in lines] == ["prose"]


def test_block_without_a_type_is_read_as_text() -> None:
    page = FakePage({"blocks": [{"lines": [_line([_span("untyped")])]}]})

    (line,) = pdf_structure.lines_from_document([page])

    assert line.text == "untyped"


def test_missing_blocks_and_lines_are_tolerated() -> None:
    empty_page = FakePage({})
    null_blocks = FakePage({"blocks": None})
    null_lines = FakePage({"blocks": [{"type": 0, "lines": None}]})

    assert (
        pdf_structure.lines_from_document([empty_page, null_blocks, null_lines]) == ()
    )


def test_page_and_block_indices_track_the_walk() -> None:
    first = FakePage(
        {
            "blocks": [
                _text_block([_line([_span("one")])]),
                _text_block([_line([_span("two")])]),
            ]
        }
    )
    second = FakePage({"blocks": [_text_block([_line([_span("three")])])]})

    lines = pdf_structure.lines_from_document([first, second])

    assert [(line.page_index, line.block_index) for line in lines] == [
        (0, 0),
        (0, 1),
        (1, 0),
    ]


def test_drafts_come_back_classified_from_the_walk() -> None:
    page = FakePage(
        {
            "blocks": [
                _text_block([_line([_span("A Larger Title", size=20.0)])]),
                _text_block([_line([_span("Body text set at the usual size.")])]),
            ]
        }
    )

    drafts = pdf_structure.drafts_from_document([page])

    assert [draft.kind for draft in drafts] == [
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
    ]


def test_layout_failure_leaves_the_book_unstructured() -> None:
    class ExplodingPage:
        @property
        def rect(self):
            raise RuntimeError("layout unavailable")

    assert pdf_structure.drafts_from_document([ExplodingPage()]) == ()
