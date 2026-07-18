"""Build a document model from markdown source.

Markdown states its own structure, so nothing here guesses. Headings, lists,
quotes and code come straight from the syntax, which is why markdown is the
reference implementation the inferred formats are measured against.

Spans point into the markdown source itself, never into a rewritten copy of it.
The block's `text` carries the readable form (inline syntax stripped, hard
wraps rejoined); the span carries where it came from.
"""

from __future__ import annotations

from voice_reader.domain.document import markdown_lines as lines_module
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.markdown_inline import strip_inline
from voice_reader.domain.document.markdown_lines import Line
from voice_reader.domain.document.model import Block, Document
from voice_reader.domain.document.sectioning import build_toc, group_into_sections


def _block_from(
    *,
    kind: BlockKind,
    run: list[Line],
    text: str,
    level: int = 0,
) -> Block:
    return Block(
        kind=kind,
        source_start=run[0].start,
        source_end=run[-1].end,
        text=text,
        level=level,
    )


class _Scanner:
    """Walks source lines once, emitting blocks in reading order."""

    def __init__(self, *, source: str) -> None:
        self._lines = lines_module.split_lines(source)
        self._blocks: list[Block] = []
        self._paragraph: list[Line] = []
        self._index = 0

    def scan(self) -> tuple[Block, ...]:
        while self._index < len(self._lines):
            line = self._lines[self._index]
            self._index += 1
            self._consume(line)
        self._flush_paragraph()
        return tuple(self._blocks)

    def _consume(self, line: Line) -> None:
        marker = lines_module.fence_marker(line.text)
        if marker is not None:
            self._flush_paragraph()
            self._consume_fenced_code(line, marker=marker)
            return

        if lines_module.is_blank(line.text):
            self._flush_paragraph()
            return

        heading = lines_module.atx_heading(line.text)
        if heading is not None:
            self._flush_paragraph()
            level, title = heading
            self._blocks.append(
                _block_from(
                    kind=BlockKind.HEADING,
                    run=[line],
                    text=strip_inline(title),
                    level=level,
                )
            )
            return

        # A `---` underline is a setext heading when prose precedes it, and a
        # thematic break otherwise. Order decides it.
        setext = lines_module.setext_level(line.text)
        if setext is not None and self._paragraph:
            self._emit_setext_heading(line, level=setext)
            return

        if lines_module.is_thematic_break(line.text):
            self._flush_paragraph()
            self._blocks.append(
                _block_from(kind=BlockKind.SEPARATOR, run=[line], text="")
            )
            return

        if lines_module.block_quote_content(line.text) is not None:
            self._flush_paragraph()
            self._consume_block_quote(line)
            return

        item = lines_module.list_item(line.text)
        if item is not None:
            self._flush_paragraph()
            level, content = item
            self._blocks.append(
                _block_from(
                    kind=BlockKind.LIST_ITEM,
                    run=[line],
                    text=strip_inline(content),
                    level=level,
                )
            )
            return

        self._paragraph.append(line)

    def _emit_setext_heading(self, underline: Line, *, level: int) -> None:
        run = list(self._paragraph) + [underline]
        title = " ".join(line.text.strip() for line in self._paragraph)
        self._paragraph = []
        self._blocks.append(
            _block_from(
                kind=BlockKind.HEADING,
                run=run,
                text=strip_inline(title),
                level=level,
            )
        )

    def _consume_fenced_code(self, opening: Line, *, marker: str) -> None:
        run = [opening]
        body: list[str] = []
        while self._index < len(self._lines):
            line = self._lines[self._index]
            self._index += 1
            run.append(line)
            if lines_module.closes_fence(line.text, marker=marker):
                break
            body.append(line.text)

        # An unterminated fence runs to the end of the source and would
        # otherwise absorb the trailing blank line. Interior blanks are kept.
        while body and not body[-1].strip():
            body.pop()

        self._blocks.append(
            _block_from(
                kind=BlockKind.CODE,
                run=run,
                text="\n".join(body),
            )
        )

    def _consume_block_quote(self, opening: Line) -> None:
        run = [opening]
        body = [str(lines_module.block_quote_content(opening.text))]

        while self._index < len(self._lines):
            line = self._lines[self._index]
            content = lines_module.block_quote_content(line.text)
            if content is None:
                break
            run.append(line)
            body.append(content)
            self._index += 1

        joined = " ".join(part.strip() for part in body if part.strip())
        self._blocks.append(
            _block_from(
                kind=BlockKind.BLOCK_QUOTE,
                run=run,
                text=strip_inline(joined),
            )
        )

    def _flush_paragraph(self) -> None:
        if not self._paragraph:
            return
        run = self._paragraph
        self._paragraph = []
        # Rejoining the hard wraps here is what turns extracted line noise back
        # into a readable, speakable paragraph.
        joined = " ".join(line.text.strip() for line in run)
        text = strip_inline(joined)
        if not text:
            return
        self._blocks.append(_block_from(kind=BlockKind.PARAGRAPH, run=run, text=text))


def scan_blocks(*, source: str) -> tuple[Block, ...]:
    """Return the markdown source as an ordered run of blocks."""

    return _Scanner(source=source).scan()


def build_document(*, source: str) -> Document:
    """Build the full document model for markdown `source`."""

    body = str(source or "")
    blocks = scan_blocks(source=body)
    sections = group_into_sections(blocks=blocks)
    return Document(
        source_length=len(body),
        sections=sections,
        toc=build_toc(sections=sections),
    )
