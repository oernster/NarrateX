"""Pressing Play with no book must inform, never traceback.

Regression: on a fresh launch (no last book) the play/pause slot let
prepare() raise ValueError("Book not loaded") straight to the console. The
transport now says what to do in the status bar and the slot boundary
converts anything unexpected into a logged error.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController

from tests.ui.ui_controller_fakes import FakeBookmarks, FakeNarration, FakeVoiceRepo


@dataclass
class _BooklessNarration(FakeNarration):
    prepare_calls: int = 0

    def loaded_book(self):
        return None

    def prepare(self, **kwargs):
        del kwargs
        self.prepare_calls += 1
        raise AssertionError("prepare must not be reached without a book")


@dataclass
class _ExplodingNarration(FakeNarration):
    def prepare(self, **kwargs):
        del kwargs
        raise ValueError("Book not loaded")


def _controller(qapp, narration) -> UiController:
    del qapp
    return UiController(
        window=MainWindow(),
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=None,
        voice_service=VoiceProfileService(
            repo=FakeVoiceRepo(
                profiles=[VoiceProfile(name="bf_emma", reference_audio_paths=[])]
            )
        ),
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


def test_play_without_a_book_informs_instead_of_raising(qapp) -> None:
    narration = _BooklessNarration(listeners=[], state=_idle_state())
    c = _controller(qapp, narration)

    c.toggle_play_pause()

    assert narration.prepare_calls == 0
    assert "Select a book" in c.window.lbl_status.text()


def test_an_unexpected_prepare_failure_is_contained(qapp) -> None:
    # No loaded_book() probe on this fake, so play() proceeds to prepare(),
    # which raises: the slot boundary must contain it.
    narration = _ExplodingNarration(listeners=[], state=_idle_state())
    c = _controller(qapp, narration)
    c.window.voice_combo.setCurrentIndex(0)

    c.toggle_play_pause()

    assert "Playback failed" in c.window.lbl_status.text()


def test_the_real_service_flow_still_reaches_prepare(qapp, tmp_path: Path) -> None:
    # A fake with a loaded book and a working prepare: the guard must not
    # block the normal path.
    del tmp_path

    @dataclass
    class _LoadedNarration(FakeNarration):
        prepare_calls: int = 0
        start_calls: int = 0

        def loaded_book(self):
            return object()

        def prepare(self, **kwargs):
            del kwargs
            self.prepare_calls += 1

        def start(self):
            self.start_calls += 1

    narration = _LoadedNarration(listeners=[], state=_idle_state())
    c = _controller(qapp, narration)
    c.window.voice_combo.setCurrentIndex(0)

    c.toggle_play_pause()

    assert narration.prepare_calls == 1
    assert narration.start_calls == 1
