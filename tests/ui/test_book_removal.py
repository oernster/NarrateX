"""Removing the current book forgets NarrateX's memory, never the file.

The ❌ control deletes bookmarks, the resume position, the ideas map and
cached audio for the loaded book, then returns the window to its fresh
state. It always confirms first; tests drive the outcome through the
explicit `confirmed` parameter because the real dialog is modal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.idea_map_service import IdeaMapService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController

from tests.ui.ui_controller_fakes import FakeBookmarks, FakeNarration, FakeVoiceRepo


@dataclass
class _ForgettingNarration(FakeNarration):
    forget_calls: int = 0
    removed: bool = False

    def loaded_book(self):
        return None if self.removed else SimpleNamespace(title="Test Book")

    def loaded_book_id(self):
        return None if self.removed else "b1"

    def forget_current_book(self):
        self.forget_calls += 1
        self.removed = True
        return "b1"


@dataclass
class _RecordingIdeasRepo:
    deleted: list[str] = field(default_factory=list)

    def load_doc(self, *, book_id: str):
        del book_id
        return None

    def save_doc_atomic(self, *, book_id: str, doc: dict) -> None:
        del book_id, doc

    def delete_doc(self, *, book_id: str) -> None:
        self.deleted.append(book_id)


def _controller(qapp) -> tuple[UiController, _ForgettingNarration, _RecordingIdeasRepo]:
    del qapp
    narration = _ForgettingNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    ideas_repo = _RecordingIdeasRepo()
    controller = UiController(
        window=MainWindow(),
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=ideas_repo),  # type: ignore[arg-type]
        voice_service=VoiceProfileService(
            repo=FakeVoiceRepo(
                profiles=[VoiceProfile(name="bf_emma", reference_audio_paths=[])]
            )
        ),
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )
    return controller, narration, ideas_repo


def test_removal_needs_a_loaded_book(qapp) -> None:
    c, narration, ideas = _controller(qapp)
    narration.removed = True  # nothing loaded

    c.remove_current_book(confirmed=True)

    assert narration.forget_calls == 0
    assert ideas.deleted == []


def test_declining_the_confirmation_removes_nothing(qapp) -> None:
    c, narration, ideas = _controller(qapp)

    c.remove_current_book(confirmed=False)

    assert narration.forget_calls == 0
    assert ideas.deleted == []


def test_the_modal_confirmation_defaults_to_cancel_under_tests(qapp) -> None:
    # confirmed=None builds the real confirmation box; under pytest it
    # answers False rather than blocking on exec().
    c, narration, ideas = _controller(qapp)

    c.remove_current_book(confirmed=None)

    assert narration.forget_calls == 0
    assert ideas.deleted == []


def test_confirmed_removal_forgets_the_book_and_resets_the_ui(qapp) -> None:
    c, narration, ideas = _controller(qapp)
    window = c.window
    window.set_reader_text("Some book text")
    window.set_chapter_controls_enabled(previous=True, next_=True)

    c.remove_current_book(confirmed=True)

    assert narration.forget_calls == 1
    assert ideas.deleted == ["b1"]
    assert window.reader.toPlainText() == ""
    assert window.btn_prev_chapter.isEnabled() is False
    assert window.btn_next_chapter.isEnabled() is False
    assert window.lbl_status.text() == "Idle"
    # With nothing loaded, the book-gated controls lock again.
    assert window.btn_remove_book.isEnabled() is False
    assert window.voice_combo.isEnabled() is False


def test_removal_survives_a_hostile_environment(qapp) -> None:
    # Every seam is allowed to fail without aborting the removal or raising.
    del qapp
    from voice_reader.ui._ui_controller_book_removal import remove_current_book

    class _RaisingIdNarration:
        def loaded_book_id(self):
            raise RuntimeError("no id")

    remove_current_book(
        SimpleNamespace(narration_service=_RaisingIdNarration()), confirmed=True
    )

    class _RaisingNarration:
        def loaded_book_id(self):
            return "b1"

        def forget_current_book(self):
            raise RuntimeError("forget exploded")

    class _RaisingIdeas:
        def delete_index(self, *, book_id):
            del book_id
            raise RuntimeError("delete exploded")

    class _ExplodingWindow:
        def __getattr__(self, name):
            raise RuntimeError(f"window unavailable: {name}")

    class _RaisingAttention:
        def clear(self):
            raise RuntimeError("clear exploded")

    hostile = SimpleNamespace(
        narration_service=_RaisingNarration(),
        idea_map_service=_RaisingIdeas(),
        window=_ExplodingWindow(),
        _picker_attention=_RaisingAttention(),
        _ideas_launch_cancel=None,
    )

    remove_current_book(hostile, confirmed=True)  # must not raise

    assert hostile._chapters == []  # noqa: SLF001


def test_the_title_falls_back_when_the_service_cannot_name_the_book(qapp) -> None:
    # A narration service without loaded_book() still confirms readably.
    from voice_reader.ui._ui_controller_book_removal import _book_title

    c, _, _ = _controller(qapp)
    c.narration_service = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )

    assert _book_title(c) == "this book"
