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

    assert c._ideas_index_job_book_id == "b1"  # noqa: SLF001

    # Poll once to ensure no exceptions and doc is at least running.
    c._poll_ideas_indexing()  # noqa: SLF001
    doc = repo.load_doc(book_id="b1")
    assert isinstance(doc, dict)
    assert doc.get("status", {}).get("state") in {"running", "completed"}


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

    boxes = [
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QMessageBox)
        and dlg.windowTitle() == "Ideas"
        and dlg not in existing
    ]
    assert boxes
    assert "already in progress" in boxes[-1].text()
    boxes[-1].close()

