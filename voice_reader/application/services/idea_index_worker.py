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
        book_id = str(payload.get("book_id") or "").strip()
        if not book_id:
            raise ValueError("book_id is required")

        book_title = payload.get("book_title")
        if book_title is not None:
            book_title = str(book_title)

        normalized_text = payload.get("normalized_text")
        if normalized_text is None:
            normalized_text = ""
        normalized_text = str(normalized_text)

        fingerprint = hashlib.sha256(normalized_text.encode("utf-8", errors="replace")).hexdigest()

        # Streaming progress keeps UI responsive and provides user feedback.
        for p in (0, 20, 60, 90):
            out_q.put({"type": "progress", "progress": int(p), "message": "Mapping ideas…"})
            time.sleep(0.01)

        doc = build_idea_index_doc_v1(
            book_id=book_id,
            book_title=book_title,
            normalized_text=normalized_text,
        )

        # Overwrite fingerprint from the indexer with a stable SHA over the same
        # normalized_text we were given. This keeps Phase-3 docs consistent even
        # if the indexer later adds caps.
        if isinstance(doc.get("book"), dict):
            doc["book"]["fingerprint_sha256"] = fingerprint

        out_q.put({"type": "progress", "progress": 100, "message": "Mapping ideas…"})
        out_q.put({"type": "result", "doc": doc})
    except Exception as exc:  # noqa: BLE001
        out_q.put({"type": "error", "message": repr(exc)})


def _touch_coverage() -> None:  # pragma: no cover
    """Reserved for future worker enhancements."""

    return

