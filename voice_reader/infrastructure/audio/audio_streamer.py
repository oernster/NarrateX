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

    def _is_tearing_down(self) -> bool:
        """Return True when playback is being stopped/paused and errors are expected.

        During stop/pause/app shutdown, PortAudio calls can legitimately fail
        (device disappeared, default device is invalid, etc.). We avoid logging
        noisy tracebacks in those situations.
        """

        return bool(self._stop.is_set() or self._pause.is_set())

    def start(
        self,
        *,
        chunk_audio_paths: Iterable[Path],
        on_chunk_start=None,
        on_chunk_end=None,
        on_playback_progress=None,
    ) -> None:
        # Stop any previous playback, but preserve pause state: if the user hit
        # Pause while we were still synthesizing/caching, we must not clear it
        # here or audio would start anyway.
        self.stop(clear_pause=False)
        self._stop.clear()

        self._log.debug("AudioStreamer starting")
        try:
            self._log.debug("AudioStreamer pause=%s", self._pause.is_set())
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
            args=(on_chunk_start, on_chunk_end, on_playback_progress),
            name="audio-player",
            daemon=True,
        )
        self._threads = [prod, play]
        for t in self._threads:
            t.start()
        for t in self._threads:
            t.join()

        self._log.debug("AudioStreamer finished")

    def pause(self) -> None:
        self._pause.set()
        self._log.debug("AudioStreamer paused")
        self._stop_playback_device()

    def resume(self) -> None:
        self._pause.clear()
        self._log.debug("AudioStreamer resumed")

    def stop(self, *, clear_pause: bool = True) -> None:
        self._stop.set()
        if clear_pause:
            self._pause.clear()
        self._log.debug("AudioStreamer stop requested")
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

    @staticmethod
    def _safe_output_device(sd) -> int | None:
        """Return a safe PortAudio output device index or None.

        On some Windows machines `sd.default.device` resolves to -1 (or a scalar
        wrapping -1). Passing `device=-1` causes PortAudioError.
        """

        out_dev = None
        try:
            default_dev = getattr(sd.default, "device", None)
            if isinstance(default_dev, (list, tuple)) and len(default_dev) >= 2:
                out_dev = default_dev[1]
            else:
                out_dev = default_dev
        except Exception:
            out_dev = None

        try:
            if out_dev is None:
                return None
            out_dev_int = int(out_dev)
        except Exception:
            return None

        if out_dev_int < 0:
            return None

        # Validate when possible.
        try:
            if hasattr(sd, "query_devices"):
                sd.query_devices(out_dev_int)
        except Exception:
            return None

        return out_dev_int

    @staticmethod
    def _sd_play(sd, *, data, sr: int, blocking: bool, device: int | None) -> None:
        """Play audio with sounddevice, retrying without device on device errors."""

        if device is None:
            sd.play(data, sr, blocking=blocking)
            return

        try:
            sd.play(data, sr, blocking=blocking, device=device)
        except TypeError:
            # Older sounddevice versions may not accept device=.
            sd.play(data, sr, blocking=blocking)
        except Exception as exc:
            msg = str(exc).lower()
            # Fallback: if explicit device selection is broken, retry without it.
            if "querying device" in msg or "device" in msg:
                sd.play(data, sr, blocking=blocking)
            else:
                raise

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
        self._log.debug("Producer thread started")

        # IMPORTANT DEBUGGING NOTE:
        # The iterator `paths` may block while it synthesizes the *next* chunk.
        # We therefore log BEFORE calling `next(it)` so it's obvious whether the
        # stall is in TTS (waiting for a path) vs reading audio (sf.read).
        it = iter(paths)
        idx = 0
        while True:
            if self._stop.is_set():
                self._log.debug("Producer stopping (stop event set)")
                return

            try:
                path = next(it)
            except StopIteration:
                break

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
            if isinstance(data, np.ndarray) and data.ndim == 1:
                frames = data.shape[0]
            else:
                frames = len(data)
            del frames
            self._audio_q.put((idx, data, sr))

            idx += 1

        self._log.debug("Producer exhausted paths")

    def _player(self, on_start, on_end, on_progress) -> None:
        import sounddevice as sd

        self._log.debug("Player thread started")
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

                out_dev = self._safe_output_device(sd)

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
                    self._log.debug(
                        "OutputStream opened sr=%s ch=%s dev=%s",
                        self._out_stream_sr,
                        self._out_stream_ch,
                        out_dev,
                    )
                except Exception:
                    # On shutdown/stop, this is expected on some systems.
                    if not self._is_tearing_down():
                        self._log.warning("Failed to open OutputStream; falling back")
                        self._log.debug("OutputStream open failed", exc_info=True)
                    self._out_stream = None
                    self._out_stream_sr = None
                    self._out_stream_ch = None
        while not self._stop.is_set():
            try:
                idx, data, sr = self._audio_q.get(timeout=0.1)
            except queue.Empty:
                # Producer may still be working.
                if self._threads and not self._threads[0].is_alive():
                    self._log.debug("Player exiting: producer not alive and queue empty")
                    return
                continue

            if on_start is not None:
                try:
                    on_start(idx)
                except Exception:
                    self._log.exception("on_chunk_start failed")

            # Best-effort progress callback: emit 0ms at chunk start.
            # IMPORTANT: this excludes any inserted pre-chunk silence; it tracks
            # only WAV playback.
            if on_progress is not None:
                try:
                    on_progress(idx, 0)
                except Exception:
                    self._log.exception("on_playback_progress failed")

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

                        # Emit progress at ~30-50ms cadence. We tie cadence to
                        # the audio write loop so we don't need extra threads.
                        progress_interval_ms = 40
                        progress_every_frames = max(
                            1, int((progress_interval_ms / 1000.0) * int(sr))
                        )

                        block = 2048
                        total = int(arr.shape[0])
                        pos = 0
                        last_progress_frames = 0
                        while pos < total:
                            if self._stop.is_set() or self._pause.is_set():
                                return False
                            end = min(pos + block, total)
                            with self._sd_lock:
                                self._out_stream.write(arr[pos:end])
                            pos = end

                            # Progress callback (exclude inserted silence).
                            if (
                                on_progress is not None
                                and (pos - last_progress_frames) >= progress_every_frames
                            ):
                                last_progress_frames = pos
                                try:
                                    ms = int((pos / float(sr)) * 1000.0)
                                    on_progress(idx, ms)
                                except Exception:
                                    self._log.exception("on_playback_progress failed")
                        return True
                except Exception:
                    # Fall back to sd.play below.
                    pass

                out_dev = self._safe_output_device(sd)

                try:
                    with self._sd_lock:
                        self._sd_play(sd, data=data, sr=int(sr), blocking=False, device=out_dev)
                except Exception:
                    # If the audio backend can't open a default device on this
                    # machine, fall back to blocking playback. This sacrifices
                    # mid-chunk interruption but keeps the app functional.
                    if self._is_tearing_down():
                        return False

                    self._log.warning("sd.play(non-blocking) failed; falling back")
                    self._log.debug("sd.play(non-blocking) failed", exc_info=True)
                    try:
                        with self._sd_lock:
                            self._sd_play(sd, data=data, sr=int(sr), blocking=True, device=out_dev)
                        return True
                    except Exception:
                        if not self._is_tearing_down():
                            self._log.error("sd.play(blocking) failed")
                            self._log.debug("sd.play(blocking) failed", exc_info=True)
                        # Avoid an infinite retry loop if the audio backend is
                        # broken (e.g. invalid default device). End playback.
                        self._stop.set()
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

                    # Progress callback at ~30-50ms cadence using sleep loop.
                    if on_progress is not None:
                        try:
                            # We don't have sample-accurate position here; use
                            # wall-clock since chunk start.
                            # This path is a fallback; prefer OutputStream.
                            now = time.perf_counter()
                            # Lazily initialize per-chunk start time.
                            if not hasattr(play_interruptible, "_t0"):
                                play_interruptible._t0 = now  # type: ignore[attr-defined]
                            ms = int((now - play_interruptible._t0) * 1000.0)  # type: ignore[attr-defined]
                            on_progress(idx, ms)
                        except Exception:
                            self._log.exception("on_playback_progress failed")

                    # Prefer sd.sleep (avoids busy-wait) but fall back to time.
                    if hasattr(sd, "sleep"):
                        sd.sleep(20)
                    else:
                        time.sleep(0.02)

            while True:
                # Avoid per-chunk spam; keep only higher-level thread lifecycle logs.
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

        self._log.debug("Player exiting: stop set")

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
