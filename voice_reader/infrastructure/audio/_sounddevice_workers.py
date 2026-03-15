"""Sounddevice playback worker loops.

These functions are intentionally extracted to keep the public streamer module
small (≤400 LOC) while preserving the existing behavior.
"""

from __future__ import annotations

import queue
import random
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from voice_reader.infrastructure.audio._silence_trimmer import trim_silence
from voice_reader.infrastructure.audio._sounddevice_helpers import safe_output_device
from voice_reader.infrastructure.audio._sounddevice_helpers import sd_play

if TYPE_CHECKING:
    from voice_reader.infrastructure.audio.sounddevice_streamer import (
        SoundDeviceAudioStreamer,
    )


def producer_loop(streamer: "SoundDeviceAudioStreamer", paths: Iterable[Path]) -> None:
    import soundfile as sf

    trim_threshold = float(streamer.trim_threshold)
    trim_pad_ms = int(streamer.trim_pad_ms)

    streamer._log.debug("Producer thread started")

    it = iter(paths)
    idx = 0
    while True:
        if streamer._stop.is_set():
            streamer._log.debug("Producer stopping (stop event set)")
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
        streamer._audio_q.put((idx, data, sr))
        idx += 1

    streamer._log.debug("Producer exhausted paths")


def player_loop(
    streamer: "SoundDeviceAudioStreamer",
    *,
    on_start,
    on_end,
    on_progress,
) -> None:
    import sounddevice as sd

    streamer._log.debug("Player thread started")

    def ensure_output_stream(*, sr: int, channels: int) -> None:
        if not hasattr(sd, "OutputStream"):
            return

        if (
            streamer._out_stream is not None
            and streamer._out_stream_sr == int(sr)
            and streamer._out_stream_ch == int(channels)
        ):
            return

        with streamer._sd_lock:
            if streamer._out_stream is not None:
                try:
                    streamer._out_stream.stop()
                except Exception:
                    pass
                try:
                    streamer._out_stream.close()
                except Exception:
                    pass
                streamer._out_stream = None
                streamer._out_stream_sr = None
                streamer._out_stream_ch = None

            out_dev = safe_output_device(sd)

            try:
                streamer._out_stream = sd.OutputStream(
                    samplerate=int(sr),
                    channels=int(channels),
                    dtype="float32",
                    device=out_dev,
                )
                streamer._out_stream.start()
                streamer._out_stream_sr = int(sr)
                streamer._out_stream_ch = int(channels)
            except Exception:
                if not streamer._is_tearing_down():
                    streamer._log.warning("Failed to open OutputStream; falling back")
                    streamer._log.debug("OutputStream open failed", exc_info=True)
                streamer._out_stream = None
                streamer._out_stream_sr = None
                streamer._out_stream_ch = None

    while not streamer._stop.is_set():
        try:
            idx, data, sr = streamer._audio_q.get(timeout=0.1)
        except queue.Empty:
            if streamer._threads and not streamer._threads[0].is_alive():
                streamer._log.debug(
                    "Player exiting: producer not alive and queue empty"
                )
                return
            continue

        if on_start is not None:
            try:
                on_start(idx)
            except Exception:
                streamer._log.exception("on_chunk_start failed")

        if on_progress is not None:
            try:
                on_progress(idx, 0)
            except Exception:
                streamer._log.exception("on_playback_progress failed")

        while streamer._pause.is_set() and not streamer._stop.is_set():
            threading.Event().wait(0.05)

        if streamer._stop.is_set():
            return

        replaying = False

        def play_interruptible() -> bool:
            # Snapshot rate per *play attempt* so changing speed while paused
            # affects the replay of the current chunk (but never mid-chunk).
            chunk_rate = float(streamer.playback_rate.multiplier)
            try:
                import numpy as np

                arr = np.asarray(data, dtype=np.float32)
                arr = streamer.resampler.resample_for_rate(arr, chunk_rate)
                if arr.ndim == 1:
                    arr = arr.reshape(-1, 1)
                channels = int(arr.shape[1])
                ensure_output_stream(sr=int(sr), channels=channels)
                if streamer._out_stream is not None:
                    try:
                        min_ms = int(streamer.pre_chunk_silence_min_ms)
                        max_ms = int(streamer.pre_chunk_silence_max_ms)
                        if max_ms < min_ms:
                            max_ms = min_ms
                        gap_ms = random.randint(min_ms, max_ms)
                    except Exception:
                        gap_ms = 120

                    if gap_ms > 0:
                        gap_frames = int((gap_ms / 1000.0) * int(sr))
                        if gap_frames > 0:
                            gap = np.zeros((gap_frames, channels), dtype=np.float32)
                            with streamer._sd_lock:
                                streamer._out_stream.write(gap)

                    progress_interval_ms = 40
                    progress_every_frames = max(
                        1, int((progress_interval_ms / 1000.0) * int(sr))
                    )

                    block = 2048
                    total = int(arr.shape[0])
                    pos = 0
                    last_progress_frames = 0
                    while pos < total:
                        if streamer._stop.is_set() or streamer._pause.is_set():
                            return False
                        end = min(pos + block, total)
                        # Volume changes should take effect mid-chunk.
                        # Read per block to reflect the latest UI setting.
                        volume = float(streamer.volume.multiplier)
                        scaled = streamer.volume_scaler.scale(
                            arr[pos:end],
                            volume=volume,
                        )
                        with streamer._sd_lock:
                            streamer._out_stream.write(scaled)
                        pos = end

                        if (
                            on_progress is not None
                            and (pos - last_progress_frames) >= progress_every_frames
                        ):
                            last_progress_frames = pos
                            try:
                                played_ms_transformed = int((pos / float(sr)) * 1000.0)
                                played_ms_original = int(
                                    played_ms_transformed * float(chunk_rate)
                                )
                                on_progress(idx, played_ms_original)
                            except Exception:
                                streamer._log.exception("on_playback_progress failed")
                    return True
            except Exception:
                pass

            # Fallback path (sd.play). Best-effort apply playback rate here too.
            play_data = data
            try:
                import numpy as np

                play_data = np.asarray(data, dtype=np.float32)
                play_data = streamer.resampler.resample_for_rate(play_data, chunk_rate)
                play_data = streamer.volume_scaler.scale(
                    play_data,
                    volume=float(streamer.volume.multiplier),
                )
            except Exception:
                play_data = data

            out_dev = safe_output_device(sd)

            try:
                with streamer._sd_lock:
                    sd_play(
                        sd,
                        data=play_data,
                        sr=int(sr),
                        blocking=False,
                        device=out_dev,
                    )
            except Exception:
                if streamer._is_tearing_down():
                    return False
                streamer._log.warning("sd.play(non-blocking) failed; falling back")
                streamer._log.debug("sd.play(non-blocking) failed", exc_info=True)
                try:
                    with streamer._sd_lock:
                        sd_play(
                            sd,
                            data=play_data,
                            sr=int(sr),
                            blocking=True,
                            device=out_dev,
                        )
                    return True
                except Exception:
                    if not streamer._is_tearing_down():
                        streamer._log.error("sd.play(blocking) failed")
                        streamer._log.debug("sd.play(blocking) failed", exc_info=True)
                    streamer._stop.set()
                    return False

            if not hasattr(sd, "get_stream"):
                with streamer._sd_lock:
                    sd.play(play_data, sr, blocking=True)
                return True

            while True:
                if streamer._stop.is_set():
                    streamer._stop_playback_device()
                    return False
                if streamer._pause.is_set():
                    streamer._stop_playback_device()
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
                        streamer._log.exception("on_playback_progress failed")

                if hasattr(sd, "sleep"):
                    sd.sleep(20)
                else:
                    time.sleep(0.02)

        while True:
            # When replaying a chunk after pause, reset the fallback wall-clock timer.
            if hasattr(play_interruptible, "_t0"):
                try:
                    delattr(play_interruptible, "_t0")
                except Exception:
                    pass

            if replaying and on_progress is not None:
                try:
                    on_progress(idx, 0)
                except Exception:
                    streamer._log.exception("on_playback_progress failed")

            finished = play_interruptible()
            if streamer._stop.is_set():
                return
            if finished:
                break

            while streamer._pause.is_set() and not streamer._stop.is_set():
                threading.Event().wait(0.05)
            if streamer._stop.is_set():
                return

            replaying = True

        if on_end is not None:
            try:
                on_end(idx)
            except Exception:
                streamer._log.exception("on_chunk_end failed")

    streamer._log.debug("Player exiting: stop set")

    try:
        with streamer._sd_lock:
            if streamer._out_stream is not None:
                try:
                    streamer._out_stream.stop()
                except Exception:
                    pass
                try:
                    streamer._out_stream.close()
                except Exception:
                    pass
                streamer._out_stream = None
                streamer._out_stream_sr = None
                streamer._out_stream_ch = None
    except Exception:
        pass
