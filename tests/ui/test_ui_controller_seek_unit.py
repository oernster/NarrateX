from __future__ import annotations

from types import SimpleNamespace

from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui._ui_controller_seek import seek_to_char_offset

from tests.ui._seek_testkit import NavFake, NarrationSvcFake, make_controller


def _controller(*, text: str = "x", nav=None, svc=None, voice=None):
    return make_controller(text=text, nav=nav, svc=svc, voice=voice)


def test_seek_invalid_offset_returns_early() -> None:
    c = _controller(text="hello")
    seek_to_char_offset(c, "bad")  # type: ignore[arg-type]
    assert c.narration_service.prepare_calls == []


def test_seek_reader_to_plain_text_exception_returns_early() -> None:
    c = _controller(text="hello")
    c.window.reader = SimpleNamespace(toPlainText=lambda: (_ for _ in ()).throw(Exception()))
    seek_to_char_offset(c, 1)
    assert c.narration_service.prepare_calls == []


def test_seek_empty_text_returns_early() -> None:
    c = _controller(text="")
    seek_to_char_offset(c, 0)
    assert c.narration_service.prepare_calls == []


def test_seek_missing_nav_returns_early() -> None:
    c = _controller(text="hello")
    c._navigation_chunk_service = None
    seek_to_char_offset(c, 0)
    assert c.narration_service.prepare_calls == []


def test_seek_nav_exception_returns_early() -> None:
    c = _controller(text="hello", nav=NavFake(chunks=[], exc=RuntimeError("boom")))
    seek_to_char_offset(c, 0)
    assert c.narration_service.prepare_calls == []


def test_seek_no_chunks_returns_early() -> None:
    c = _controller(text="hello", nav=NavFake(chunks=[]))
    seek_to_char_offset(c, 0)
    assert c.narration_service.prepare_calls == []


def test_seek_resolve_mapping_exception_falls_back_to_zero_and_works(monkeypatch) -> None:
    svc = NarrationSvcFake(stop_calls=[], prepare_calls=[])
    delattr(svc, "loaded_book_id_exc")  # keep as simple object

    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(
            chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]
        ),
    )

    # Remove attribute so resolve_playback_index_for_char_offset fails.
    if hasattr(c.narration_service, "sanitized_text_mapper"):
        delattr(c.narration_service, "sanitized_text_mapper")

    seek_to_char_offset(c, 15)
    assert c.narration_service.prepare_calls
    assert c.narration_service.prepare_calls[-1]["start_playback_index"] == 0


def test_seek_candidates_empty_returns_early() -> None:
    class _Mapper:
        def sanitize_with_mapping(self, *, original_text: str):
            del original_text
            return SimpleNamespace(speak_text="")

    svc = NarrationSvcFake(stop_calls=[], prepare_calls=[])
    svc.sanitized_text_mapper = _Mapper()  # type: ignore[attr-defined]

    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(
            chunks=[TextChunk(chunk_id=0, text="---", start_char=10, end_char=20)]
        ),
    )

    seek_to_char_offset(c, 15)
    assert c.narration_service.prepare_calls == []


def test_seek_clamp_sets_status_and_can_ignore_status_failures() -> None:
    svc = NarrationSvcFake(stop_calls=[], prepare_calls=[])
    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(
            chunks=[TextChunk(chunk_id=0, text="A", start_char=25, end_char=50)]
        ),
    )
    # Make setText fail to cover the exception handler.
    c.window.lbl_status = SimpleNamespace(setText=lambda *_: (_ for _ in ()).throw(Exception()))

    seek_to_char_offset(c, 0)
    assert c.narration_service.prepare_calls


def test_seek_selected_voice_exception_is_handled() -> None:
    c = _controller(
        text="x" * 200,
        nav=NavFake(chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]),
    )
    c._selected_voice = lambda: (_ for _ in ()).throw(Exception())
    seek_to_char_offset(c, 15)
    assert c.narration_service.prepare_calls == []


def test_seek_selected_voice_none_returns_early() -> None:
    c = _controller(
        text="x" * 200,
        nav=NavFake(chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]),
    )
    c._selected_voice = lambda: None
    seek_to_char_offset(c, 15)
    assert c.narration_service.prepare_calls == []


def test_seek_stop_type_error_falls_back_to_stop_no_args() -> None:
    calls: list[str] = []

    class _SvcNoKwStop(NarrationSvcFake):
        def stop(self):  # type: ignore[override]
            calls.append("stop")

    svc = _SvcNoKwStop(stop_calls=[], prepare_calls=[])
    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]),
    )
    seek_to_char_offset(c, 15)
    assert "stop" in calls


def test_seek_stop_unexpected_exception_is_ignored() -> None:
    class _SvcStopExplodes(NarrationSvcFake):
        def stop(self, *, persist_resume: bool = True):
            raise RuntimeError("boom")

    svc = _SvcStopExplodes(stop_calls=[], prepare_calls=[])
    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]),
    )
    seek_to_char_offset(c, 15)
    assert c.narration_service.prepare_calls


def test_seek_assignment_of_last_prepared_voice_id_can_fail_and_is_ignored() -> None:
    svc = NarrationSvcFake(stop_calls=[], prepare_calls=[])
    nav = NavFake(chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)])

    from types import SimpleNamespace

    class _Controller(SimpleNamespace):
        def __setattr__(self, name, value):
            if name == "_last_prepared_voice_id":
                raise RuntimeError("no")
            return super().__setattr__(name, value)

    base = _controller(text="x" * 200, svc=svc, nav=nav)
    c = _Controller(**base.__dict__)
    seek_to_char_offset(c, 15)
    assert c.narration_service.prepare_calls


def test_seek_prepare_failure_returns_early() -> None:
    class _SvcBadPrepare(NarrationSvcFake):
        def prepare(self, *, voice, start_playback_index: int, persist_resume: bool = True):
            raise RuntimeError("boom")

    svc = _SvcBadPrepare(stop_calls=[], prepare_calls=[])
    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]),
    )
    seek_to_char_offset(c, 15)
    assert c.narration_service.start_calls == 0


def test_seek_highlight_failure_is_ignored() -> None:
    svc = NarrationSvcFake(stop_calls=[], prepare_calls=[])
    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]),
    )
    c.window.highlight_range = lambda *_: (_ for _ in ()).throw(Exception())
    seek_to_char_offset(c, 15)
    assert c.narration_service.start_calls == 1


def test_seek_start_failure_returns_early() -> None:
    class _SvcBadStart(NarrationSvcFake):
        def start(self):
            raise RuntimeError("boom")

    svc = _SvcBadStart(stop_calls=[], prepare_calls=[])
    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]),
    )
    seek_to_char_offset(c, 15)
    assert c.narration_service.start_calls == 0


def test_seek_loaded_book_id_exception_skips_persistence() -> None:
    svc = NarrationSvcFake(stop_calls=[], prepare_calls=[], loaded_book_id_exc=RuntimeError("x"))
    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]),
    )
    seek_to_char_offset(c, 15)
    assert c.narration_service.start_calls == 1


def test_seek_resume_persist_exception_is_caught() -> None:
    svc = NarrationSvcFake(stop_calls=[], prepare_calls=[])
    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]),
    )
    c.bookmark_service = SimpleNamespace(
        save_resume_position=lambda **_: (_ for _ in ()).throw(Exception())
    )
    seek_to_char_offset(c, 15)
    assert c.narration_service.start_calls == 1


def test_seek_first_start_exception_path_is_covered(monkeypatch) -> None:
    class _BrokenChunk:
        text = "A"
        end_char = 10

        @property
        def start_char(self):
            raise RuntimeError("nope")

    broken = _BrokenChunk()
    good = TextChunk(chunk_id=1, text="B", start_char=50, end_char=60)

    svc = NarrationSvcFake(stop_calls=[], prepare_calls=[])
    c = _controller(text="x" * 200, svc=svc, nav=NavFake(chunks=[broken, good]))

    monkeypatch.setattr(
        "voice_reader.ui._ui_controller_seek.resolve_playback_index_for_char_offset",
        lambda *_args, **_kwargs: 1,
    )
    seek_to_char_offset(c, 55)
    assert c.narration_service.prepare_calls


def test_seek_candidate_filtering_exception_falls_back_to_all_chunks(monkeypatch) -> None:
    class _MapperExplodes:
        def sanitize_with_mapping(self, *, original_text: str):
            del original_text
            raise RuntimeError("boom")

    svc = NarrationSvcFake(stop_calls=[], prepare_calls=[])
    svc.sanitized_text_mapper = _MapperExplodes()  # type: ignore[attr-defined]

    c = _controller(
        text="x" * 200,
        svc=svc,
        nav=NavFake(
            chunks=[
                TextChunk(chunk_id=0, text="A", start_char=10, end_char=20),
                TextChunk(chunk_id=1, text="B", start_char=20, end_char=30),
            ]
        ),
    )

    monkeypatch.setattr(
        "voice_reader.ui._ui_controller_seek.resolve_playback_index_for_char_offset",
        lambda *_args, **_kwargs: 1,
    )

    seek_to_char_offset(c, 25)
    assert c.narration_service.prepare_calls
    assert c.narration_service.prepare_calls[-1]["start_playback_index"] == 1


def test_seek_stop_kw_type_error_then_stop_raises_is_ignored() -> None:
    calls: list[str] = []

    class _SvcStopKwTypeError:
        def stop(self):
            calls.append("stop")
            raise RuntimeError("boom")

        def prepare(self, *, voice, start_playback_index: int, persist_resume: bool = True):
            calls.append(f"prepare:{int(start_playback_index)}")

        def start(self):
            calls.append("start")

        def loaded_book_id(self):
            return "b1"

    svc = _SvcStopKwTypeError()

    window = SimpleNamespace(
        reader=SimpleNamespace(toPlainText=lambda: "x" * 200),
        highlight_range=lambda *_: None,
        lbl_status=SimpleNamespace(setText=lambda *_: None, text=lambda: ""),
    )
    c = SimpleNamespace(
        _log=SimpleNamespace(exception=lambda *_: None),
        window=window,
        _navigation_chunk_service=NavFake(
            chunks=[TextChunk(chunk_id=0, text="A", start_char=10, end_char=20)]
        ),
        narration_service=svc,
        bookmark_service=SimpleNamespace(save_resume_position=lambda **_: None),
        _selected_voice=lambda: VoiceProfile(name="v", reference_audio_paths=[]),
    )

    seek_to_char_offset(c, 15)
    # stop was attempted but its failure must not prevent restarting.
    assert "prepare:0" in calls
    assert "start" in calls

