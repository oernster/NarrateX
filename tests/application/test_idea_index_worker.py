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


def test_run_worker_emits_progress_and_result(monkeypatch) -> None:
    ctx = get_context("spawn")
    q = ctx.Queue()

    import tempfile
    from pathlib import Path

    p = Path(tempfile.mkdtemp()) / "b1.normalized.txt"
    p.write_text("Hello world", encoding="utf-8")

    # Use env var (same mechanism as frozen EXE) to enable debug events.
    monkeypatch.setenv("NARRATEX_IDEAS_DEBUG", "1")

    run_worker(
        out_q=q,
        payload={
            "book_id": "b1",
            "book_title": "Title",
            "text_path": str(p),
        },
    )

    events = _drain_until_result(q)

    assert any(ev.get("type") == "progress" for ev in events)
    assert any(ev.get("type") == "debug" for ev in events)
    result = next(ev for ev in events if ev.get("type") == "result")
    doc = result.get("doc")
    assert isinstance(doc, dict)
    assert doc["status"]["state"] == "completed"
    assert doc["book"]["book_id"] == "b1"


def test_run_worker_debug_put_line_is_executed(monkeypatch) -> None:
    """Coverage: ensure the in-worker _dbg() path executes its out_q.put().

    We intentionally avoid multiprocessing queues here so coverage is attributed to
    this process.
    """

    class _Q:
        def __init__(self) -> None:
            self.events: list[dict] = []

        def put(self, ev: dict) -> None:
            assert isinstance(ev, dict)
            self.events.append(ev)

    import tempfile
    from pathlib import Path

    q = _Q()
    p = Path(tempfile.mkdtemp()) / "b1.normalized.txt"
    p.write_text("Hello world", encoding="utf-8")

    monkeypatch.setenv("NARRATEX_IDEAS_DEBUG", "1")

    run_worker(
        out_q=q,
        payload={
            "book_id": "b1",
            "book_title": "Title",
            "text_path": str(p),
        },
    )

    assert any(ev.get("type") == "debug" for ev in q.events)
    assert any(ev.get("type") == "progress" for ev in q.events)
    assert any(ev.get("type") == "result" for ev in q.events)


def test_run_worker_debug_disabled_causes_dbg_early_return_line_coverage(
    monkeypatch,
) -> None:
    """Coverage: ensure _dbg()'s early-return path executes when debug is off."""

    class _Q:
        def __init__(self) -> None:
            self.events: list[dict] = []

        def put(self, ev: dict) -> None:
            self.events.append(ev)

    import tempfile
    from pathlib import Path

    q = _Q()
    p = Path(tempfile.mkdtemp()) / "b1.normalized.txt"
    p.write_text("Hello world", encoding="utf-8")

    monkeypatch.delenv("NARRATEX_IDEAS_DEBUG", raising=False)

    run_worker(
        out_q=q,
        payload={
            "book_id": "b1",
            "book_title": "Title",
            "text_path": str(p),
        },
    )

    assert any(ev.get("type") == "progress" for ev in q.events)
    assert any(ev.get("type") == "result" for ev in q.events)
    assert not any(ev.get("type") == "debug" for ev in q.events)


def test_run_worker_emits_more_than_one_progress_event_for_large_text() -> None:
    """Regression: UI progress bar should visibly move for long books."""

    ctx = get_context("spawn")
    q = ctx.Queue()

    import tempfile
    from pathlib import Path

    p = Path(tempfile.mkdtemp()) / "b1.normalized.txt"
    p.write_text("Hello world. " * 20000, encoding="utf-8")

    run_worker(
        out_q=q,
        payload={
            "book_id": "b1",
            "book_title": "Title",
            "text_path": str(p),
        },
    )

    events = _drain_until_result(q, timeout_seconds=5.0)
    progresses = [ev for ev in events if ev.get("type") == "progress"]
    assert len(progresses) >= 2


def test_run_worker_progress_steps_change_with_text_size() -> None:
    """Cover the worker's progress-step thresholds."""

    ctx = get_context("spawn")

    import tempfile
    from pathlib import Path

    def _run_with_chars(n_chars: int) -> list[dict]:
        q = ctx.Queue()
        p = Path(tempfile.mkdtemp()) / "b1.normalized.txt"
        p.write_text("x" * int(n_chars), encoding="utf-8")
        run_worker(
            out_q=q, payload={"book_id": "b1", "book_title": None, "text_path": str(p)}
        )
        return _drain_until_result(q, timeout_seconds=5.0)

    # Between 20k and 80k -> 8 steps + initial 0 + final 100
    evs_mid = _run_with_chars(20_000)
    pcts_mid = [
        int(ev.get("progress") or 0) for ev in evs_mid if ev.get("type") == "progress"
    ]
    assert len(pcts_mid) >= 10

    # Between 80k and 200k -> 12 steps + initial 0 + final 100
    evs_big = _run_with_chars(80_000)
    pcts_big = [
        int(ev.get("progress") or 0) for ev in evs_big if ev.get("type") == "progress"
    ]
    assert len(pcts_big) >= 14


def test_run_worker_accepts_none_normalized_text() -> None:
    """Cover tolerant branches; worker reads from a file."""

    ctx = get_context("spawn")
    q = ctx.Queue()

    import tempfile
    from pathlib import Path

    p = Path(tempfile.mkdtemp()) / "b1.normalized.txt"
    p.write_text("", encoding="utf-8")

    run_worker(
        out_q=q,
        payload={
            "book_id": "b1",
            "book_title": None,
            "text_path": str(p),
        },
    )

    events = _drain_until_result(q)
    assert any(ev.get("type") == "result" for ev in events)


def test_run_worker_emits_error_when_missing_book_id() -> None:
    ctx = get_context("spawn")
    q = ctx.Queue()

    run_worker(out_q=q, payload={"text_path": "missing.txt"})
    ev = q.get(timeout=1.0)
    assert ev["type"] in {"error", "debug"}
    if ev["type"] == "debug":
        ev = q.get(timeout=1.0)
    assert ev["type"] == "error"


def test_run_worker_emits_error_when_missing_text_path() -> None:
    ctx = get_context("spawn")
    q = ctx.Queue()

    run_worker(out_q=q, payload={"book_id": "b1"})
    ev = q.get(timeout=1.0)
    assert ev["type"] in {"error", "debug"}
    if ev["type"] == "debug":
        ev = q.get(timeout=1.0)
    assert ev["type"] == "error"


def test_run_worker_emits_debug_event_on_error_when_enabled(monkeypatch) -> None:
    """Coverage: ensure the exception-path debug out_q.put() executes."""

    class _Q:
        def __init__(self) -> None:
            self.events: list[dict] = []

        def put(self, ev: dict) -> None:
            assert isinstance(ev, dict)
            self.events.append(ev)

    q = _Q()

    monkeypatch.setenv("NARRATEX_IDEAS_DEBUG", "1")

    # Missing book_id triggers exception handler.
    run_worker(out_q=q, payload={"text_path": "missing.txt"})

    assert any(ev.get("type") == "error" for ev in q.events)
    assert any(
        ev.get("type") == "debug" and "worker error" in str(ev.get("message", ""))
        for ev in q.events
    )
