from __future__ import annotations

import time
import queue
from dataclasses import dataclass

from voice_reader.application.services.idea_indexing_manager import IdeaIndexJob, IdeaIndexingManager


@dataclass
class _Repo:
    docs: dict[str, dict]

    def load_doc(self, *, book_id: str):
        return self.docs.get(book_id)

    def save_doc_atomic(self, *, book_id: str, doc: dict) -> None:
        self.docs[book_id] = doc


def test_manager_start_persists_running_marker() -> None:
    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]

    mgr.start_indexing(book_id="b1", book_title=None, normalized_text="hi")
    assert repo.docs["b1"]["status"]["state"] == "running"


def test_manager_start_raises_on_empty_book_id() -> None:
    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]

    try:
        mgr.start_indexing(book_id=" ", book_title=None, normalized_text="hi")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_manager_poll_persists_result_doc() -> None:
    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]

    mgr.start_indexing(book_id="b1", book_title="T", normalized_text="hi")

    # Give the worker a moment to run and emit events.
    for _ in range(50):
        events = mgr.poll(book_id="b1")
        if any(ev.get("type") == "result" for ev in events if isinstance(ev, dict)):
            break
        time.sleep(0.01)

    doc = repo.docs["b1"]
    assert doc["status"]["state"] == "completed"
    assert doc["book"]["book_id"] == "b1"


def test_manager_start_is_noop_when_job_running(monkeypatch) -> None:
    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]

    class _P:
        def is_alive(self):
            return True

    job = mgr.start_indexing(book_id="b1", book_title=None, normalized_text="hi")
    # Force the stored job to appear alive, and ensure second start returns it.
    job.process = _P()
    mgr._jobs["b1"] = job  # noqa: SLF001

    job2 = mgr.start_indexing(book_id="b1", book_title=None, normalized_text="hi")
    assert job2 is job


def test_manager_active_job_returns_job_when_alive() -> None:
    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]

    class _P:
        def is_alive(self):
            return True

    job = IdeaIndexJob(book_id="b1", process=_P(), out_q=None, started_at="t")
    mgr._jobs["b1"] = job  # noqa: SLF001

    assert mgr.active_job(book_id="b1") is job


def test_manager_active_job_returns_job_when_finished() -> None:
    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]

    class _P:
        def is_alive(self):
            return False

    job = mgr.start_indexing(book_id="b1", book_title=None, normalized_text="hi")
    job.process = _P()
    mgr._jobs["b1"] = job  # noqa: SLF001

    assert mgr.active_job(book_id="b1") is job


def test_manager_poll_returns_empty_when_no_job() -> None:
    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]
    assert mgr.poll(book_id="missing") == []


def test_manager_active_job_returns_none_when_missing() -> None:
    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]
    assert mgr.active_job(book_id="missing") is None


def test_manager_poll_persists_progress_and_error_without_spawning() -> None:
    """Cover poll() branches without starting a real worker process."""

    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]

    class _Q:
        def __init__(self, events: list[dict]):
            self._events = list(events)

        def get_nowait(self):
            if not self._events:
                raise queue.Empty
            return self._events.pop(0)

    class _P:
        def __init__(self):
            self.join_calls = 0

        def is_alive(self):
            return False

        def join(self, timeout=None):
            self.join_calls += 1

    p = _P()
    q = _Q(
        [
            {"type": "progress", "progress": "bad", "message": "x"},
            {"type": "error", "message": "boom"},
        ]
    )
    mgr._jobs["b1"] = IdeaIndexJob(book_id="b1", process=p, out_q=q, started_at="t")  # noqa: SLF001

    events = mgr.poll(book_id="b1")
    assert len(events) == 2
    assert repo.docs["b1"]["status"]["state"] == "error"
    assert p.join_calls >= 1


def test_manager_cancel_terminates_and_persists_cancelled() -> None:
    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]

    class _P:
        def __init__(self):
            self.terminated = False
            self.joined = False

        def is_alive(self):
            return True

        def terminate(self):
            self.terminated = True

        def join(self, timeout=None):
            self.joined = True

    p = _P()
    mgr._jobs["b1"] = IdeaIndexJob(book_id="b1", process=p, out_q=None, started_at="t")  # noqa: SLF001

    mgr.cancel(book_id="b1")
    assert p.terminated is True
    assert p.joined is True
    assert repo.docs["b1"]["status"]["state"] == "cancelled"


def test_manager_cancel_is_noop_when_no_job() -> None:
    repo = _Repo(docs={})
    mgr = IdeaIndexingManager(repo=repo)  # type: ignore[arg-type]

    mgr.cancel(book_id="missing")
    assert repo.docs == {}

