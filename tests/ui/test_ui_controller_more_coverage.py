from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.idea_map_service import IdeaMapService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController

from tests.ui.ui_controller_fakes import (
    FakeBookmarks,
    FakeIdeasRepo,
    FakeNarration,
    FakeVoiceRepo,
    InlineThread,
)


def test_voice_label_formats_kokoro_ids() -> None:
    vp = VoiceProfile(name="bf_emma", reference_audio_paths=[])
    assert UiController._voice_label(vp) == "Emma (British Female)"


def test_voice_label_prettifies_snake_case() -> None:
    vp = VoiceProfile(name="my_custom_voice", reference_audio_paths=[])
    assert UiController._voice_label(vp) == "My Custom Voice"


def test_refresh_voices_filters_system_and_sorts(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    repo = FakeVoiceRepo(
        profiles=[
            VoiceProfile(name="system", reference_audio_paths=[]),
            VoiceProfile(name="bf_emma", reference_audio_paths=[]),
            VoiceProfile(name="am_michael", reference_audio_paths=[]),
        ]
    )
    voice_service = VoiceProfileService(repo=repo)
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )
    c.refresh_voices()

    # system filtered out, remaining sorted by label.
    assert w.voice_combo.count() == 2


def test_refresh_voices_puts_british_first_then_alphabetical(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    repo = FakeVoiceRepo(
        profiles=[
            VoiceProfile(name="am_michael", reference_audio_paths=[]),
            VoiceProfile(name="bm_george", reference_audio_paths=[]),
            VoiceProfile(name="af_bella", reference_audio_paths=[]),
            VoiceProfile(name="bf_emma", reference_audio_paths=[]),
            VoiceProfile(name="af_alloy", reference_audio_paths=[]),
        ]
    )
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        voice_service=VoiceProfileService(repo=repo),
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )
    c.refresh_voices()

    labels = [w.voice_combo.itemText(i) for i in range(w.voice_combo.count())]
    assert labels == [
        "Emma (British Female)",
        "George (British Male)",
        "Alloy (American Female)",
        "Bella (American Female)",
        "Michael (American Male)",
    ]


def test_ui_controller_has_no_search_button(qapp) -> None:
    """Search was removed with the Sections-only brain button design."""

    del qapp
    w = MainWindow()

    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo(profiles=[]))

    UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    assert not hasattr(w, "btn_search")


def test_select_book_cancel_noop(monkeypatch, qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    # Cancel dialog.
    monkeypatch.setattr(
        __import__(
            "voice_reader.ui.ui_controller",
            fromlist=["QFileDialog"],
        ).QFileDialog,
        "getOpenFileName",
        lambda *a, **k: ("", ""),
    )
    c.select_book()


def test_select_book_cancels_ideas_job_when_switching_books(monkeypatch, qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo(profiles=[]))

    # Arrange: controller thinks an ideas indexing job is running for this book.
    class _Mgr:
        cancel_calls: list[str] = []

        def cancel(self, *, book_id: str) -> None:
            self.cancel_calls.append(str(book_id))

    mgr = _Mgr()
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        idea_indexing_manager=mgr,  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )
    c._ideas_index_job_book_id = "b1"  # noqa: SLF001
    # Timer is optional; this test only asserts cancel() is called.
    c._ideas_index_timer = None  # noqa: SLF001

    # Cancel dialog: do not open a new book.
    monkeypatch.setattr(
        __import__(
            "voice_reader.ui.ui_controller",
            fromlist=["QFileDialog"],
        ).QFileDialog,
        "getOpenFileName",
        lambda *a, **k: ("", ""),
    )

    c.select_book()
    assert mgr.cancel_calls == ["b1"]


def test_on_app_exit_cancels_ideas_job(monkeypatch, qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo(profiles=[]))

    class _Mgr:
        cancel_calls: list[str] = []

        def cancel(self, *, book_id: str) -> None:
            self.cancel_calls.append(str(book_id))

    mgr = _Mgr()
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        idea_indexing_manager=mgr,  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )
    c._ideas_index_job_book_id = "b1"  # noqa: SLF001
    c._ideas_index_timer = None  # noqa: SLF001

    c.on_app_exit()
    assert mgr.cancel_calls == ["b1"]


def test_select_book_cover_extractor_failure_is_ignored(
    monkeypatch, qapp, tmp_path: Path
) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    p = tmp_path / "a.txt"
    p.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        __import__(
            "voice_reader.ui.ui_controller",
            fromlist=["QFileDialog"],
        ).QFileDialog,
        "getOpenFileName",
        lambda *a, **k: (str(p), ""),
    )
    monkeypatch.setattr(
        c,
        "_cover_extractor",
        SimpleNamespace(
            extract_cover_bytes=lambda path: (_ for _ in ()).throw(RuntimeError("x"))
        ),
    )
    # Run the load worker inline so the failure path executes deterministically.
    from voice_reader.ui import _ui_controller_book_loading as book_loading

    monkeypatch.setattr(book_loading.threading, "Thread", InlineThread)
    c.select_book()
    assert c._book_load_inflight is False  # noqa: SLF001
