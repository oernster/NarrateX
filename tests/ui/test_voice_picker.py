"""The voice picker: sex and region toggles filtering the dropdown.

The dropdown only ever shows the current sex and region combination; the
toggles carry their state as glyphs; the user's pick survives a refresh
when it still matches. No voice is defaulted: the picker is disabled until
a book loads, then an amber attention ring flashes until first touched,
holds steady until a voice is chosen and clears on choice.
"""

from __future__ import annotations

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController

from tests.ui.ui_controller_fakes import FakeBookmarks, FakeNarration, FakeVoiceRepo

FULL_SET = [
    "bf_alice",
    "bf_emma",
    "bf_isabella",
    "bm_daniel",
    "bm_george",
    "af_bella",
    "af_heart",
    "am_adam",
    "am_michael",
]


def _controller(qapp, names: list[str]) -> UiController:
    del qapp
    return UiController(
        window=MainWindow(),
        narration_service=FakeNarration(
            listeners=[],
            state=NarrationState(
                status=NarrationStatus.IDLE,
                current_chunk_id=None,
                total_chunks=None,
                progress=0.0,
            ),
        ),  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=None,
        voice_service=VoiceProfileService(
            repo=FakeVoiceRepo(
                profiles=[VoiceProfile(name=n, reference_audio_paths=[]) for n in names]
            )
        ),
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )


def _labels(c: UiController) -> list[str]:
    combo = c.window.voice_combo
    return [combo.itemText(i) for i in range(combo.count())]


def test_default_lists_british_females_with_nothing_selected(qapp) -> None:
    c = _controller(qapp, FULL_SET)

    assert _labels(c) == [
        "Alice (British Female)",
        "Emma (British Female)",
        "Isabella (British Female)",
    ]
    # No voice is defaulted: the combo rests on its mic placeholder.
    assert c.window.voice_combo.currentIndex() == -1
    assert c.window.voice_combo.currentData() is None
    assert c.window.voice_combo.placeholderText() == "🎙 Select Voice"
    assert c.window.btn_voice_sex.text() == "♀"
    assert c.window.btn_voice_region.text() == "🇬🇧"
    # The glyphs display as centred icons, not baseline-riding text.
    assert not c.window.btn_voice_sex.icon().isNull()
    assert not c.window.btn_voice_region.icon().isNull()


def test_sex_toggle_switches_to_british_males(qapp) -> None:
    c = _controller(qapp, FULL_SET)

    c.toggle_voice_sex()

    assert _labels(c) == ["Daniel (British Male)", "George (British Male)"]
    assert c.window.btn_voice_sex.text() == "♂"


def test_region_cycle_reaches_american_voices(qapp) -> None:
    c = _controller(qapp, FULL_SET)

    c.cycle_voice_region()

    assert _labels(c) == ["Bella (American Female)", "Heart (American Female)"]
    assert c.window.btn_voice_region.text() == "🇺🇸"

    # Cycling wraps back to British.
    c.cycle_voice_region()
    assert c.window.btn_voice_region.text() == "🇬🇧"


def test_a_pick_survives_a_refresh_when_it_still_matches(qapp) -> None:
    c = _controller(qapp, FULL_SET)

    combo = c.window.voice_combo
    combo.setCurrentIndex(
        [combo.itemData(i) for i in range(combo.count())].index("bf_isabella")
    )

    c.refresh_voices()

    assert combo.currentData() == "bf_isabella"


def test_an_unparseable_voice_shows_in_every_combination(qapp) -> None:
    c = _controller(qapp, ["bf_emma", "customvoice", "zf_zoe", "bx_bob"])

    # Unknown prefixes and free-form names are never filtered out.
    for _ in range(2):
        for _ in range(2):
            data = [
                c.window.voice_combo.itemData(i)
                for i in range(c.window.voice_combo.count())
            ]
            assert "customvoice" in data
            assert "zf_zoe" in data
            assert "bx_bob" in data
            c.toggle_voice_sex()
        c.cycle_voice_region()


def test_no_voices_shows_the_placeholder(qapp) -> None:
    c = _controller(qapp, [])

    assert _labels(c) == ["(no voices found)"]


def test_toggles_lock_with_the_dropdown_during_playback(qapp) -> None:
    c = _controller(qapp, FULL_SET)

    def _state(status: NarrationStatus) -> NarrationState:
        return NarrationState(
            status=status,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        )

    c._apply_state(_state(NarrationStatus.PLAYING))  # noqa: SLF001
    assert c.window.btn_voice_sex.isEnabled() is False
    assert c.window.btn_voice_region.isEnabled() is False

    c._apply_state(_state(NarrationStatus.IDLE))  # noqa: SLF001
    assert c.window.btn_voice_sex.isEnabled() is True
    assert c.window.btn_voice_region.isEnabled() is True


class _BookAwareNarration(FakeNarration):
    """A fake whose loaded_book answer the tests control."""

    def __init__(self, *, listeners, state, book=None):
        super().__init__(listeners=listeners, state=state)
        self.book = book
        self.presynth_calls: list = []

    def loaded_book(self):
        return self.book

    def presynthesize_start(self, voice, *, cancel_event=None):
        self.presynth_calls.append((voice, cancel_event))


def _book_aware_controller(qapp, *, book):
    del qapp
    return UiController(
        window=MainWindow(),
        narration_service=_BookAwareNarration(
            listeners=[],
            state=NarrationState(
                status=NarrationStatus.IDLE,
                current_chunk_id=None,
                total_chunks=None,
                progress=0.0,
            ),
            book=book,
        ),  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=None,
        voice_service=VoiceProfileService(
            repo=FakeVoiceRepo(
                profiles=[
                    VoiceProfile(name=n, reference_audio_paths=[]) for n in FULL_SET
                ]
            )
        ),
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )


def test_picker_is_disabled_until_a_book_loads(qapp) -> None:
    c = _book_aware_controller(qapp, book=None)

    assert c.window.voice_combo.isEnabled() is False
    assert c.window.btn_voice_sex.isEnabled() is False
    assert c.window.btn_voice_region.isEnabled() is False


def test_picker_enables_once_a_book_is_present(qapp) -> None:
    c = _book_aware_controller(qapp, book=object())
    c.refresh_voices()

    assert c.window.voice_combo.isEnabled() is True
    assert c.window.btn_voice_sex.isEnabled() is True


def test_attention_flashes_then_steadies_then_clears(qapp) -> None:
    from PySide6.QtCore import QEvent

    c = _book_aware_controller(qapp, book=object())
    combo = c.window.voice_combo
    attention = c._picker_attention  # noqa: SLF001

    # A book landing starts the flash.
    attention.start()
    assert combo.property("attention") is True
    assert attention._timer.isActive()  # noqa: SLF001

    # The flash alternates the ring.
    attention.tick()
    assert combo.property("attention") is False
    attention.tick()
    assert combo.property("attention") is True

    # First interaction stops the flashing but keeps the ring.
    attention.eventFilter(combo, QEvent(QEvent.Enter))
    assert attention._timer.isActive() is False  # noqa: SLF001
    assert combo.property("attention") is True

    # Choosing a voice clears the prompt and pre-synthesises.
    combo.setCurrentIndex(0)
    assert combo.property("attention") is False
    assert c.narration_service.presynth_calls, "presynthesis did not start"


def test_attention_does_not_start_when_a_voice_is_already_chosen(qapp) -> None:
    c = _book_aware_controller(qapp, book=object())
    combo = c.window.voice_combo
    combo.setCurrentIndex(1)
    attention = c._picker_attention  # noqa: SLF001

    attention.start()

    assert combo.property("attention") in (None, False)
    assert attention._timer.isActive() is False  # noqa: SLF001


def test_losing_a_pick_to_a_toggle_reflashes_the_prompt(qapp) -> None:
    # Switching region (or sex) can drop the chosen voice back to the
    # placeholder; that must re-raise the amber prompt like a fresh book.
    c = _book_aware_controller(qapp, book=object())
    combo = c.window.voice_combo
    attention = c._picker_attention  # noqa: SLF001
    combo.setCurrentIndex(0)
    assert attention._timer.isActive() is False  # noqa: SLF001

    c.cycle_voice_region()

    assert combo.currentIndex() == -1
    assert combo.property("attention") is True
    assert attention._timer.isActive() is True  # noqa: SLF001


def test_toggling_with_no_pick_does_not_restart_the_prompt(qapp) -> None:
    c = _book_aware_controller(qapp, book=object())
    attention = c._picker_attention  # noqa: SLF001

    c.cycle_voice_region()

    assert attention._timer.isActive() is False  # noqa: SLF001


def test_book_probe_failure_counts_as_loaded() -> None:
    # The probe is permissive: a service whose loaded_book raises must not
    # lock the picker shut.
    from types import SimpleNamespace

    from voice_reader.ui import _ui_controller_voices as voices

    def _boom():
        raise RuntimeError("probe exploded")

    controller = SimpleNamespace(narration_service=SimpleNamespace(loaded_book=_boom))
    assert voices.book_is_loaded(controller) is True
