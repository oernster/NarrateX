from __future__ import annotations


from dataclasses import dataclass

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.structural_bookmark_service import (
    StructuralBookmarkService,
)
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.services.reading_start_service import ReadingStartService
from voice_reader.application.services.navigation_chunk_service import (
    NavigationChunkService,
)
from voice_reader.ui._ui_controller_sections import open_structural_bookmarks_dialog
from voice_reader.ui.main_window import MainWindow


@dataclass
class _FakeNarration:
    listeners: list
    state: NarrationState
    prepare_calls: list[dict]
    stop_calls: int = 0
    start_calls: int = 0
    _book: object | None = None

    def add_listener(self, listener):
        self.listeners.append(listener)

    def loaded_book_id(self):
        return "b1"

    def stop(self, *, persist_resume: bool = True):
        del persist_resume
        self.stop_calls += 1

    def prepare(
        self,
        *,
        voice,
        start_playback_index=None,
        start_char_offset=None,
        force_start_char=None,
        skip_essay_index=True,
        persist_resume=True,
    ):
        self.prepare_calls.append(
            {
                "voice": getattr(voice, "name", ""),
                "start_playback_index": start_playback_index,
                "start_char_offset": start_char_offset,
                "force_start_char": force_start_char,
                "skip_essay_index": skip_essay_index,
                "persist_resume": persist_resume,
            }
        )

    def start(self):
        self.start_calls += 1


@dataclass(frozen=True, slots=True)
class _FakeVoiceRepo:
    def list_profiles(self):
        return [VoiceProfile(name="bf_emma", reference_audio_paths=[])]


def test_go_to_section_calls_prepare_with_force_start_char(qapp) -> None:
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication

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
        prepare_calls=[],
    )
    narration._book = type(
        "B",
        (),
        {"normalized_text": "\n\nChapter 1: Start\n\nHello\n", "title": "T"},
    )()

    controller = SimpleNamespace(
        window=w,
        narration_service=narration,
        structural_bookmark_service=StructuralBookmarkService(),
        voice_service=VoiceProfileService(repo=_FakeVoiceRepo()),
        _voices=[VoiceProfile(name="bf_emma", reference_audio_paths=[])],
        _last_prepared_voice_id=None,
        _chapters=[],
        _sections_dialog=None,
        _selected_voice=lambda: VoiceProfile(name="bf_emma", reference_audio_paths=[]),
    )

    open_structural_bookmarks_dialog(controller)
    QApplication.processEvents()

    dlg = getattr(controller, "_sections_dialog", None)
    assert dlg is not None
    assert dlg.list.count() >= 1
    dlg.list.setCurrentRow(0)
    dlg.btn_goto.click()
    assert narration.prepare_calls
    call = narration.prepare_calls[-1]
    assert call["start_char_offset"] is not None
    assert call["force_start_char"] == call["start_char_offset"]
    assert call["skip_essay_index"] is True
    assert call["persist_resume"] is False


def test_sections_go_to_prefers_body_heading_when_toc_duplicates_exist(qapp) -> None:
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication

    del qapp
    w = MainWindow()
    w.show()
    QApplication.processEvents()

    text = (
        "Table of Contents\n\n"
        "Chapter 1\n"
        "Chapter 2\n"
        "Chapter 3\n\n"
        "Prologue\n\n"
        "Chapter 1\nBody\n\n"
        "Chapter 2\nBody\n\n"
        "Chapter 3\nBody\n\n"
    )

    narration = _FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
        prepare_calls=[],
    )
    narration._book = type("B", (), {"normalized_text": text, "title": "T"})()

    controller = SimpleNamespace(
        window=w,
        narration_service=narration,
        structural_bookmark_service=StructuralBookmarkService(),
        voice_service=VoiceProfileService(repo=_FakeVoiceRepo()),
        _voices=[VoiceProfile(name="bf_emma", reference_audio_paths=[])],
        _last_prepared_voice_id=None,
        _chapters=[],
        _sections_dialog=None,
        _selected_voice=lambda: VoiceProfile(name="bf_emma", reference_audio_paths=[]),
    )

    open_structural_bookmarks_dialog(controller)
    QApplication.processEvents()

    dlg = getattr(controller, "_sections_dialog", None)
    assert dlg is not None

    # Select the Chapter 3 item.
    target_row = None
    for i in range(dlg.list.count()):
        item = dlg.list.item(i)
        if item is not None and item.text() == "📌 Chapter 3":
            target_row = i
            break

    assert target_row is not None
    dlg.list.setCurrentRow(int(target_row))
    dlg.btn_goto.click()

    assert narration.prepare_calls
    call = narration.prepare_calls[-1]

    expected_offset = text.index("\nChapter 3\nBody") + 1
    assert call["start_char_offset"] == expected_offset
    assert call["force_start_char"] == expected_offset
    assert call["skip_essay_index"] is True


def test_sections_go_to_defensive_guard_never_forces_pre_boundary_offset(qapp) -> None:
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication

    del qapp
    w = MainWindow()
    w.show()
    QApplication.processEvents()

    # ReadingStartService will treat Chapter 1 as the first real section and start
    # after the heading line (at the first paragraph). We intentionally return a
    # pre-boundary bookmark to ensure the UI guard won't force narration there.
    text = "\n\nChapter 1\n\nBody paragraph.\n"

    # Precompute the readable-start boundary the controller will compute.
    boundary = int(ReadingStartService().detect_start(text).start_char)

    # Provide a navigation-chunk service so the controller uses the same path as
    # real book load.
    class _Nav:
        def __init__(self):
            self._svc = NavigationChunkService(
                reading_start_detector=ReadingStartService(),
                chunking_service=ChunkingService(),
            )

        def build_chunks(self, *, book_text: str):
            return self._svc.build_chunks(book_text=book_text)

    narration = _FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
        prepare_calls=[],
    )
    narration._book = type("B", (), {"normalized_text": text, "title": "T"})()

    class _Svc:
        def build_for_loaded_book(self, **_):
            return [
                type(
                    "SB",
                    (),
                    {
                        "label": "Chapter 1",
                        "char_offset": 2,  # before the readable start
                        "chunk_index": None,
                        "kind": "chapter",
                        "level": 0,
                    },
                )()
            ]

    controller = SimpleNamespace(
        window=w,
        narration_service=narration,
        structural_bookmark_service=_Svc(),
        _navigation_chunk_service=_Nav(),
        _chapters=[],
        _sections_dialog=None,
        _selected_voice=lambda: VoiceProfile(name="bf_emma", reference_audio_paths=[]),
    )

    open_structural_bookmarks_dialog(controller)
    QApplication.processEvents()
    dlg = getattr(controller, "_sections_dialog", None)
    assert dlg is not None
    dlg.list.setCurrentRow(0)
    dlg.btn_goto.click()

    assert narration.prepare_calls
    call = narration.prepare_calls[-1]
    assert call["skip_essay_index"] is True
    # Guard behavior: if the anchor is pre-boundary, we should not force-start.
    assert call["force_start_char"] is None
    assert call["start_char_offset"] == boundary


def test_go_to_section_falls_back_to_chunk_index_when_offset_missing(qapp) -> None:
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication

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
        prepare_calls=[],
    )
    narration._book = type(
        "B",
        (),
        {"normalized_text": "X", "title": "T"},
    )()

    class _Svc:
        def build_for_loaded_book(self, **_):
            return [
                type(
                    "SB",
                    (),
                    {
                        "label": "Chapter 1",
                        "char_offset": 0,
                        "chunk_index": 5,
                        "kind": "chapter",
                        "level": 0,
                    },
                )()
            ]

    controller = SimpleNamespace(
        window=w,
        narration_service=narration,
        structural_bookmark_service=_Svc(),
        _chapters=[],
        _sections_dialog=None,
        _selected_voice=lambda: VoiceProfile(name="bf_emma", reference_audio_paths=[]),
    )

    open_structural_bookmarks_dialog(controller)
    QApplication.processEvents()
    dlg = getattr(controller, "_sections_dialog", None)
    assert dlg is not None
    dlg.list.setCurrentRow(0)

    # Force offset-less navigation by editing the stored item.
    item = dlg.list.item(0)
    it = item.data(0x0100)  # Qt.UserRole
    it2 = type(it)(
        label=it.label,
        char_offset=None,
        chunk_index=5,
        kind=it.kind,
        level=it.level,
    )
    item.setData(0x0100, it2)
    dlg.btn_goto.click()
    assert narration.prepare_calls
    call = narration.prepare_calls[-1]
    assert call["start_playback_index"] == 5
