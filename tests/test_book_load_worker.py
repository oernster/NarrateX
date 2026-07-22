"""The book-load child process: compute in the child, adopt in the parent.

`run_worker` is exercised in-process against a real plain-text book, because
the child-side pipeline is ordinary Python; only the process boundary needs
the real spawn, which gets one integration test. The failure branches use a
fake multiprocessing context so a dead child is provable without one.
"""

from __future__ import annotations

import queue as queue_module
from pathlib import Path

from voice_reader import book_load_worker

BOOK_TEXT = (
    "Contents\n"
    "Chapter 1 .... 1\n\n"
    "Chapter 1\n"
    "The first chapter begins in earnest here. "
    "It runs on for long enough to produce more than one chunk of text.\n\n"
    "Chapter 2\n"
    "The second chapter follows the first. "
    "It closes the little fixture book out with a final passage.\n"
)

# The same bounds app.py wires; any sane values work for the fixture.
CHUNK_MIN_CHARS = 120
CHUNK_MAX_CHARS = 220


class _ListQueue:
    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


class _ExplodingQueue:
    def put(self, item) -> None:
        del item
        raise RuntimeError("queue is gone")


def _payload(path: Path, tmp_path: Path) -> dict:
    return {
        "path": str(path),
        "temp_books_dir": str(tmp_path / "temp_books"),
        "chunk_min_chars": CHUNK_MIN_CHARS,
        "chunk_max_chars": CHUNK_MAX_CHARS,
    }


def _book_file(tmp_path: Path) -> Path:
    p = tmp_path / "fixture.txt"
    p.write_text(BOOK_TEXT, encoding="utf-8")
    return p


def test_run_worker_loads_a_real_text_book(tmp_path: Path) -> None:
    out_q = _ListQueue()

    book_load_worker.run_worker(
        out_q=out_q, payload=_payload(_book_file(tmp_path), tmp_path)
    )

    assert len(out_q.items) == 1
    event = out_q.items[0]
    assert event["type"] == "result"
    assert event["book"].title == "fixture"
    assert "Chapter 1" in event["book"].normalized_text
    assert event["chapters"], "chapter index came back empty"
    assert isinstance(event["start_char"], int)


def test_run_worker_handles_a_book_with_no_headings(tmp_path: Path) -> None:
    # No contents, no chapters: the chapter index falls back to detection,
    # which finds nothing, and the result is still a valid load.
    p = tmp_path / "flat.txt"
    p.write_text(
        "Alpha beta gamma delta epsilon zeta eta theta iota kappa.\n\n"
        "Lambda mu nu xi omicron pi rho sigma tau upsilon phi chi.\n",
        encoding="utf-8",
    )
    out_q = _ListQueue()

    book_load_worker.run_worker(out_q=out_q, payload=_payload(p, tmp_path))

    assert len(out_q.items) == 1
    event = out_q.items[0]
    assert event["type"] == "result"
    assert event["book"].title == "flat"
    assert event["chapters"] == ()


def test_run_worker_reports_a_missing_file_as_an_error(tmp_path: Path) -> None:
    out_q = _ListQueue()

    book_load_worker.run_worker(
        out_q=out_q, payload=_payload(tmp_path / "missing.txt", tmp_path)
    )

    assert len(out_q.items) == 1
    assert out_q.items[0]["type"] == "error"
    assert out_q.items[0]["message"]


def test_run_worker_survives_a_broken_queue(tmp_path: Path) -> None:
    # Both puts raising must not escape: the child exits quietly instead of
    # tracebacking after its parent stopped listening.
    book_load_worker.run_worker(
        out_q=_ExplodingQueue(), payload=_payload(tmp_path / "missing.txt", tmp_path)
    )


def test_load_in_subprocess_round_trips_a_real_book(tmp_path: Path) -> None:
    """The one real spawn: the whole result crosses the process boundary."""

    result = book_load_worker.load_in_subprocess(
        path=_book_file(tmp_path),
        temp_books_dir=tmp_path / "temp_books",
        chunk_min_chars=CHUNK_MIN_CHARS,
        chunk_max_chars=CHUNK_MAX_CHARS,
    )

    assert result["type"] == "result"
    assert result["book"].title == "fixture"
    assert result["chapters"]


_EMPTY = object()


class _FakeContext:
    """A multiprocessing stand-in for the parent-side failure branches.

    `gets` scripts the queue: each entry is either the `_EMPTY` sentinel
    (raise Empty) or a value to return. `alive_answers` scripts is_alive.
    """

    def __init__(self, *, gets: list, alive_answers: list[bool]) -> None:
        self._gets = gets
        self._alive_answers = alive_answers
        self.started = False

    def Queue(self):  # noqa: N802 (multiprocessing API shape)
        ctx = self

        class _Q:
            def get(self, timeout=None):
                del timeout
                if not ctx._gets:
                    raise queue_module.Empty
                item = ctx._gets.pop(0)
                if item is _EMPTY:
                    raise queue_module.Empty
                return item

        return _Q()

    def Process(self, *, target, kwargs):  # noqa: N802 (multiprocessing API shape)
        del target, kwargs
        ctx = self

        class _P:
            daemon = False

            def start(self) -> None:
                ctx.started = True

            def is_alive(self) -> bool:
                if ctx._alive_answers:
                    return ctx._alive_answers.pop(0)
                return False

            def join(self, timeout=None) -> None:
                del timeout

        return _P()


def _run_with_fake_context(monkeypatch, fake: _FakeContext) -> dict:
    monkeypatch.setattr(
        book_load_worker.mp, "get_context", lambda kind: fake, raising=True
    )
    return book_load_worker.load_in_subprocess(
        path=Path("x.txt"),
        temp_books_dir=Path("tmp"),
        chunk_min_chars=CHUNK_MIN_CHARS,
        chunk_max_chars=CHUNK_MAX_CHARS,
    )


def test_load_in_subprocess_reports_a_child_that_died(monkeypatch) -> None:
    fake = _FakeContext(gets=[_EMPTY, _EMPTY], alive_answers=[False])

    result = _run_with_fake_context(monkeypatch, fake)

    assert fake.started is True
    assert result["type"] == "error"
    assert "without a result" in result["message"]


def test_load_in_subprocess_keeps_waiting_while_the_child_works(monkeypatch) -> None:
    # First poll: empty but alive, so the loop continues; second poll: result.
    fake = _FakeContext(
        gets=[_EMPTY, {"type": "result", "book": None}],
        alive_answers=[True],
    )

    result = _run_with_fake_context(monkeypatch, fake)

    assert result == {"type": "result", "book": None}


def test_a_dying_child_that_already_reported_is_still_heard(monkeypatch) -> None:
    # Empty poll, child dead, but its event was already piped: the drain
    # retry must return it rather than reporting a failure.
    fake = _FakeContext(
        gets=[_EMPTY, {"type": "result", "book": None}],
        alive_answers=[False],
    )

    result = _run_with_fake_context(monkeypatch, fake)

    assert result == {"type": "result", "book": None}
