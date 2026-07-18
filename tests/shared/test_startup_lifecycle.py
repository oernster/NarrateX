"""Startup and shutdown are best-effort, and have to stay that way.

A failure on the way out must not skip the steps after it, or a crash in
indexing would cost the reader their place in the book. A failure warming the
speech model must not surface at all, since the warm-up is an optimisation.
"""

from __future__ import annotations

from voice_reader.shared.startup_lifecycle import (
    shutdown,
    start_tts_warmup,
    warm_up_tts,
)


class _Log:
    def __init__(self) -> None:
        self.exceptions: list[str] = []
        self.debugs: list[str] = []

    def exception(self, message: str, *args: object) -> None:
        del args
        self.exceptions.append(message)

    def debug(self, message: str, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.debugs.append(message)


class _Controller:
    def __init__(self, *, boom: bool = False) -> None:
        self.boom = boom
        self.exited = False

    def on_app_exit(self) -> None:
        if self.boom:
            raise RuntimeError("indexing failed")
        self.exited = True


class _Narration:
    def __init__(self, *, exit_boom: bool = False, stop_boom: bool = False) -> None:
        self.exit_boom = exit_boom
        self.stop_boom = stop_boom
        self.exited = False
        self.stopped = False
        self.warmed: list[object] = []

    def on_app_exit(self) -> None:
        if self.exit_boom:
            raise RuntimeError("resume save failed")
        self.exited = True

    def stop(self) -> None:
        if self.stop_boom:
            raise RuntimeError("stop failed")
        self.stopped = True

    def startup_warmup(self, voice: object) -> None:
        self.warmed.append(voice)


class _Voices:
    def __init__(self, profiles: list[object] | None = None, *, boom: bool = False):
        self.profiles = profiles or []
        self.boom = boom

    def list_profiles(self) -> list[object]:
        if self.boom:
            raise RuntimeError("no voices")
        return self.profiles


class TestShutdown:
    def test_the_ordinary_path_runs_every_step(self) -> None:
        controller, narration, log = _Controller(), _Narration(), _Log()

        shutdown(controller, narration, log=log)

        assert controller.exited
        assert narration.exited
        assert narration.stopped
        assert log.exceptions == []

    def test_a_failure_in_one_step_does_not_skip_the_rest(self) -> None:
        # Losing the resume position because indexing raised first would be a
        # poor trade, so each step is guarded on its own.
        controller, narration, log = _Controller(boom=True), _Narration(), _Log()

        shutdown(controller, narration, log=log)

        assert narration.exited
        assert narration.stopped
        assert len(log.exceptions) == 1

    def test_a_failure_saving_the_position_still_stops_narration(self) -> None:
        controller = _Controller()
        narration = _Narration(exit_boom=True)
        log = _Log()

        shutdown(controller, narration, log=log)

        assert narration.stopped
        assert len(log.exceptions) == 1

    def test_a_failure_stopping_narration_is_logged_not_raised(self) -> None:
        controller = _Controller()
        narration = _Narration(stop_boom=True)
        log = _Log()

        shutdown(controller, narration, log=log)

        assert len(log.exceptions) == 1

    def test_every_step_failing_is_still_survivable(self) -> None:
        controller = _Controller(boom=True)
        narration = _Narration(exit_boom=True, stop_boom=True)
        log = _Log()

        shutdown(controller, narration, log=log)

        assert len(log.exceptions) == 3


class TestWarmUp:
    def test_the_first_voice_is_the_one_warmed(self) -> None:
        narration, log = _Narration(), _Log()

        warm_up_tts(_Voices(["first", "second"]), narration, log=log)

        assert narration.warmed == ["first"]

    def test_no_voices_means_nothing_to_warm(self) -> None:
        narration, log = _Narration(), _Log()

        warm_up_tts(_Voices([]), narration, log=log)

        assert narration.warmed == []
        assert log.debugs == []

    def test_a_failure_never_reaches_the_user(self) -> None:
        # The app works without the warm-up, so this is a debug note at most.
        narration, log = _Narration(), _Log()

        warm_up_tts(_Voices(boom=True), narration, log=log)

        assert narration.warmed == []
        assert log.debugs == ["Startup TTS warmup failed"]


class TestStartingTheWarmUpThread:
    def test_the_thread_is_a_named_daemon_and_is_started(self) -> None:
        # Startup must not be held up by the warm-up, nor kept alive by it.
        started: list[str] = []

        class _Thread:
            def __init__(self, *, target, name, daemon) -> None:  # noqa: ANN001
                self.target = target
                self.name = name
                self.daemon = daemon

            def start(self) -> None:
                started.append(self.name)
                self.target()

        narration, log = _Narration(), _Log()

        thread = start_tts_warmup(_Voices(["first"]), narration, log=log, spawn=_Thread)

        assert started == ["tts-startup-warmup"]
        assert thread.daemon is True
        assert narration.warmed == ["first"]
