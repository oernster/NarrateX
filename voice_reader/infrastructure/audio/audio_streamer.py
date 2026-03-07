"""Audio streaming / playback implementation.

Design:

- A producer thread reads WAVs and pushes numpy arrays into a queue.
- A player thread consumes arrays and plays them sequentially.

This keeps TTS generation separate from playback and is unit-testable by
substituting the AudioStreamer interface.
"""

from __future__ import annotations

import queue
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def _trim_silence(
    data,
    *,
    sample_rate: int,
    threshold: float,
    pad_ms: int,
    trim_leading: bool,
    trim_trailing: bool,
):
    """Trim leading/trailing near-silence from an audio array.

    This reduces perceived gaps between chunk WAVs and removes the common
    "fade out / fade in" sensation that is actually leading/trailing silence.
    """

    try:
        import numpy as np

        if not isinstance(data, np.ndarray):
            return data
        if data.size == 0:
            return data

        # Reduce to mono for detection.
        if data.ndim == 2:
            mono = np.mean(data.astype(np.float32), axis=1)
        else:
            mono = data.astype(np.float32)

        abs_m = np.abs(mono)
        idx = np.where(abs_m > float(threshold))[0]
        if idx.size == 0:
            # All silence (or threshold too high) — keep unchanged.
            return data

        pad = int(max(0, sample_rate) * (pad_ms / 1000.0))
        start = 0
        end = int(mono.shape[0])
        if trim_leading:
            start = max(int(idx[0]) - pad, 0)
        if trim_trailing:
            end = min(int(idx[-1]) + pad, int(mono.shape[0]))
        if end <= start:
            return data
        return data[start:end]
    except Exception:
        return data


@dataclass
class SoundDeviceAudioStreamer:
    target_buffer_seconds: float = 15.0
    # Trim settings: keep conservative defaults and tune via code if needed.
    # Lower threshold trims less (more natural micro-pauses), higher trims more.
    trim_threshold: float = 0.0015
    trim_pad_ms: int = 30
    # We prefer a short *silence before* each chunk over any perceived "fade in".
    # If the audio device ramps up, it will ramp during silence, not speech.
    pre_chunk_silence_min_ms: int = 50
    pre_chunk_silence_max_ms: int = 250

    def __post_init__(self) -> None:
        import logging

        self._log = logging.getLogger(self.__class__.__name__)
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.clear()
        self._audio_q: "queue.Queue[tuple[int, object, int]]" = queue.Queue(maxsize=32)
        self._threads: list[threading.Thread] = []
        self._sd_lock = threading.Lock()

        # Best-effort persistent output stream to avoid device start/stop ramping
        # (often perceived as fade-out/fade-in between chunks).
        self._out_stream = None
        self._out_stream_sr: int | None = None
        self._out_stream_ch: int | None = None

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
                # Prefer aborting an OutputStream if we're using one.
                if self._out_stream is not None:
                    try:
                        if hasattr(self._out_stream, "abort"):
                            self._out_stream.abort()
                        elif hasattr(self._out_stream, "stop"):
                            self._out_stream.stop()
                    except Exception:
                        pass
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

        trim_threshold = float(self.trim_threshold)
        trim_pad_ms = int(self.trim_pad_ms)

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

            data = _trim_silence(
                data,
                sample_rate=int(sr),
                threshold=trim_threshold,
                pad_ms=trim_pad_ms,
                # Keep the start of the chunk intact; trimming leading audio can
                # make initial phonemes hard to hear.
                trim_leading=False,
                trim_trailing=True,
            )
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

        def ensure_output_stream(*, sr: int, channels: int):
            """Open (or reuse) a persistent OutputStream.

            Keeping the device open across chunks avoids PortAudio output ramping
            that users perceive as fade-in/fade-out between sentence groups.
            """

            if not hasattr(sd, "OutputStream"):
                return

            if (
                self._out_stream is not None
                and self._out_stream_sr == int(sr)
                and self._out_stream_ch == int(channels)
            ):
                return

            with self._sd_lock:
                # Close any previous stream.
                if self._out_stream is not None:
                    try:
                        self._out_stream.stop()
                    except Exception:
                        pass
                    try:
                        self._out_stream.close()
                    except Exception:
                        pass
                    self._out_stream = None
                    self._out_stream_sr = None
                    self._out_stream_ch = None

                # Select output device if available.
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
                    self._out_stream = sd.OutputStream(
                        samplerate=int(sr),
                        channels=int(channels),
                        dtype="float32",
                        device=out_dev,
                    )
                    self._out_stream.start()
                    self._out_stream_sr = int(sr)
                    self._out_stream_ch = int(channels)
                    self._log.info(
                        "OutputStream opened sr=%s ch=%s dev=%s",
                        self._out_stream_sr,
                        self._out_stream_ch,
                        out_dev,
                    )
                except Exception:
                    self._log.exception("Failed to open OutputStream; falling back")
                    self._out_stream = None
                    self._out_stream_sr = None
                    self._out_stream_ch = None
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

                # Preferred path: persistent OutputStream.
                try:
                    import numpy as np

                    arr = np.asarray(data, dtype=np.float32)
                    if arr.ndim == 1:
                        arr = arr.reshape(-1, 1)
                    channels = int(arr.shape[1])
                    ensure_output_stream(sr=int(sr), channels=channels)
                    if self._out_stream is not None:
                        # Insert a short silence BEFORE speech. This provides
                        # natural cadence and prevents missing word beginnings
                        # if the device applies a ramp on first non-silent audio.
                        try:
                            min_ms = int(self.pre_chunk_silence_min_ms)
                            max_ms = int(self.pre_chunk_silence_max_ms)
                            if max_ms < min_ms:
                                max_ms = min_ms
                            gap_ms = random.randint(min_ms, max_ms)
                        except Exception:
                            gap_ms = 120

                        if gap_ms > 0:
                            gap_frames = int((gap_ms / 1000.0) * int(sr))
                            if gap_frames > 0:
                                gap = np.zeros((gap_frames, channels), dtype=np.float32)
                                with self._sd_lock:
                                    self._out_stream.write(gap)

                        block = 2048
                        total = int(arr.shape[0])
                        pos = 0
                        while pos < total:
                            if self._stop.is_set() or self._pause.is_set():
                                return False
                            end = min(pos + block, total)
                            with self._sd_lock:
                                self._out_stream.write(arr[pos:end])
                            pos = end
                        return True
                except Exception:
                    # Fall back to sd.play below.
                    pass

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

        # Best-effort close stream.
        try:
            with self._sd_lock:
                if self._out_stream is not None:
                    try:
                        self._out_stream.stop()
                    except Exception:
                        pass
                    try:
                        self._out_stream.close()
                    except Exception:
                        pass
                    self._out_stream = None
                    self._out_stream_sr = None
                    self._out_stream_ch = None
        except Exception:
            pass
