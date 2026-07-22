"""Book loading must not block the Qt/UI thread.

Selecting a large book (the combined hardback) froze the window because the
whole pipeline (parse, render plan, chapter index, cover) ran inline on the
UI thread. It now runs on a worker thread and posts widget updates back
through `ui_call_requested`, exactly as the Ideas launcher does. These tests
pin that contract: the call returns before any parsing happens, the full
pipeline still works run inline, and a failing load still surfaces an error
state instead of a blank window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.ui import _ui_controller_book_loading as book_loading
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController

from tests.ui.ui_controller_fakes import (
    FakeBookmarks,
    FakeNarration,
    FakeVoiceRepo,
    InlineThread,
)


@dataclass
class _CountingNarration(FakeNarration):
    load_calls: int = 0

    def load_book(self, path: Path):
        del path
        self.load_calls += 1
        return SimpleNamespace(normalized_text="Hello", title="T")


@dataclass
class _FailingNarration(FakeNarration):
    states: list = field(default_factory=list)

    def load_book(self, path: Path):
        del path
        raise RuntimeError("parse failed")

    def _set_state(self, state) -> None:
        self.states.append(state)


def _controller(qapp, narration) -> UiController:
    del qapp
    w = MainWindow()
    return UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=None,
        voice_service=VoiceProfileService(repo=FakeVoiceRepo(profiles=[])),
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )


def _idle_state() -> NarrationState:
    return NarrationState(
        status=NarrationStatus.IDLE,
        current_chunk_id=None,
        total_chunks=None,
        progress=0.0,
    )


def test_load_selected_book_returns_before_any_parsing(qapp, monkeypatch) -> None:
    """Regression: selecting a book must not run the pipeline inline."""

    narration = _CountingNarration(listeners=[], state=_idle_state())
    c = _controller(qapp, narration)

    import threading

    monkeypatch.setattr(threading.Thread, "start", lambda self: None)

    book_loading.load_selected_book(c, path=Path("book.txt"))

    assert narration.load_calls == 0
    assert c._book_load_inflight is True  # noqa: SLF001


def test_inline_pipeline_populates_the_window(qapp, monkeypatch) -> None:
    narration = _CountingNarration(listeners=[], state=_idle_state())
    c = _controller(qapp, narration)

    monkeypatch.setattr(book_loading.threading, "Thread", InlineThread)

    book_loading.load_selected_book(c, path=Path("book.txt"))

    assert narration.load_calls == 1
    assert c._book_load_inflight is False  # noqa: SLF001
    assert "Hello" in c.window.reader.toPlainText()


def test_failed_load_surfaces_an_error_state(qapp, monkeypatch) -> None:
    narration = _FailingNarration(listeners=[], state=_idle_state())
    c = _controller(qapp, narration)

    monkeypatch.setattr(book_loading.threading, "Thread", InlineThread)

    book_loading.load_selected_book(c, path=Path("bad.epub"))

    assert c._book_load_inflight is False  # noqa: SLF001
    assert c._chapters == []  # noqa: SLF001
    assert narration.states, "no error state was set"
    last = narration.states[-1]
    assert last.status == NarrationStatus.ERROR
    assert "bad.epub" in (last.message or "")


def test_reentry_is_blocked_while_a_load_is_in_flight(qapp, monkeypatch) -> None:
    narration = _CountingNarration(listeners=[], state=_idle_state())
    c = _controller(qapp, narration)
    c._book_load_inflight = True  # noqa: SLF001

    monkeypatch.setattr(book_loading.threading, "Thread", InlineThread)

    book_loading.load_selected_book(c, path=Path("book.txt"))

    assert narration.load_calls == 0
    assert c._book_load_inflight is True  # noqa: SLF001


def test_post_to_ui_falls_back_without_a_signal() -> None:
    calls: list[int] = []
    controller = SimpleNamespace()  # no ui_call_requested attribute

    book_loading._post_to_ui(controller, lambda: calls.append(1))  # noqa: SLF001

    assert calls == [1]


def test_post_to_ui_swallows_callback_errors() -> None:
    controller = SimpleNamespace()

    def _boom() -> None:
        raise RuntimeError("x")

    book_loading._post_to_ui(controller, _boom)  # noqa: SLF001
