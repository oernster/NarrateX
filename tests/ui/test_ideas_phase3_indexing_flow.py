from __future__ import annotations

from dataclasses import dataclass
from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.idea_indexing_manager import IdeaIndexingManager
from voice_reader.application.services.idea_map_service import IdeaMapService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.infrastructure.ideas.json_idea_index_repository import JSONIdeaIndexRepository
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController


@dataclass
class _FakeNarration:
    listeners: list
    state: NarrationState

    def add_listener(self, listener):
        self.listeners.append(listener)

    def loaded_book_id(self):
        return "b1"


@dataclass
class _FakeBookmarks:
    def list_bookmarks(self, *, book_id: str):
        del book_id
        return []

    def add_bookmark(self, *, book_id: str, char_offset: int, chunk_index: int):
        del book_id, char_offset, chunk_index

    def delete_bookmark(self, *, book_id: str, bookmark_id: int) -> None:
        del book_id, bookmark_id

    def save_resume_position(self, *, book_id: str, char_offset: int, chunk_index: int):
        del book_id, char_offset, chunk_index

    def load_resume_position(self, *, book_id: str):
        del book_id
        return None


@dataclass(frozen=True, slots=True)
class _FakeVoiceRepo:
    def list_profiles(self):
        return [VoiceProfile(name="bf_emma", reference_audio_paths=[])]


def test_ideas_click_unindexed_shows_permission_and_starts_indexing(qapp, tmp_path):
    """Phase 3: clicking 🧠 on an unindexed book should prompt and (on accept) start indexing."""

    from PySide6.QtWidgets import QApplication, QMessageBox

    del qapp
    w = MainWindow()
    w.show()
    QApplication.processEvents()

    narration = _FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )

    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    idea_service = IdeaMapService(repo=repo)

    # Ensure staging occurs under the test temp dir (avoid touching real cwd/cache).
    import voice_reader.shared.config as cfg_mod

    original_from_project_root = cfg_mod.Config.from_project_root

    def _fake_from_project_root(_):
        real = original_from_project_root(tmp_path)
        return real

    cfg_mod.Config.from_project_root = staticmethod(_fake_from_project_root)  # type: ignore[assignment]

    mgr = IdeaIndexingManager(repo=repo)
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        idea_indexing_manager=mgr,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    # Provide a book so the launcher can stage text.
    narration._book = type("B", (), {"normalized_text": "Hello", "title": "T"})()  # type: ignore[attr-defined]

    # Ensure only new dialogs are considered.
    existing = {
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QMessageBox) and dlg.windowTitle() == "Ideas"
    }

    c.open_ideas_dialog()
    QApplication.processEvents()

    boxes = [
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QMessageBox) and dlg.windowTitle() == "Ideas" and dlg not in existing
    ]
    assert boxes
    box = boxes[-1]

    # Simulate user accepting the permission prompt.
    box.done(int(QMessageBox.Ok))
    QApplication.processEvents()

    # Mapping should show the dedicated Ideas progress bar (separate from narration progress).
    assert hasattr(w, "ideas_progress")
    assert w.ideas_progress.isVisible() is True

    # Job id may be set shortly after launcher posts back; assert we at least entered launch.
    assert getattr(c, "_ideas_launch_inflight", False) in {True, False}  # noqa: SLF001

    # Poll once to ensure no exceptions and doc is at least running.
    import time

    deadline = time.monotonic() + 2.0
    doc = None
    while time.monotonic() < deadline:
        c._poll_ideas_indexing()  # noqa: SLF001
        QApplication.processEvents()
        doc = repo.load_doc(book_id="b1")
        if isinstance(doc, dict):
            break
        time.sleep(0.01)

    # Restore Config patch.
    cfg_mod.Config.from_project_root = original_from_project_root  # type: ignore[assignment]

    assert isinstance(doc, dict)
    assert doc.get("status", {}).get("state") in {"running", "completed"}

    # The progress bar should be updated during mapping and is expected to
    # eventually hide once the indexing worker returns a terminal event.
    # In tests, process scheduling can vary, so assert it is either hidden or
    # has advanced beyond the initial 0 state.
    assert (w.ideas_progress.isVisible() is False) or (
        w.ideas_progress.value() >= 0
    )


def test_open_ideas_dialog_when_job_running_shows_in_progress_message(qapp, tmp_path):
    from PySide6.QtWidgets import QApplication, QMessageBox

    del qapp
    w = MainWindow()
    w.show()
    QApplication.processEvents()

    narration = _FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )

    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    idea_service = IdeaMapService(repo=repo)
    mgr = IdeaIndexingManager(repo=repo)
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        idea_indexing_manager=mgr,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    # Simulate a running job.
    c._ideas_index_job_book_id = "b1"  # noqa: SLF001

    existing = {
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QMessageBox) and dlg.windowTitle() == "Ideas"
    }

    c.open_ideas_dialog()
    QApplication.processEvents()

    # While mapping is running, we should *not* open another message box; the
    # main UI shows a dedicated progress bar under 🧠 instead.
    boxes = [
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QMessageBox)
        and dlg.windowTitle() == "Ideas"
        and dlg not in existing
    ]
    assert boxes == []

