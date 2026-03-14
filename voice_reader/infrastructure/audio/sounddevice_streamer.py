"""Audio streaming / playback implementation.

Design:
- A producer thread reads WAVs and pushes arrays into a queue.
- A player thread consumes arrays and plays them sequentially.

Playback-rate adjustment is applied here (playback concern only).
"""

from __future__ import annotations

import queue
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.infrastructure.audio._silence_trimmer import trim_silence
from voice_reader.infrastructure.audio._sounddevice_helpers import safe_output_device
from voice_reader.infrastructure.audio._sounddevice_helpers import sd_play
from voice_reader.infrastructure.audio.resampler import AudioResampler


@dataclass
class SoundDeviceAudioStreamer:
    target_buffer_seconds: float = 15.0
    # Trim settings: keep conservative defaults and tune via code if needed.
    trim_threshold: float = 0.0015
    trim_pad_ms: int = 30
    pre_chunk_silence_min_ms: int = 50
    pre_chunk_silence_max_ms: int = 250

    playback_rate: PlaybackRate = PlaybackRate.default()
    resampler: AudioResampler = AudioResampler()

    def __post_init__(self) -> None:
        import logging

        self._log = logging.getLogger(self.__class__.__name__)
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.clear()
        self._audio_q: "queue.Queue[tuple[int, object, int]]" = queue.Queue(maxsize=32)
        self._threads: list[threading.Thread] = []
        self._sd_lock = threading.Lock()

        self._out_stream = None
        self._out_stream_sr: int | None = None
        self._out_stream_ch: int | None = None

    def set_playback_rate(self, rate: PlaybackRate) -> None:
        self.playback_rate = rate

    def _is_tearing_down(self) -> bool:
        return bool(self._stop.is_set() or self._pause.is_set())

    def start(
        self,
        *,
        chunk_audio_paths: Iterable[Path],
        on_chunk_start=None,
        on_chunk_end=None,
        on_playback_progress=None,
    ) -> None:
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
        try:
            import sounddevice as sd

            with self._sd_lock:
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
            return

    def _producer(self, paths: Iterable[Path]) -> None:
        import soundfile as sf

        trim_threshold = float(self.trim_threshold)
        trim_pad_ms = int(self.trim_pad_ms)

        self._log.debug("Producer thread started")

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

            data = trim_silence(
                data,
                sample_rate=int(sr),
                threshold=trim_threshold,
                pad_ms=trim_pad_ms,
                trim_leading=False,
                trim_trailing=True,
            )
            self._audio_q.put((idx, data, sr))
            idx += 1

        self._log.debug("Producer exhausted paths")

    def _player(self, on_start, on_end, on_progress) -> None:
        import sounddevice as sd

        self._log.debug("Player thread started")

        def ensure_output_stream(*, sr: int, channels: int):
            if not hasattr(sd, "OutputStream"):
                return

            if (
                self._out_stream is not None
                and self._out_stream_sr == int(sr)
                and self._out_stream_ch == int(channels)
            ):
                return

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

                out_dev = safe_output_device(sd)

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
                except Exception:
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
                if self._threads and not self._threads[0].is_alive():
                    self._log.debug(
                        "Player exiting: producer not alive and queue empty"
                    )
                    return
                continue

            if on_start is not None:
                try:
                    on_start(idx)
                except Exception:
                    self._log.exception("on_chunk_start failed")

            if on_progress is not None:
                try:
                    on_progress(idx, 0)
                except Exception:
                    self._log.exception("on_playback_progress failed")

            while self._pause.is_set() and not self._stop.is_set():
                threading.Event().wait(0.05)

            if self._stop.is_set():
                return

            replaying = False

            def play_interruptible() -> bool:
                # Snapshot rate per *play attempt* so changing speed while paused
                # affects the replay of the current chunk (but never mid-chunk).
                chunk_rate = float(self.playback_rate.multiplier)
                try:
                    import numpy as np

                    arr = np.asarray(data, dtype=np.float32)
                    arr = self.resampler.resample_for_rate(arr, chunk_rate)
                    if arr.ndim == 1:
                        arr = arr.reshape(-1, 1)
                    channels = int(arr.shape[1])
                    ensure_output_stream(sr=int(sr), channels=channels)
                    if self._out_stream is not None:
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

                            if (
                                on_progress is not None
                                and (pos - last_progress_frames)
                                >= progress_every_frames
                            ):
                                last_progress_frames = pos
                                try:
                                    played_ms_transformed = int(
                                        (pos / float(sr)) * 1000.0
                                    )
                                    played_ms_original = int(
                                        played_ms_transformed * float(chunk_rate)
                                    )
                                    on_progress(idx, played_ms_original)
                                except Exception:
                                    self._log.exception("on_playback_progress failed")
                        return True
                except Exception:
                    pass

                # Fallback path (sd.play). Best-effort apply playback rate here
                # too so speed control works even without OutputStream.
                play_data = data
                try:
                    import numpy as np

                    play_data = np.asarray(data, dtype=np.float32)
                    play_data = self.resampler.resample_for_rate(play_data, chunk_rate)
                except Exception:
                    play_data = data

                out_dev = safe_output_device(sd)

                try:
                    with self._sd_lock:
                        sd_play(
                            sd,
                            data=play_data,
                            sr=int(sr),
                            blocking=False,
                            device=out_dev,
                        )
                except Exception:
                    if self._is_tearing_down():
                        return False
                    self._log.warning("sd.play(non-blocking) failed; falling back")
                    self._log.debug("sd.play(non-blocking) failed", exc_info=True)
                    try:
                        with self._sd_lock:
                            sd_play(
                                sd,
                                data=play_data,
                                sr=int(sr),
                                blocking=True,
                                device=out_dev,
                            )
                        return True
                    except Exception:
                        if not self._is_tearing_down():
                            self._log.error("sd.play(blocking) failed")
                            self._log.debug("sd.play(blocking) failed", exc_info=True)
                        self._stop.set()
                        return False

                if not hasattr(sd, "get_stream"):
                    with self._sd_lock:
                        sd.play(play_data, sr, blocking=True)
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
                        return True

                    if not active:
                        return True

                    if on_progress is not None:
                        try:
                            now = time.perf_counter()
                            t0 = getattr(play_interruptible, "_t0", None)
                            if t0 is None:
                                t0 = now
                                setattr(play_interruptible, "_t0", t0)

                            played_ms_transformed = int((now - float(t0)) * 1000.0)
                            played_ms_original = int(
                                played_ms_transformed * float(chunk_rate)
                            )
                            on_progress(idx, played_ms_original)
                        except Exception:
                            self._log.exception("on_playback_progress failed")

                    if hasattr(sd, "sleep"):
                        sd.sleep(20)
                    else:
                        time.sleep(0.02)

            while True:
                # When replaying a chunk after pause, reset the fallback
                # wall-clock progress timer.
                if hasattr(play_interruptible, "_t0"):
                    try:
                        delattr(play_interruptible, "_t0")
                    except Exception:
                        pass

                if replaying and on_progress is not None:
                    try:
                        on_progress(idx, 0)
                    except Exception:
                        self._log.exception("on_playback_progress failed")

                finished = play_interruptible()
                if self._stop.is_set():
                    return
                if finished:
                    break

                while self._pause.is_set() and not self._stop.is_set():
                    threading.Event().wait(0.05)
                if self._stop.is_set():
                    return

                replaying = True

            if on_end is not None:
                try:
                    on_end(idx)
                except Exception:
                    self._log.exception("on_chunk_end failed")

        self._log.debug("Player exiting: stop set")

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
