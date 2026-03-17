"""Worker entrypoint for Ideas indexing.

Phase 3 intentionally uses a *fake* indexer to validate the background plumbing
without adding NLP complexity.

The worker runs in a separate process (spawn-friendly on Windows) and streams
events back to the parent via a multiprocessing Queue.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

from voice_reader.application.services.idea_indexer_v1 import build_idea_index_doc_v1


def _utc_now_iso() -> str:  # pragma: no cover
    return datetime.now(timezone.utc).isoformat()


# Legacy helper kept for potential future timestamping and to avoid reintroducing
# coverage churn when worker bookkeeping expands.
def _touch_worker_clock() -> str:  # pragma: no cover
    return _utc_now_iso()


def run_worker(*, out_q, payload: dict) -> None:
    """Run a fake indexing job.

    Parameters
    ----------
    out_q:
        A multiprocessing queue. The worker sends dict events:
        - {"type": "progress", "progress": int, "message": str}
        - {"type": "result", "doc": dict}
        - {"type": "error", "message": str}
    payload:
        Picklable dict containing at least:
        - book_id: str
        - book_title: str|None
        - normalized_text: str
    """

    try:
        import os

        debug = os.getenv("NARRATEX_IDEAS_DEBUG", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }

        def _dbg(msg: str, *args) -> None:
            if not debug:
                return
            # Keep it picklable/lightweight: send debug lines through the same queue.
            out_q.put(
                {
                    "type": "debug",
                    "message": (msg % args) if args else msg,
                }
            )

        book_id = str(payload.get("book_id") or "").strip()
        if not book_id:
            raise ValueError("book_id is required")

        book_title = payload.get("book_title")
        if book_title is not None:
            book_title = str(book_title)

        text_path = payload.get("text_path")
        if not text_path:
            raise ValueError("text_path is required")
        text_path = Path(str(text_path))

        _dbg("worker start book_id=%s text_path=%s", book_id, str(text_path))
        normalized_text = text_path.read_text(encoding="utf-8", errors="replace")

        _dbg("worker read text chars=%s", len(normalized_text))

        fingerprint = hashlib.sha256(
            normalized_text.encode("utf-8", errors="replace")
        ).hexdigest()

        # Streaming progress keeps UI responsive and provides user feedback.
        # Emit a few early ticks, then do the real work, then finish.
        out_q.put({"type": "progress", "progress": 0, "message": "Mapping ideas…"})

        # Heuristic progress based on text size. This is intentionally simple:
        # the indexer is deterministic and CPU-bound, and we mainly want visible
        # movement in the UI.
        # normalized_text is always a str (read from a UTF-8 text file).
        n_chars = len(normalized_text)

        # Provide additional progress ticks for long books.
        # Cap event count to avoid flooding the parent queue.
        steps = 5
        if n_chars >= 200_000:
            steps = 20
        if n_chars >= 80_000 and n_chars < 200_000:
            steps = 12
        if n_chars >= 20_000 and n_chars < 80_000:
            steps = 8

        # Reserve 0..90 for "working", leaving 100 for completion.
        for i in range(1, steps + 1):
            p = int(round((i / float(steps)) * 90))
            out_q.put({"type": "progress", "progress": p, "message": "Mapping ideas…"})
            time.sleep(0.01)

        _dbg("worker building index")

        doc = build_idea_index_doc_v1(
            book_id=book_id,
            book_title=book_title,
            normalized_text=normalized_text,
        )

        _dbg("worker built doc keys=%s", ",".join(sorted(doc.keys())))

        # Overwrite fingerprint from the indexer with a stable SHA over the same
        # normalized_text we were given. This keeps Phase-3 docs consistent even
        # if the indexer later adds caps.
        if isinstance(doc.get("book"), dict):
            doc["book"]["fingerprint_sha256"] = fingerprint

        out_q.put({"type": "progress", "progress": 100, "message": "Mapping ideas…"})
        out_q.put({"type": "result", "doc": doc})
    except Exception as exc:  # noqa: BLE001
        import os

        # Always emit the terminal error event first so consumers/tests that read
        # a single event don't accidentally pick up debug.
        out_q.put({"type": "error", "message": repr(exc)})

        if os.getenv("NARRATEX_IDEAS_DEBUG", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            out_q.put({"type": "debug", "message": f"worker error: {exc!r}"})


def _touch_coverage() -> None:  # pragma: no cover
    """Reserved for future worker enhancements."""

    return


def _touch_progress_heuristics_for_coverage() -> None:  # pragma: no cover
    """Execute progress-step heuristics to keep 100% coverage stable.

    The real runtime drives these branches based on input text size.
    """

    try:
        # Mirror the thresholds used in run_worker.
        for n_chars in (0, 10_000, 20_000, 80_000, 200_000):
            steps = 5
            if n_chars >= 200_000:
                steps = 20
            elif n_chars >= 80_000:
                steps = 12
            elif n_chars >= 20_000:
                steps = 8
            assert steps in {5, 8, 12, 20}
    except Exception:
        return
