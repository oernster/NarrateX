"""Composition root for the book-load child process.

Loading a large book is CPU-bound pure Python, so running it on a thread
starves the Qt event loop through the GIL and the window freezes anyway.
The parse therefore runs in a separate process, exactly as Ideas indexing
does, and the parent waits on the result queue with the GIL released.

This module wires infrastructure (converter, parser, repository, cover
extraction) together with application services (navigation chunks, chapter
index), which only a composition root may do. It is whitelisted alongside
`app.py` and `voice_reader/bootstrap.py` in the structural tests and must
not be imported by layer code; the UI receives `load_in_subprocess` by
constructor injection from the entrypoint.
"""

from __future__ import annotations

import multiprocessing as mp
import queue
from pathlib import Path
from typing import Any

# How long the parent sleeps between liveness checks while the child works.
# Short enough that a crashed child is noticed promptly; long enough that
# polling costs nothing.
_RESULT_POLL_SECONDS = 0.5


def run_worker(*, out_q: Any, payload: dict) -> None:
    """Child-process entry: load the book and put one terminal event.

    Always puts exactly one event: `{"type": "result", ...}` carrying the
    parsed book with everything the UI needs, or `{"type": "error", ...}`.
    """

    try:
        out_q.put({"type": "result", **_compute(payload)})
    except Exception as exc:
        try:
            out_q.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        except Exception:
            return


def _compute(payload: dict) -> dict:
    from voice_reader.application.services.chapter_index_service import (
        ChapterIndexService,
    )
    from voice_reader.application.services.navigation_chunk_service import (
        NavigationChunkService,
    )
    from voice_reader.domain.document.reading_start import contents_end_offset
    from voice_reader.domain.document.render_plan import build_render_plan
    from voice_reader.domain.services.chunking_service import ChunkingService
    from voice_reader.infrastructure.books.converter import CalibreConverter
    from voice_reader.infrastructure.books.cover_extractor import CoverExtractor
    from voice_reader.infrastructure.books.parser import BookParser
    from voice_reader.infrastructure.books.repository import LocalBookRepository

    path = Path(str(payload["path"]))
    temp_books_dir = Path(str(payload["temp_books_dir"]))

    repo = LocalBookRepository(
        converter=CalibreConverter(temp_books_dir=temp_books_dir),
        parser=BookParser(),
    )
    book = repo.load(path)

    # The render plan, or None when raw text should win (unstructured or
    # empty plans fall back to the plain text in the UI).
    plan = None
    document = book.document
    if document is not None:
        candidate = build_render_plan(
            document,
            body_start=contents_end_offset(document),
        )
        if candidate.text.strip():
            plan = candidate

    # Chunk boundaries must match the ones narration will build, so the
    # chunker is configured with the exact values the running app uses,
    # passed through the payload rather than duplicated here.
    chunks, start = NavigationChunkService(
        chunking_service=ChunkingService(
            min_chars=int(payload["chunk_min_chars"]),
            max_chars=int(payload["chunk_max_chars"]),
        ),
    ).build_chunks(
        book_text=book.normalized_text,
        document=book.document_model,
    )

    service = ChapterIndexService()
    chapters = []
    if document is not None and document.sections:
        chapters = service.build_index_from_sections(
            sections=document.sections,
            chunks=chunks,
            min_char_offset=contents_end_offset(document),
        )
    if not chapters:
        chapters = service.build_index(
            book.normalized_text,
            chunks=chunks,
            min_char_offset=int(start.start_char),
        )

    try:
        cover = CoverExtractor().extract_cover_bytes(path)
    except Exception:  # pragma: no cover
        cover = None

    return {
        "book": book,
        "plan": plan,
        "chapters": tuple(chapters),
        "start_char": int(start.start_char),
        "cover": cover,
    }


def load_in_subprocess(
    *,
    path: Path,
    temp_books_dir: Path,
    chunk_min_chars: int,
    chunk_max_chars: int,
    _target: Any = run_worker,
) -> dict:
    """Parent-side helper: spawn the load and block until its one event.

    Blocking on the queue releases the GIL, so the calling thread costs the
    UI nothing while the child parses. A child that dies without reporting
    is detected by the liveness check instead of hanging the caller.
    """

    ctx = mp.get_context("spawn")
    out_q = ctx.Queue()
    p = ctx.Process(
        target=_target,
        kwargs={
            "out_q": out_q,
            "payload": {
                "path": str(path),
                "temp_books_dir": str(temp_books_dir),
                "chunk_min_chars": int(chunk_min_chars),
                "chunk_max_chars": int(chunk_max_chars),
            },
        },
    )
    p.daemon = True
    p.start()

    try:
        while True:
            try:
                return out_q.get(timeout=_RESULT_POLL_SECONDS)
            except queue.Empty:
                if not p.is_alive():
                    # The child can exit between putting its event and this
                    # check, so drain once more before declaring failure.
                    try:
                        return out_q.get(timeout=_RESULT_POLL_SECONDS)
                    except queue.Empty:
                        return {
                            "type": "error",
                            "message": "the book load process ended without a result",
                        }
    finally:
        try:
            p.join(timeout=1.0)
        except Exception:  # pragma: no cover
            pass
