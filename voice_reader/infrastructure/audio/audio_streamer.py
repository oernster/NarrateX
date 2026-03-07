"""Audio streaming / playback implementation.

Design:

- A producer thread reads WAVs and pushes numpy arrays into a queue.
- A player thread consumes arrays and plays them sequentially.

This keeps TTS generation separate from playback and is unit-testable by
substituting the AudioStreamer interface.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class SoundDeviceAudioStreamer:
    target_buffer_seconds: float = 15.0

    def __post_init__(self) -> None:
        import logging

        self._log = logging.getLogger(self.__class__.__name__)
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.clear()
        self._audio_q: "queue.Queue[tuple[int, object, int]]" = queue.Queue(maxsize=32)
        self._threads: list[threading.Thread] = []
        self._sd_lock = threading.Lock()

    def start(
        self,
        *,
        chunk_audio_paths: Iterable[Path],
        on_chunk_start=None,
        on_chunk_end=None,
    ) -> None:
        # Stop any previous playback, but preserve pause state: if the user hit
        # Pause while we were still synthesizing/caching, we must not clear it
        # here or audio would start anyway.
        self.stop(clear_pause=False)
        self._stop.clear()

        self._log.info("AudioStreamer starting")
        try:
            self._log.info("AudioStreamer pause=%s", self._pause.is_set())
        except Exception:
            pass

        prod = threading.Thread(
            target=self._producer,
            args=(chunk_audio_paths,),
            name="audio-producer",
            daemon=True,
        )
        play = threading.Thread(
            target=self._player,
            args=(on_chunk_start, on_chunk_end),
            name="audio-player",
            daemon=True,
        )
        self._threads = [prod, play]
        for t in self._threads:
            t.start()
        for t in self._threads:
            t.join()

        self._log.info("AudioStreamer finished")

    def pause(self) -> None:
        self._pause.set()
        self._log.info("AudioStreamer paused")
        self._stop_playback_device()

    def resume(self) -> None:
        self._pause.clear()
        self._log.info("AudioStreamer resumed")

    def stop(self, *, clear_pause: bool = True) -> None:
        self._stop.set()
        if clear_pause:
            self._pause.clear()
        self._log.info("AudioStreamer stop requested")
        self._stop_playback_device()
        while not self._audio_q.empty():
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                break

    def _stop_playback_device(self) -> None:
        """Best-effort: interrupt sounddevice playback immediately."""

        try:
            import sounddevice as sd

            with self._sd_lock:
                if hasattr(sd, "stop"):
                    sd.stop()
        except Exception:
            # If sounddevice isn't importable in tests or hasn't been loaded,
            # we still want pause/stop to behave consistently via events.
            return

    def _producer(self, paths: Iterable[Path]) -> None:
        # Read files and push audio arrays to queue.
        import numpy as np
        import soundfile as sf

        # NOTE:
        # We intentionally rely on the queue's maxsize for backpressure.
        # Maintaining an accurate "seconds buffered" counter would require
        # cross-thread coordination to decrement as playback consumes.
        # A bounded queue provides a robust, deadlock-free buffer.
        self._log.info("Producer thread started")

        # IMPORTANT DEBUGGING NOTE:
        # The iterator `paths` may block while it synthesizes the *next* chunk.
        # We therefore log BEFORE calling `next(it)` so it's obvious whether the
        # stall is in TTS (waiting for a path) vs reading audio (sf.read).
        it = iter(paths)
        idx = 0
        while True:
            if self._stop.is_set():
                self._log.info("Producer stopping (stop event set)")
                return

            self._log.info("Producer waiting for next path idx=%s", idx)
            try:
                path = next(it)
            except StopIteration:
                break

            self._log.info("Producer got path idx=%s path=%s", idx, path.as_posix())
            data, sr = sf.read(str(path), dtype="float32", always_2d=False)
            self._log.info(
                "Producer read idx=%s sr=%s path=%s", idx, sr, path.as_posix()
            )
            if isinstance(data, np.ndarray) and data.ndim == 1:
                frames = data.shape[0]
            else:
                frames = len(data)
            del frames
            self._audio_q.put((idx, data, sr))
            self._log.info("Producer enqueued idx=%s", idx)

            idx += 1

        self._log.info("Producer exhausted paths")

    def _player(self, on_start, on_end) -> None:
        import sounddevice as sd

        self._log.info("Player thread started")
        played_seconds = 0.0
        while not self._stop.is_set():
            try:
                idx, data, sr = self._audio_q.get(timeout=0.1)
            except queue.Empty:
                # Producer may still be working.
                if self._threads and not self._threads[0].is_alive():
                    self._log.info("Player exiting: producer not alive and queue empty")
                    return
                continue

            if on_start is not None:
                try:
                    on_start(idx)
                except Exception:
                    self._log.exception("on_chunk_start failed")

            while self._pause.is_set() and not self._stop.is_set():
                threading.Event().wait(0.05)

            if self._stop.is_set():
                return

            # Start playback.
            # Use an interruptible loop when possible so pause/stop takes effect
            # mid-chunk.
            def play_interruptible() -> bool:
                """Return True if chunk finished normally, False if interrupted."""

                # Some Windows setups (and some host APIs) fail to query the
                # default output device using device=-1. Prefer an explicit
                # output device index when available.
                out_dev = None
                try:
                    default_dev = getattr(sd.default, "device", None)
                    if isinstance(default_dev, (list, tuple)) and len(default_dev) >= 2:
                        out_dev = default_dev[1]
                    if isinstance(out_dev, int) and out_dev < 0:
                        out_dev = None
                except Exception:
                    out_dev = None

                try:
                    with self._sd_lock:
                        try:
                            sd.play(data, sr, blocking=False, device=out_dev)
                        except TypeError:
                            # Older sounddevice versions may not accept device=.
                            sd.play(data, sr, blocking=False)
                except Exception:
                    # If the audio backend can't open a default device on this
                    # machine, fall back to blocking playback. This sacrifices
                    # mid-chunk interruption but keeps the app functional.
                    self._log.exception("sd.play(non-blocking) failed; falling back")
                    try:
                        with self._sd_lock:
                            try:
                                sd.play(data, sr, blocking=True, device=out_dev)
                            except TypeError:
                                sd.play(data, sr, blocking=True)
                        return True
                    except Exception:
                        self._log.exception("sd.play(blocking) failed")
                        return False

                # If sounddevice doesn't expose get_stream (e.g., stubbed in
                # unit tests), fall back to blocking behavior.
                if not hasattr(sd, "get_stream"):
                    with self._sd_lock:
                        sd.play(data, sr, blocking=True)
                    return True

                while True:
                    if self._stop.is_set():
                        self._stop_playback_device()
                        return False
                    if self._pause.is_set():
                        self._stop_playback_device()
                        return False

                    try:
                        stream = sd.get_stream()
                        active = bool(getattr(stream, "active", False))
                    except Exception:
                        # If we can't introspect stream state, just assume the
                        # chunk completes.
                        return True

                    if not active:
                        return True

                    # Prefer sd.sleep (avoids busy-wait) but fall back to time.
                    if hasattr(sd, "sleep"):
                        sd.sleep(20)
                    else:
                        time.sleep(0.02)

            while True:
                self._log.info("Player starting idx=%s sr=%s", idx, sr)
                finished = play_interruptible()
                if self._stop.is_set():
                    return
                if finished:
                    break

                # Interrupted by pause: wait and replay current chunk from the
                # beginning on resume (user-requested semantics).
                while self._pause.is_set() and not self._stop.is_set():
                    threading.Event().wait(0.05)
                if self._stop.is_set():
                    return

            # Best-effort: don't assume ndarray typing here.
            played_seconds += 0.0

            if on_end is not None:
                try:
                    on_end(idx)
                except Exception:
                    self._log.exception("on_chunk_end failed")

        self._log.info("Player exiting: stop set")
