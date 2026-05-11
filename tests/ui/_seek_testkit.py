"""Testkit for click-to-seek UI controller tests.

Keep shared fakes here so individual test modules stay comfortably under the
repo's per-file LOC guardrail.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from voice_reader.domain.entities.voice_profile import VoiceProfile


@dataclass
class NavFake:
    chunks: list
    exc: Exception | None = None

    def build_chunks(self, *, book_text: str, skip_essay_index: bool = True):
        del book_text, skip_essay_index
        if self.exc is not None:
            raise self.exc
        return list(self.chunks), None


@dataclass
class NarrationSvcFake:
    stop_calls: list
    prepare_calls: list
    start_calls: int = 0
    loaded_book_id_exc: Exception | None = None

    def stop(self, *, persist_resume: bool = True):
        self.stop_calls.append(bool(persist_resume))

    def prepare(self, *, voice, start_playback_index: int, persist_resume: bool = True):
        self.prepare_calls.append(
            {
                "voice": voice,
                "start_playback_index": int(start_playback_index),
                "persist_resume": bool(persist_resume),
            }
        )

    def start(self):
        self.start_calls += 1

    def loaded_book_id(self):
        if self.loaded_book_id_exc is not None:
            raise self.loaded_book_id_exc
        return "b1"


def make_controller(
    *,
    text: str = "x",
    nav: object | None = None,
    svc: object | None = None,
    voice: VoiceProfile | None = None,
):
    if svc is None:
        svc = NarrationSvcFake(stop_calls=[], prepare_calls=[])
    if nav is None:
        nav = NavFake(chunks=[])
    if voice is None:
        voice = VoiceProfile(name="v", reference_audio_paths=[])

    window = SimpleNamespace(
        reader=SimpleNamespace(toPlainText=lambda: text),
        highlight_range=lambda *_: None,
        lbl_status=SimpleNamespace(setText=lambda *_: None, text=lambda: ""),
    )
    bookmark_service = SimpleNamespace(save_resume_position=lambda **_: None)
    return SimpleNamespace(
        _log=SimpleNamespace(exception=lambda *_: None),
        window=window,
        _navigation_chunk_service=nav,
        narration_service=svc,
        bookmark_service=bookmark_service,
        _selected_voice=lambda: voice,
    )

