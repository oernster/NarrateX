"""The one question every door to opening a book asks."""

from __future__ import annotations

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.ui._ui_controller_book_loading import narration_holds_the_book


class _Controller:
    def __init__(self, service=None) -> None:
        if service is not None:
            self.narration_service = service


class _Engine:
    def __init__(self, state) -> None:
        self.state = state


def _state(status: NarrationStatus) -> NarrationState:
    return NarrationState(
        status=status, current_chunk_id=None, total_chunks=None, progress=0.0
    )


def test_a_playing_engine_holds_the_book() -> None:
    controller = _Controller(_Engine(_state(NarrationStatus.PLAYING)))

    assert narration_holds_the_book(controller) is True


def test_a_stopped_engine_holds_nothing() -> None:
    controller = _Controller(_Engine(_state(NarrationStatus.STOPPED)))

    assert narration_holds_the_book(controller) is False


def test_no_narration_service_at_all_holds_nothing() -> None:
    """A build with nothing wired is narrating nothing, so nothing is locked."""

    assert narration_holds_the_book(_Controller()) is False


def test_a_service_whose_state_is_not_a_narration_state_holds_nothing() -> None:
    assert narration_holds_the_book(_Controller(_Engine("playing"))) is False
