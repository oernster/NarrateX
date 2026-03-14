from __future__ import annotations

import queue
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from voice_reader.infrastructure.audio.audio_streamer import (
    SoundDeviceAudioStreamer,
    _trim_silence,
    _safe_output_device,
    _sd_play,
)


def test_trim_silence_non_array_passthrough() -> None:
    obj = object()
    assert (
        _trim_silence(
            obj,
            sample_rate=16000,
            threshold=0.001,
            pad_ms=10,
            trim_leading=True,
            trim_trailing=True,
        )
        is obj
    )


def test_trim_silence_all_silence_passthrough() -> None:
    data = np.zeros(100, dtype=np.float32)
    out = _trim_silence(
        data,
        sample_rate=16000,
        threshold=0.001,
        pad_ms=10,
        trim_leading=True,
        trim_trailing=True,
    )
    assert out is data


def test_sd_play_fallback_device_errors(monkeypatch) -> None:
    calls: list[tuple] = []

    class _SD:
        def play(self, data, sr, blocking: bool, device=None):
            calls.append((blocking, device))
            if device is not None:
                raise RuntimeError("Querying device")

    _sd_play(_SD(), data=[0], sr=1, blocking=False, device=3)
    assert calls == [(False, 3), (False, None)]


def test_safe_output_device_handles_default_minus_one(monkeypatch) -> None:
    class _Default:
        device = -1

    sd = SimpleNamespace(default=_Default(), query_devices=lambda idx: None)
    assert _safe_output_device(sd) is None


def test_stop_playback_device_ignores_missing_sounddevice(monkeypatch) -> None:
    s = SoundDeviceAudioStreamer()
    monkeypatch.delitem(__import__("sys").modules, "sounddevice", raising=False)
    # Should not raise.
    s._stop_playback_device()  # pylint: disable=protected-access


def test_streamer_pause_resume_stop_smoke(monkeypatch, tmp_path: Path) -> None:
    # Stub sounddevice/soundfile to avoid audio hardware.
    p = tmp_path / "a.wav"
    p.write_bytes(b"x")

    fake_sf = SimpleNamespace(read=lambda path, dtype, always_2d: (np.zeros(100, dtype=np.float32), 8000))

    class _FakeStream:
        active = False

    class _SD:
        default = SimpleNamespace(device=[0, None])

        @staticmethod
        def query_devices(idx):
            return None

        @staticmethod
        def play(data, sr, blocking: bool, device=None):
            return None

        @staticmethod
        def stop():
            return None

        @staticmethod
        def get_stream():
            return _FakeStream()

        @staticmethod
        def sleep(ms: int):
            return None

    monkeypatch.setitem(__import__("sys").modules, "soundfile", fake_sf)
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", _SD)

    s = SoundDeviceAudioStreamer()

    # Exercise pause/resume/stop API; start() blocks until done.
    s.pause()
    s.resume()
    s.stop()
    s.start(chunk_audio_paths=[p])

