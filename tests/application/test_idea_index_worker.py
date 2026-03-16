from __future__ import annotations

import time
from multiprocessing import get_context

from voice_reader.application.services.idea_index_worker import run_worker


def _drain_until_result(q, *, timeout_seconds: float = 2.0) -> list[dict]:
    """Multiprocessing Queue empty() is unreliable on Windows.

    Drain events until a result/error arrives or timeout.
    """

    deadline = time.monotonic() + float(timeout_seconds)
    events: list[dict] = []
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            ev = q.get(timeout=min(0.25, remaining))
        except Exception:
            continue
        assert isinstance(ev, dict)
        events.append(ev)
        if ev.get("type") in {"result", "error"}:
            break
    return events


def test_run_worker_emits_progress_and_result() -> None:
    ctx = get_context("spawn")
    q = ctx.Queue()

    run_worker(
        out_q=q,
        payload={
            "book_id": "b1",
            "book_title": "Title",
            "normalized_text": "Hello world",
        },
    )

    events = _drain_until_result(q)

    assert any(ev.get("type") == "progress" for ev in events)
    result = next(ev for ev in events if ev.get("type") == "result")
    doc = result.get("doc")
    assert isinstance(doc, dict)
    assert doc["status"]["state"] == "completed"
    assert doc["book"]["book_id"] == "b1"


def test_run_worker_accepts_none_normalized_text() -> None:
    """Cover the tolerant normalized_text=None branch."""

    ctx = get_context("spawn")
    q = ctx.Queue()

    run_worker(
        out_q=q,
        payload={
            "book_id": "b1",
            "book_title": None,
            "normalized_text": None,
        },
    )

    events = _drain_until_result(q)
    assert any(ev.get("type") == "result" for ev in events)


def test_run_worker_emits_error_when_missing_book_id() -> None:
    ctx = get_context("spawn")
    q = ctx.Queue()

    run_worker(out_q=q, payload={"normalized_text": "x"})
    ev = q.get(timeout=1.0)
    assert ev["type"] == "error"

