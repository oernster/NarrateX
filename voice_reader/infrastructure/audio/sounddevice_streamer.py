"""Audio streaming / playback implementation.

Design:
- A producer thread reads WAVs and pushes arrays into a queue.
- A player thread consumes arrays and plays them sequentially.

Playback-rate adjustment is applied here (playback concern only).
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume
from voice_reader.infrastructure.audio._volume_scaler import VolumeScaler
from voice_reader.infrastructure.audio._sounddevice_workers import player_loop
from voice_reader.infrastructure.audio._sounddevice_workers import producer_loop
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
    volume: PlaybackVolume = PlaybackVolume.default()
    resampler: AudioResampler = AudioResampler()
    volume_scaler: VolumeScaler = VolumeScaler()

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

    def set_volume(self, volume: PlaybackVolume) -> None:
        self.volume = volume

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
        producer_loop(self, paths)

    def _player(self, on_start, on_end, on_progress) -> None:
        player_loop(
            self,
            on_start=on_start,
            on_end=on_end,
            on_progress=on_progress,
        )
