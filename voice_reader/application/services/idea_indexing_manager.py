"""Background indexing manager for Ideas.

Phase 3 scope:

- spawn a separate process (maximum playback isolation)
- stream progress + completion back to the UI
- persist progress/completion using the existing IdeaIndexRepository
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import queue
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from voice_reader.domain.interfaces.idea_index_repository import IdeaIndexRepository
from voice_reader.application.services.idea_index_worker import run_worker
from voice_reader.application.services.ideas_staging import safe_unlink


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class IdeaIndexJob:
    book_id: str
    # `multiprocessing` returns platform/context-specific process/queue classes
    # (e.g. SpawnProcess). Use `Any` for pragmatic typing.
    process: Any
    out_q: Any
    started_at: str
    input_text_path: str | None = None


class IdeaIndexingManager:
    """Owns indexing jobs and persistence of their documents."""

    def __init__(self, *, repo: IdeaIndexRepository) -> None:
        self._repo = repo
        self._jobs: dict[str, IdeaIndexJob] = {}

    def active_job(self, *, book_id: str) -> IdeaIndexJob | None:
        job = self._jobs.get(book_id)
        if job is None:
            return None
        if not job.process.is_alive():
            return job
        return job

    def start_indexing(
        self,
        *,
        book_id: str,
        book_title: str | None,
        text_path: str | Path,
    ) -> IdeaIndexJob:
        """Start a new indexing job for a book (no-op if already running)."""

        book_id = str(book_id).strip()
        if not book_id:
            raise ValueError("book_id must be non-empty")

        existing = self._jobs.get(book_id)
        if existing is not None and existing.process.is_alive():
            return existing

        # Debug visibility for packaged builds where spawn/process creation can fail silently.
        logging.getLogger(self.__class__.__name__).info(
            "Ideas: start_indexing book_id=%s text_path=%s", book_id, str(text_path)
        )

        started_at = _utc_now_iso()
        # Persist a lightweight running marker.
        self._repo.save_doc_atomic(
            book_id=book_id,
            doc={
                "schema_version": 1,
                "status": {
                    "state": "running",
                    "started_at": started_at,
                    "progress": 0,
                },
            },
        )

        ctx = mp.get_context("spawn")
        out_q: mp.Queue = ctx.Queue()
        text_path = str(Path(text_path).resolve())
        payload = {
            "book_id": book_id,
            "book_title": book_title,
            "text_path": text_path,
        }
        p = ctx.Process(target=run_worker, kwargs={"out_q": out_q, "payload": payload})
        p.daemon = True
        p.start()

        logging.getLogger(self.__class__.__name__).info(
            "Ideas: worker process started book_id=%s pid=%s alive=%s",
            book_id,
            getattr(p, "pid", None),
            bool(getattr(p, "is_alive", lambda: False)()),
        )

        job = IdeaIndexJob(
            book_id=book_id,
            process=p,
            out_q=out_q,
            started_at=started_at,
            input_text_path=text_path,
        )
        self._jobs[book_id] = job
        return job

    def cancel(self, *, book_id: str) -> None:
        job = self._jobs.get(book_id)
        if job is None:
            return
        try:
            if job.process.is_alive():
                job.process.terminate()
        except Exception:  # pragma: no cover
            pass
        try:
            job.process.join(timeout=0.2)
        except Exception:  # pragma: no cover
            pass

        # Cleanup staged input (best-effort).
        safe_unlink(job.input_text_path)

        # Persist cancellation state (best-effort).
        try:
            self._repo.save_doc_atomic(
                book_id=book_id,
                doc={
                    "schema_version": 1,
                    "status": {
                        "state": "cancelled",
                        "cancelled_at": _utc_now_iso(),
                    },
                },
            )
        except Exception:  # pragma: no cover
            pass

    def poll(self, *, book_id: str) -> list[dict]:
        """Drain pending events for the job and persist running/completed docs."""

        job = self._jobs.get(book_id)
        if job is None:
            return []

        events: list[dict] = []
        while True:
            try:
                ev = job.out_q.get_nowait()
            except queue.Empty:
                break
            except Exception:  # pragma: no cover
                break
            if isinstance(ev, dict):
                events.append(ev)

        # If the UI is stuck at 0%, the most common causes are:
        # - worker process crashed before emitting progress
        # - queue is not being drained
        # - job is not alive
        # Log minimal state when no events arrive.
        if not events:
            logging.getLogger(self.__class__.__name__).debug(
                "Ideas: poll book_id=%s alive=%s qsize=%s",
                book_id,
                bool(getattr(job.process, "is_alive", lambda: False)()),
                getattr(job.out_q, "qsize", lambda: "?")(),
            )

        # Best-effort persistence: running progress + completion.
        for ev in events:
            typ = ev.get("type")
            if typ == "progress":
                try:
                    p = int(ev.get("progress") or 0)
                except Exception:
                    p = 0
                try:
                    self._repo.save_doc_atomic(
                        book_id=book_id,
                        doc={
                            "schema_version": 1,
                            "status": {
                                "state": "running",
                                "started_at": job.started_at,
                                "progress": max(0, min(100, p)),
                            },
                        },
                    )
                except Exception:  # pragma: no cover
                    pass
            elif typ == "result":
                doc = ev.get("doc")
                if isinstance(doc, dict):
                    self._repo.save_doc_atomic(book_id=book_id, doc=doc)
            elif typ == "error":
                try:
                    self._repo.save_doc_atomic(
                        book_id=book_id,
                        doc={
                            "schema_version": 1,
                            "status": {
                                "state": "error",
                                "error": str(ev.get("message") or "error"),
                                "failed_at": _utc_now_iso(),
                            },
                        },
                    )
                except Exception:  # pragma: no cover
                    pass

        # Cleanup: if the process finished, join it.
        try:
            if not job.process.is_alive():
                job.process.join(timeout=0.2)
        except Exception:  # pragma: no cover
            pass

        # Cleanup staged input on terminal events (best-effort).
        if any(
            isinstance(ev, dict) and ev.get("type") in {"result", "error"}
            for ev in events
        ):
            safe_unlink(job.input_text_path)

        return events

