from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
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
    stop_calls: int = 0
    start_calls: int = 0
    prepare_calls: list[tuple[str, int]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.prepare_calls is None:
            self.prepare_calls = []

    def add_listener(self, listener):
        self.listeners.append(listener)

    def loaded_book_id(self):
        return "b1"

    def current_position(self):
        return 0, 0

    def stop(self):
        self.stop_calls += 1

    def prepare(self, *, voice, start_playback_index=None):
        assert start_playback_index is not None
        self.prepare_calls.append((getattr(voice, "name", ""), int(start_playback_index)))

    def start(self):
        self.start_calls += 1


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


def test_open_ideas_dialog_go_to_navigates_using_chunk_index(qapp, tmp_path: Path) -> None:
    del qapp
    w = MainWindow()
    narration = _FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )

    # Persist a minimal completed ideas index.
    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    repo.save_doc_atomic(
        book_id="b1",
        doc={
            "schema_version": 1,
            "status": {"state": "completed", "completed_at": datetime.now(timezone.utc).isoformat()},
            "book": {"fingerprint_sha256": IdeaMapService.fingerprint_sha256(normalized_text="")},
            "anchors": [{"anchor_id": "a1", "chunk_index": 12, "char_offset": 10, "sentence_id": None}],
            "nodes": [{"node_id": "n1", "label": "Decision fatigue", "primary_anchor_id": "a1"}],
        },
    )
    idea_service = IdeaMapService(repo=repo)

    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    # Open dialog.
    c.open_ideas_dialog()
    dlg = c._ideas_dialog  # noqa: SLF001
    assert dlg is not None
    assert dlg.isVisible() is True

    # Ensure the list is populated.
    assert dlg.list.count() == 1

    # Trigger navigation.
    item = dlg.list.item(0)
    assert item is not None
    dlg.list.setCurrentItem(item)
    dlg.btn_goto.click()

    assert narration.stop_calls == 1
    assert narration.start_calls == 1
    assert narration.prepare_calls[-1][1] == 12


def test_open_ideas_dialog_shows_message_when_unindexed(qapp, tmp_path: Path) -> None:
    """When no completed index exists, show the Phase-3 permission prompt."""

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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    # No index present.
    idea_service = IdeaMapService(repo=JSONIdeaIndexRepository(bookmarks_dir=tmp_path))

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )
    existing = {
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QMessageBox) and dlg.windowTitle() == "Ideas"
    }

    c.open_ideas_dialog()

    boxes = [
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QMessageBox)
        and dlg.windowTitle() == "Ideas"
        and dlg not in existing
    ]
    assert boxes, "Expected an Ideas message box when unindexed"
    assert "Map this book" in boxes[-1].text()
    boxes[-1].close()

    # Cover the test-only re-widen path to avoid title truncation on Windows.
    from voice_reader.ui import _ui_controller_ideas

    _ui_controller_ideas._widen_message_box(boxes[-1], min_width=420)  # noqa: SLF001


def test_open_ideas_dialog_permission_prompt_mentions_previous_error(qapp, tmp_path: Path) -> None:
    """If the persisted status is error, the permission prompt should mention it."""

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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    repo.save_doc_atomic(
        book_id="b1",
        doc={"schema_version": 1, "status": {"state": "error"}},
    )
    idea_service = IdeaMapService(repo=repo)

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    existing = {
        id(dlg)
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
        and id(dlg) not in existing
    ]
    assert boxes
    assert "Previous mapping failed" in boxes[-1].text()
    boxes[-1].close()


def test_open_ideas_dialog_permission_prompt_mentions_previous_cancelled(
    qapp, tmp_path: Path
) -> None:
    """If the persisted status is cancelled, the permission prompt should mention it."""

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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    repo.save_doc_atomic(
        book_id="b1",
        doc={"schema_version": 1, "status": {"state": "cancelled"}},
    )
    idea_service = IdeaMapService(repo=repo)

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    existing = {
        id(dlg)
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
        and id(dlg) not in existing
    ]
    assert boxes
    assert "Previous mapping was cancelled" in boxes[-1].text()
    boxes[-1].close()


def test_open_ideas_dialog_permission_prompt_mentions_previous_running(
    qapp, tmp_path: Path
) -> None:
    """If the persisted status is running (e.g. app closed mid-index), mention it."""

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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    repo.save_doc_atomic(
        book_id="b1",
        doc={"schema_version": 1, "status": {"state": "running"}},
    )
    idea_service = IdeaMapService(repo=repo)

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    existing = {
        id(dlg)
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
        and id(dlg) not in existing
    ]
    assert boxes
    assert "Previous mapping didn’t finish" in boxes[-1].text()
    boxes[-1].close()


def test_open_ideas_dialog_permission_prompt_mentions_stale_index(
    qapp, tmp_path: Path
) -> None:
    """If index is completed but fingerprint mismatches, prompt should mention it's out of date."""

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
    # Ensure the controller sees a normalized_text, so fingerprint mismatch is meaningful.
    narration._book = type("B", (), {"normalized_text": "NEW", "title": "T"})()  # type: ignore[attr-defined]

    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    repo.save_doc_atomic(
        book_id="b1",
        doc={
            "schema_version": 1,
            "status": {"state": "completed"},
            "book": {"fingerprint_sha256": IdeaMapService.fingerprint_sha256(normalized_text="OLD")},
        },
    )
    idea_service = IdeaMapService(repo=repo)

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    existing = {
        id(dlg)
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
        and id(dlg) not in existing
    ]
    assert boxes
    assert "out of date" in boxes[-1].text().casefold()
    boxes[-1].close()


def test_open_ideas_dialog_shows_message_when_invalid_doc(qapp, tmp_path: Path) -> None:
    """When index exists but is invalid, show a failure message."""

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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    # Persist a "completed" index with nodes/anchors wrong types.
    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.ideas.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": {"state": "completed"},
                "book": {
                    "fingerprint_sha256": IdeaMapService.fingerprint_sha256(
                        normalized_text=""
                    )
                },
                "nodes": "bad",
                "anchors": "bad",
            }
        ),
        encoding="utf-8",
    )
    idea_service = IdeaMapService(repo=repo)

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )
    c.open_ideas_dialog()

    # It should open a dialog (empty list is OK) not crash.
    dlg = c._ideas_dialog  # noqa: SLF001
    assert dlg is not None
    assert dlg.list.count() == 0


def test_open_ideas_dialog_shows_message_when_no_book_loaded(qapp) -> None:
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
    # Override to simulate no loaded book id.
    narration.loaded_book_id = lambda: None  # type: ignore[method-assign]

    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())
    idea_service = IdeaMapService(repo=JSONIdeaIndexRepository(bookmarks_dir=Path.cwd()))

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )
    c.open_ideas_dialog()
    QApplication.processEvents()

    boxes = [
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QMessageBox) and dlg.text() == "Load a book to map ideas."
    ]
    assert boxes
    assert boxes[-1].windowTitle() == "Ideas"
    boxes[-1].close()


def test_open_ideas_dialog_shows_message_when_doc_not_dict(qapp) -> None:
    """Exercise the 'Failed loading idea map' branch."""

    from types import SimpleNamespace

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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    # Fake service that claims completed but returns a non-dict doc.
    idea_service = SimpleNamespace(
        has_completed_index=lambda **_: True,
        load_index_doc=lambda **_: [],
    )

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )
    # Ensure we only assert against message boxes created by *this* call.
    # Qt sometimes keeps old dialogs around across tests.
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
    # Text should correspond to failed load.
    assert "Failed" in boxes[-1].text()
    boxes[-1].close()


def test_open_ideas_dialog_list_item_filtering_and_goto_no_voice_is_noop(
    qapp, tmp_path: Path
) -> None:
    """Cover filtering branches and the go-to early return when no voice is selected."""

    from types import SimpleNamespace

    del qapp
    w = MainWindow()
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
    repo.save_doc_atomic(
        book_id="b1",
        doc={
            "schema_version": 1,
            "status": {"state": "completed"},
            "book": {"fingerprint_sha256": IdeaMapService.fingerprint_sha256(normalized_text="")},
            "nodes": [
                1,
                {"node_id": "", "label": "x"},
                {"node_id": "n1", "label": ""},
                {"node_id": "n1", "label": "Valid"},
            ],
            "anchors": [
                1,
                {"anchor_id": "a1", "chunk_index": "not-int"},
            ],
        },
    )
    idea_service = IdeaMapService(repo=repo)

    # Voice service returns empty, so controller._selected_voice() will return None.
    voice_service = VoiceProfileService(
        repo=SimpleNamespace(list_profiles=lambda: [])  # type: ignore[arg-type]
    )

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    c.open_ideas_dialog()
    dlg = c._ideas_dialog  # noqa: SLF001
    assert dlg is not None
    # Only the valid node should remain.
    assert dlg.list.count() == 1

    # Go To should be a no-op because no voice is selected.
    dlg.btn_goto.click()
    assert narration.prepare_calls == []


def test_open_ideas_dialog_go_to_bad_chunk_index_is_noop(qapp, tmp_path: Path) -> None:
    """Cover the chunk_index parse failure branch in _go_to."""

    del qapp
    w = MainWindow()
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
    repo.save_doc_atomic(
        book_id="b1",
        doc={
            "schema_version": 1,
            "status": {"state": "completed"},
            "book": {"fingerprint_sha256": IdeaMapService.fingerprint_sha256(normalized_text="")},
            "anchors": [{"anchor_id": "a1", "chunk_index": "bad"}],
            "nodes": [{"node_id": "n1", "label": "X", "primary_anchor_id": "a1"}],
        },
    )
    idea_service = IdeaMapService(repo=repo)
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    c.open_ideas_dialog()
    dlg = c._ideas_dialog  # noqa: SLF001
    assert dlg is not None
    dlg.btn_goto.click()
    assert narration.prepare_calls == []


def test_open_ideas_dialog_reopens_closing_existing_dialog(qapp, tmp_path: Path) -> None:
    """Cover the 'close existing dialog' branch."""

    del qapp
    w = MainWindow()
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
    repo.save_doc_atomic(
        book_id="b1",
        doc={
            "schema_version": 1,
            "status": {"state": "completed"},
            "book": {"fingerprint_sha256": IdeaMapService.fingerprint_sha256(normalized_text="")},
            "anchors": [{"anchor_id": "a1", "chunk_index": 1}],
            "nodes": [{"node_id": "n1", "label": "X", "primary_anchor_id": "a1"}],
        },
    )
    idea_service = IdeaMapService(repo=repo)
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=idea_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    c.open_ideas_dialog()
    first = c._ideas_dialog  # noqa: SLF001
    assert first is not None
    assert first.isVisible() is True

    c.open_ideas_dialog()
    second = c._ideas_dialog  # noqa: SLF001
    assert second is not None
    assert second is not first


