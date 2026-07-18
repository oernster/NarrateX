"""Plan what the narrator speaks, from the document model.

The narrator's counterpart to `render_plan`. The pane decides what to *show*
from `Block.is_displayed`; this decides what to *say* from `Block.is_spoken`.
Both answers come from the same block kinds, so the two views cannot drift
apart: a folio the reader never sees is a folio the narrator never reads.

Chunks are cut from the *source slice* of each block, never from the block's
own cleaned text. A chunk's `start_char` and `end_char` are the coordinates
every other part of the app indexes by (bookmarks, the resume position,
click-to-seek, the audio cache key), so the spoken string has to be the string
those offsets actually point at.

Blocks are not the unit of speech, though. A PDF extractor reports whatever it
grouped visually, which is often a single sentence, so speaking block by block
would breathe between every sentence and synthesise three times the audio. So
consecutive blocks are gathered into a *run* first, and the run is what gets
chunked. A run only ever spans blocks separated by nothing but whitespace, so a
chunk still covers one contiguous stretch of source and still says exactly what
its span claims. Anything skipped, a folio or a running head, leaves real
characters behind in the gap and so ends the run.

A chunk's span is not taken from `ChunkingService`. That service normalises its
input before measuring, so whatever whitespace it collapses shifts every offset
it then reports, and a run gathered from several blocks contains exactly the
line breaks it collapses. Each chunk is instead located back in the run by the
same whitespace-insensitive search that anchors blocks, which makes the span
exact rather than nearly right.
"""

from __future__ import annotations

from typing import Iterator

from voice_reader.domain.document.model import Document
from voice_reader.domain.document.text_index import condense, locate, match_key
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.services.chunking_service import ChunkingService


def _narration_runs(
    document: Document,
    *,
    source_text: str,
    start_offset: int,
) -> Iterator[tuple[int, int]]:
    """Yield the source spans to narrate, in reading order.

    A block ending before the start offset is passed over entirely. The one
    block straddling the offset is entered part-way, which is what a forced
    start (an ideas jump, a click) asks for.

    Consecutive blocks join into one run when they share a kind and nothing but
    whitespace separates them. Kind matters because a heading is its own
    utterance: folding it into the paragraph below would read the title and the
    first sentence as a single breath.
    """

    run_start: int | None = None
    run_end = 0
    run_kind = None

    for block in document.spoken_blocks:
        if block.source_end <= start_offset:
            continue
        start = max(block.source_start, start_offset)

        joins = (
            run_start is not None
            and block.kind is run_kind
            and not source_text[run_end:start].strip()
        )
        if joins:
            run_end = block.source_end
            continue

        if run_start is not None:
            yield run_start, run_end
        run_start, run_end, run_kind = start, block.source_end, block.kind

    if run_start is not None:
        yield run_start, run_end


def build_narration_chunks(
    document: Document,
    *,
    source_text: str,
    chunking_service: ChunkingService,
    start_offset: int = 0,
) -> tuple[TextChunk, ...]:
    """Cut the spoken runs into TTS-sized chunks, in book coordinates.

    Chunk ids are assigned across the whole document rather than per run, so
    they stay the stable sequence the audio cache keys by. A chunk that cannot
    be located in its own run is dropped rather than given a guessed span, on
    the same reasoning as a draft that will not anchor.
    """

    body = str(source_text or "")
    chunks: list[TextChunk] = []

    runs = _narration_runs(
        document,
        source_text=body,
        start_offset=max(0, int(start_offset)),
    )
    for start, end in runs:
        condensed, offsets = condense(body[start:end])
        cursor = 0

        for chunk in chunking_service.chunk_text(body[start:end]):
            placed = locate(
                condensed=condensed,
                offsets=offsets,
                needle=match_key(chunk.text),
                cursor=cursor,
            )
            if placed is None:
                continue

            chunk_start, chunk_end, cursor = placed
            chunks.append(
                TextChunk(
                    chunk_id=len(chunks),
                    text=chunk.text,
                    start_char=start + chunk_start,
                    end_char=start + chunk_end,
                )
            )

    return tuple(chunks)
