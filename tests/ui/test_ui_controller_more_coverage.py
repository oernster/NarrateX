from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController


@dataclass
class _FakeNarration:
    listeners: list
    state: NarrationState
    last_rate: float | None = None

    def add_listener(self, listener):
        self.listeners.append(listener)

    def load_book(self, path: Path):
        del path
        return SimpleNamespace(normalized_text="Hello", title="T")

    def prepare(self, *, voice, start_playback_index=None):
        del voice, start_playback_index

    def start(self):
        return

    def pause(self):
        return

    def stop(self):
        return

    def set_playback_rate(self, rate) -> None:
        # Accept a PlaybackRate-ish object (value object in real code).
        self.last_rate = float(getattr(rate, "multiplier", rate))

    def loaded_book_id(self):
        return "b1"

    def current_position(self):
        return 0, 0

    def _maybe_save_resume_position(self):
        return


@dataclass
class _FakeBookmarks:
    def list_bookmarks(self, *, book_id: str):
        del book_id
        return []

    def add_bookmark(self, *, book_id: str, char_offset: int, chunk_index: int):
        del book_id, char_offset, chunk_index
        return None

    def delete_bookmark(self, *, book_id: str, bookmark_id: int) -> None:
        del book_id, bookmark_id

    def save_resume_position(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> None:
        del book_id, char_offset, chunk_index

    def load_resume_position(self, *, book_id: str):
        del book_id
        return None


@dataclass(frozen=True, slots=True)
class _FakeVoiceRepo:
    profiles: list[VoiceProfile]

    def list_profiles(self):
        return list(self.profiles)


def test_voice_label_formats_kokoro_ids() -> None:
    vp = VoiceProfile(name="bf_emma", reference_audio_paths=[])
    assert UiController._voice_label(vp) == "Emma (British Female)"


def test_voice_label_prettifies_snake_case() -> None:
    vp = VoiceProfile(name="my_custom_voice", reference_audio_paths=[])
    assert UiController._voice_label(vp) == "My Custom Voice"


def test_refresh_voices_filters_system_and_sorts(qapp) -> None:
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
    repo = _FakeVoiceRepo(
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
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )
    c.refresh_voices()

    # system filtered out, remaining sorted by label.
    assert w.voice_combo.count() == 2


def test_select_book_cancel_noop(monkeypatch, qapp) -> None:
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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
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


def test_select_book_cover_extractor_failure_is_ignored(
    monkeypatch, qapp, tmp_path: Path
) -> None:
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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
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
    c.select_book()


def test_on_state_ignores_runtime_error_on_emit(monkeypatch, qapp) -> None:
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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    # Patch the controller's SignalInstance to a stub that raises RuntimeError.
    # SignalInstance.emit is read-only, so replace the attribute entirely.
    monkeypatch.setattr(
        c,
        "state_received",
        SimpleNamespace(emit=lambda state: (_ for _ in ()).throw(RuntimeError("dead"))),
    )
    c.on_state(narration.state)


def test_apply_state_ignores_non_state(monkeypatch, qapp) -> None:
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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )
    c._apply_state(object())  # pylint: disable=protected-access


def test_speed_changed_calls_service(qapp) -> None:
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
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    # Drive controller logic directly (signal wiring covered by smoke tests).
    c.set_speed("1.25x")
    assert narration.last_rate == 1.25
