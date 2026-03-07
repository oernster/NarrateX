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

        paths = list(chunk_audio_paths)

        prod = threading.Thread(
            target=self._producer,
            args=(paths,),
            name="audio-producer",
            daemon=True,
        )
        play = threading.Thread(
            target=self._player,
            args=(paths, on_chunk_start, on_chunk_end),
            name="audio-player",
            daemon=True,
        )
        self._threads = [prod, play]
        for t in self._threads:
            t.start()
        for t in self._threads:
            t.join()

    def pause(self) -> None:
        self._pause.set()
        self._stop_playback_device()

    def resume(self) -> None:
        self._pause.clear()

    def stop(self, *, clear_pause: bool = True) -> None:
        self._stop.set()
        if clear_pause:
            self._pause.clear()
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

    def _producer(self, paths: list[Path]) -> None:
        # Read files and push audio arrays to queue.
        import numpy as np
        import soundfile as sf

        # NOTE:
        # We intentionally rely on the queue's maxsize for backpressure.
        # Maintaining an accurate "seconds buffered" counter would require
        # cross-thread coordination to decrement as playback consumes.
        # A bounded queue provides a robust, deadlock-free buffer.
        for idx, path in enumerate(paths):
            if self._stop.is_set():
                return

            data, sr = sf.read(str(path), dtype="float32", always_2d=False)
            if isinstance(data, np.ndarray) and data.ndim == 1:
                frames = data.shape[0]
            else:
                frames = len(data)
            del frames
            self._audio_q.put((idx, data, sr))

    def _player(self, paths: list[Path], on_start, on_end) -> None:
        import sounddevice as sd

        played_seconds = 0.0
        while not self._stop.is_set():
            try:
                idx, data, sr = self._audio_q.get(timeout=0.1)
            except queue.Empty:
                # Producer may still be working.
                if self._threads and not self._threads[0].is_alive():
                    return
                continue

            if on_start is not None:
                try:
                    on_start(idx)
                except Exception:
                    pass

            while self._pause.is_set() and not self._stop.is_set():
                threading.Event().wait(0.05)

            if self._stop.is_set():
                return

            # Start playback.
            # Use an interruptible loop when possible so pause/stop takes effect
            # mid-chunk.
            def play_interruptible() -> bool:
                """Return True if chunk finished normally, False if interrupted."""

                with self._sd_lock:
                    sd.play(data, sr, blocking=False)

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
                    pass
