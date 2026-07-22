"""The voice picker: sex and region toggles filtering the dropdown.

The dropdown only ever shows the current sex and region combination;
the toggles carry their state as glyphs; the user's pick survives a
refresh when it still matches; and the deliberate default (bf_emma) wins
over whatever sorts first alphabetically.
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


def test_default_is_british_female_with_emma_selected(qapp) -> None:
    c = _controller(qapp, FULL_SET)

    assert _labels(c) == [
        "Alice (British Female)",
        "Emma (British Female)",
        "Isabella (British Female)",
    ]
    # The deliberate default beats alphabetical order.
    assert c.window.voice_combo.currentData() == "bf_emma"
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
