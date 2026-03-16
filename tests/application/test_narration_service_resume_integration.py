from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.narration_service import NarrationService
from voice_reader.domain.entities.book import Book
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.services.chunking_service import ChunkingService


@dataclass(frozen=True, slots=True)
class _FakeBookRepo:
    book: Book

    def load(self, source_path: Path) -> Book:
        del source_path
        return self.book


@dataclass
class _FakeCache:
    base: Path

    def audio_path(self, *, book_id: str, voice_name: str, chunk_id: int) -> Path:
        return self.base / book_id / voice_name / f"{chunk_id}.wav"

    def exists(self, *, book_id: str, voice_name: str, chunk_id: int) -> bool:
        del book_id, voice_name, chunk_id
        return False

    def ensure_parent_dir(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    def alignment_path(self, *, book_id: str, voice_name: str, chunk_id: int) -> Path:
        return self.base / book_id / voice_name / f"{chunk_id}.align.json"

    def alignment_exists(self, *, book_id: str, voice_name: str, chunk_id: int) -> bool:
        del book_id, voice_name, chunk_id
        return False


@dataclass
class _FakeTTSEngine:
    @property
    def engine_name(self) -> str:
        return "fake"

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
        device: str,
        language: str,
    ) -> Path:
        del text, voice_profile, device, language
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"RIFF....WAVE")
        return output_path


@dataclass
class _FakeStreamer:
    def set_playback_rate(self, rate) -> None:
        del rate

    def set_volume(self, volume) -> None:
        del volume

    def start(
        self,
        *,
        chunk_audio_paths,
        on_chunk_start=None,
        on_chunk_end=None,
        on_playback_progress=None,
    ) -> None:
        del chunk_audio_paths, on_chunk_start, on_chunk_end, on_playback_progress

    def wait(self, timeout_seconds: float | None = None) -> bool:
        del timeout_seconds
        return True

    def pause(self) -> None:
        return

    def resume(self) -> None:
        return

    def stop(self) -> None:
        return


@dataclass
class _FakeBookmarkService:
    resume_chunk_index: int | None
    load_calls: int = 0
    save_calls: list[tuple[str, int, int]] = field(default_factory=list)

    def load_resume_position(self, *, book_id: str):
        self.load_calls += 1
        assert book_id == "book-1"
        if self.resume_chunk_index is None:
            return None
        # ResumePosition is a domain object; NarrationService only needs chunk_index.
        return type(
            "RP",
            (),
            {
                "chunk_index": int(self.resume_chunk_index),
                "char_offset": 0,
                "updated_at": None,
            },
        )()

    def save_resume_position(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> None:
        self.save_calls.append((str(book_id), int(char_offset), int(chunk_index)))


def test_prepare_uses_resume_position_when_present(tmp_path: Path) -> None:
    book = Book(id="book-1", title="T", raw_text="x", normalized_text="Hello world")
    svc = NarrationService(
        book_repo=_FakeBookRepo(book=book),  # type: ignore[arg-type]
        cache_repo=_FakeCache(base=tmp_path),  # type: ignore[arg-type]
        tts_engine=_FakeTTSEngine(),  # type: ignore[arg-type]
        audio_streamer=_FakeStreamer(),  # type: ignore[arg-type]
        chunking_service=ChunkingService(min_chars=1, max_chars=5),
        device="cpu",
        language="en",
        bookmark_service=_FakeBookmarkService(
            resume_chunk_index=7
        ),  # type: ignore[arg-type]
    )
    svc.load_book(tmp_path / "book.txt")
    svc.prepare(voice=VoiceProfile(name="v", reference_audio_paths=[]))
    # Uses resume chunk index as the start playback index.
    assert svc._start_playback_index == 7  # noqa: SLF001


def test_prepare_starts_from_beginning_when_no_resume(tmp_path: Path) -> None:
    book = Book(id="book-1", title="T", raw_text="x", normalized_text="Hello world")
    bs = _FakeBookmarkService(resume_chunk_index=None)
    svc = NarrationService(
        book_repo=_FakeBookRepo(book=book),  # type: ignore[arg-type]
        cache_repo=_FakeCache(base=tmp_path),  # type: ignore[arg-type]
        tts_engine=_FakeTTSEngine(),  # type: ignore[arg-type]
        audio_streamer=_FakeStreamer(),  # type: ignore[arg-type]
        chunking_service=ChunkingService(min_chars=1, max_chars=5),
        device="cpu",
        language="en",
        bookmark_service=bs,  # type: ignore[arg-type]
    )
    svc.load_book(tmp_path / "book.txt")
    svc.prepare(voice=VoiceProfile(name="v", reference_audio_paths=[]))
    assert svc._start_playback_index == 0  # noqa: SLF001
    assert bs.load_calls == 1


def test_load_book_persists_resume_position_for_previous_book(tmp_path: Path) -> None:
    """Selecting a new book should autosave resume for the previously loaded one.

    This covers the UI flow where the user opens a new book while PAUSED/STOPPED.
    The persistence is owned by NarrationService, via load_book() calling
    _maybe_save_resume_position().
    """

    book1 = Book(id="book-1", title="T1", raw_text="x", normalized_text="Hello")
    book2 = Book(id="book-2", title="T2", raw_text="x", normalized_text="World")

    class _SwitchingRepo:
        def __init__(self) -> None:
            self.calls = 0

        def load(self, source_path: Path) -> Book:
            self.calls += 1
            if self.calls == 1:
                return book1
            return book2

    bs = _FakeBookmarkService(resume_chunk_index=None)
    svc = NarrationService(
        book_repo=_SwitchingRepo(),  # type: ignore[arg-type]
        cache_repo=_FakeCache(base=tmp_path),  # type: ignore[arg-type]
        tts_engine=_FakeTTSEngine(),  # type: ignore[arg-type]
        audio_streamer=_FakeStreamer(),  # type: ignore[arg-type]
        chunking_service=ChunkingService(min_chars=1, max_chars=5),
        device="cpu",
        language="en",
        bookmark_service=bs,  # type: ignore[arg-type]
    )

    # First book load sets the current book, but does not save (no previous book).
    svc.load_book(tmp_path / "b1.txt")

    # Simulate an existing play position so a resume can be saved.
    svc._start_playback_index = 0  # noqa: SLF001
    svc._set_state(
        NarrationState(
            status=NarrationStatus.PAUSED,
            current_chunk_id=2,
            total_chunks=10,
            progress=0.2,
            audible_start=123,
        )
    )

    svc.load_book(tmp_path / "b2.txt")
    assert bs.save_calls
    saved_book_id, saved_char, saved_chunk_idx = bs.save_calls[-1]
    assert saved_book_id == "book-1"
    assert saved_char == 123
    assert saved_chunk_idx == 2


def test_load_book_stops_active_play_thread_to_allow_new_play(tmp_path: Path) -> None:
    """Regression: switching books from PAUSED must not leave the old thread alive.

    If the previous narration thread stays alive, [`start()`](voice_reader/application/services/narration_service.py:313)
    can no-op, making the new book fail to play.
    """

    book1 = Book(id="book-1", title="T1", raw_text="x", normalized_text="Hello")
    book2 = Book(id="book-2", title="T2", raw_text="x", normalized_text="World")

    class _SwitchingRepo:
        def __init__(self) -> None:
            self.calls = 0

        def load(self, source_path: Path) -> Book:
            self.calls += 1
            return book1 if self.calls == 1 else book2

    # Arrange a fake playback thread that appears alive.
    class _AliveThread:
        def is_alive(self) -> bool:
            return True

    svc = NarrationService(
        book_repo=_SwitchingRepo(),  # type: ignore[arg-type]
        cache_repo=_FakeCache(base=tmp_path),  # type: ignore[arg-type]
        tts_engine=_FakeTTSEngine(),  # type: ignore[arg-type]
        audio_streamer=_FakeStreamer(),  # type: ignore[arg-type]
        chunking_service=ChunkingService(min_chars=1, max_chars=5),
        device="cpu",
        language="en",
        bookmark_service=_FakeBookmarkService(resume_chunk_index=None),  # type: ignore[arg-type]
    )

    svc.load_book(tmp_path / "b1.txt")

    # Simulate paused playback still having a live thread.
    svc._play_thread = _AliveThread()  # type: ignore[assignment]  # noqa: SLF001
    svc._set_state(
        NarrationState(
            status=NarrationStatus.PAUSED,
            current_chunk_id=0,
            total_chunks=1,
            progress=0.0,
            audible_start=0,
        )
    )

    stop_calls: list[None] = []
    orig_stop = svc.stop

    def _stop_spy() -> None:
        stop_calls.append(None)
        orig_stop()

    svc.stop = _stop_spy  # type: ignore[method-assign]

    svc.load_book(tmp_path / "b2.txt")
    assert stop_calls, "Expected load_book() to stop active playback before switching"


def test_stop_accepts_persist_resume_false(tmp_path: Path) -> None:
    """Coverage: stop(persist_resume=False) is used by queued navigation (Ideas GoTo)."""

    book = Book(id="book-1", title="T", raw_text="x", normalized_text="Hello")

    svc = NarrationService(
        book_repo=_FakeBookRepo(book=book),
        cache_repo=_FakeCache(base=tmp_path),
        tts_engine=_FakeTTSEngine(),
        audio_streamer=_FakeStreamer(),
        chunking_service=ChunkingService(min_chars=1, max_chars=5),
        device="cpu",
        language="en",
        bookmark_service=_FakeBookmarkService(resume_chunk_index=None),  # type: ignore[arg-type]
    )

    svc.load_book(tmp_path / "b1.txt")
    svc.stop(persist_resume=False)
