"""Hand-written stand-ins for the narration service's collaborators.

Every one of these can be told to fail, because most of the uncovered code in
the narration package is a broad handler protecting playback from a
collaborator that misbehaves. No mock library is used anywhere in this
repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.entities.text_chunk import TextChunk


class Boom(RuntimeError):
    """Raised by a fake asked to fail, so a test can name what it forced."""


@dataclass(frozen=True, slots=True)
class FakeMapping:
    speak_text: str
    speak_to_original: list[int]


class FakeMapper:
    """Sanitiser that speaks the text unchanged, or nothing for chosen text."""

    def __init__(self, *, silent_for: set[str] | None = None) -> None:
        self.silent_for = set(silent_for or set())

    def sanitize_with_mapping(self, *, original_text: str) -> FakeMapping:
        if original_text in self.silent_for:
            return FakeMapping(speak_text="", speak_to_original=[])
        return FakeMapping(
            speak_text=original_text,
            speak_to_original=list(range(len(original_text))),
        )


class FakeCacheRepo:
    def __init__(
        self,
        root: Path | None = None,
        *,
        fail_paths: bool = False,
        fail_purge: bool = False,
    ) -> None:
        self.root = root or Path("audio-cache")
        self.fail_paths = fail_paths
        self.fail_purge = fail_purge
        self.purged: list[str] = []

        self.cached: set[tuple[str, str, int]] = set()
        self.parents: list[Path] = []

    def purge_book(self, *, book_id: str) -> None:
        if self.fail_purge:
            raise Boom("purge_book")
        self.purged.append(book_id)

    def exists(self, *, book_id: str, voice_name: str, chunk_id: int) -> bool:
        return (book_id, voice_name, chunk_id) in self.cached

    def ensure_parent_dir(self, path: Path) -> None:
        self.parents.append(path)

    def audio_path(self, *, book_id: str, voice_name: str, chunk_id: int) -> Path:
        if self.fail_paths:
            raise Boom("audio_path")
        return self.root / book_id / voice_name / f"{chunk_id}.wav"

    def alignment_path(self, *, book_id: str, voice_name: str, chunk_id: int) -> Path:
        if self.fail_paths:
            raise Boom("alignment_path")
        return self.root / book_id / voice_name / f"{chunk_id}.json"


class FakeAlignmentIO:
    def __init__(self, *, loaded=None, fail_save: bool = False) -> None:
        self.loaded = loaded
        self.fail_save = fail_save
        self.saved: list[tuple[Path, object]] = []

    def load(self, path: Path):
        return self.loaded

    def save(self, *, path: Path, alignment) -> None:
        if self.fail_save:
            raise Boom("save")
        self.saved.append((path, alignment))


@dataclass(frozen=True, slots=True)
class FakeSpan:
    start_char: int
    end_char: int
    audio_start_ms: int
    audio_end_ms: int
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class FakeEstimate:
    duration_ms: int
    spans: list[FakeSpan]


class FakeEstimatedAligner:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def estimate(
        self, *, chunk_id: int, speak_text: str, speak_to_original, duration_ms: int
    ) -> FakeEstimate:
        self.calls.append(
            {
                "chunk_id": chunk_id,
                "speak_text": speak_text,
                "speak_to_original": list(speak_to_original),
                "duration_ms": duration_ms,
            }
        )
        return FakeEstimate(
            duration_ms=duration_ms,
            spans=[FakeSpan(0, max(1, len(speak_text)), 0, duration_ms)],
        )


class FakeSynchronizer:
    def __init__(self, span: tuple[int | None, int | None] = (1, 2)) -> None:
        self.span = span
        self.seen: list[object] = []

    def resolve_span(self, *, alignment, chunk_local_ms: int):
        self.seen.append(alignment)
        return self.span


class FakeAudioStreamer:
    def __init__(self, *, fail_rate: bool = False, fail_volume: bool = False) -> None:
        self.fail_rate = fail_rate
        self.fail_volume = fail_volume
        self.events: list[str] = []

    def pause(self) -> None:
        self.events.append("pause")

    def resume(self) -> None:
        self.events.append("resume")

    def stop(self) -> None:
        self.events.append("stop")

    def set_playback_rate(self, rate) -> None:
        if self.fail_rate:
            raise Boom("set_playback_rate")
        self.events.append("rate")

    def set_volume(self, volume) -> None:
        if self.fail_volume:
            raise Boom("set_volume")
        self.events.append("volume")

    def start(
        self,
        *,
        chunk_audio_paths,
        on_chunk_start,
        on_chunk_end,
        on_playback_progress,
    ) -> None:
        """Record the callbacks and drain the path iterator, as a real streamer
        would, without touching a device. Tests drive the callbacks directly."""

        self.events.append("start")
        self.on_chunk_start = on_chunk_start
        self.on_chunk_end = on_chunk_end
        self.on_playback_progress = on_playback_progress
        self.paths = list(chunk_audio_paths)


class FakeBookmarkService:
    def __init__(self, *, fail: bool = False, fail_delete: bool = False) -> None:
        self.fail = fail
        self.fail_delete = fail_delete
        self.saved: list[dict] = []
        self.deleted: list[str] = []
        self.resume: object | None = None
        self.fail_load: bool = False

    def load_resume_position(self, *, book_id: str):
        if self.fail_load:
            raise Boom("load_resume_position")
        return self.resume

    def save_resume_position(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> None:
        if self.fail:
            raise Boom("save_resume_position")
        self.saved.append(
            {
                "book_id": book_id,
                "char_offset": char_offset,
                "chunk_index": chunk_index,
            }
        )

    def delete_book_state(self, *, book_id: str) -> None:
        if self.fail_delete:
            raise Boom("delete_book_state")
        self.deleted.append(book_id)


class FakePreferencesRepo:
    def __init__(
        self,
        *,
        volume=None,
        fail_volume: bool = False,
        fail_save_path: bool = False,
        fail_clear_path: bool = False,
    ) -> None:
        self.volume = volume
        self.fail_volume = fail_volume
        self.fail_save_path = fail_save_path
        self.fail_clear_path = fail_clear_path
        self.saved_paths: list[Path] = []
        self.cleared = 0

    def load_playback_volume(self):
        if self.fail_volume:
            raise Boom("load_playback_volume")
        return self.volume

    def save_last_book_path(self, path: Path) -> None:
        if self.fail_save_path:
            raise Boom("save_last_book_path")
        self.saved_paths.append(path)

    def clear_last_book_path(self) -> None:
        if self.fail_clear_path:
            raise Boom("clear_last_book_path")
        self.cleared += 1


class FakeBookRepo:
    def __init__(self, book=None) -> None:
        self.book = book
        self.loaded: list[Path] = []

    def load(self, source_path: Path):
        self.loaded.append(source_path)
        return self.book


class FakeChunkingService:
    def __init__(self, chunks: list[TextChunk] | None = None) -> None:
        self.chunks = chunks or []
        self.calls: list[str] = []

    def chunk_text(self, text: str) -> list[TextChunk]:
        self.calls.append(text)
        return list(self.chunks)


class FakeLog:
    def __init__(self) -> None:
        self.exceptions: list[str] = []

    def exception(self, message: str, *args, **kwargs) -> None:
        self.exceptions.append(message)

    def warning(self, message: str, *args, **kwargs) -> None:
        pass

    def info(self, message: str, *args, **kwargs) -> None:
        pass

    def debug(self, message: str, *args, **kwargs) -> None:
        pass


class FakeEngine:
    def __init__(self, name: str = "Fake Engine", *, fail: bool = False) -> None:
        self.engine_name = name
        self.fail = fail
        self.synthesized: list[dict] = []

    def synthesize_to_file(
        self, *, text: str, voice_profile, output_path: Path, device, language
    ) -> None:
        if self.fail:
            raise Boom("synthesize_to_file")
        self.synthesized.append({"text": text, "output_path": output_path})


@dataclass(frozen=True, slots=True)
class FakeResumePosition:
    char_offset: int


@dataclass(frozen=True, slots=True)
class FakeStart:
    start_char: int = 0
    reason: str = "body"


class FakeNavigationChunkService:
    def __init__(self, chunks=None, *, fail: bool = False, start_char: int = 0) -> None:
        self.chunks = chunks or []
        self.fail = fail
        self.start = FakeStart(start_char)

    def build_chunks(self, *, book_text: str, document, **kwargs):
        if self.fail:
            raise Boom("build_chunks")
        return list(self.chunks), self.start
