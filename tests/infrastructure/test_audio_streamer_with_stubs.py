from __future__ import annotations

import types
from pathlib import Path

import numpy as np

from voice_reader.infrastructure.audio.audio_streamer import SoundDeviceAudioStreamer


def test_audio_streamer_plays_all_chunks(monkeypatch, tmp_path: Path) -> None:
    p1 = tmp_path / "1.wav"
    p2 = tmp_path / "2.wav"
    p1.write_bytes(b"x")
    p2.write_bytes(b"x")

    played = []
    nonzero_writes = []

    def fake_read(path: str, dtype: str, always_2d: bool):
        del path, dtype, always_2d
        # Use non-zero audio so the OutputStream path can distinguish "real"
        # audio writes from inserted silent gaps.
        return np.ones(800, dtype=np.float32), 8000

    def fake_play(data, sr, blocking: bool):
        del data, sr, blocking
        played.append(1)

    def fake_stop():
        return

    class FakeOutputStream:
        def __init__(self, samplerate, channels, dtype, device=None):
            del samplerate, channels, dtype, device

        def start(self):
            return

        def write(self, data):
            # Count only non-zero writes (chunk audio), not inserted silence.
            try:
                if bool((np.asarray(data) != 0).any()):
                    nonzero_writes.append(1)
            except Exception:
                nonzero_writes.append(1)
            return

        def stop(self):
            return

        def close(self):
            return

    class FakeStream:
        active = False

    def fake_get_stream():
        return FakeStream()

    fake_sf = types.SimpleNamespace(read=fake_read)
    fake_sd = types.SimpleNamespace(
        play=fake_play,
        stop=fake_stop,
        get_stream=fake_get_stream,
        query_devices=lambda dev=None, kind=None: {"index": dev, "kind": kind},
        default=types.SimpleNamespace(device=[-1, -1]),
        OutputStream=FakeOutputStream,
        sleep=lambda ms: None,
    )
    monkeypatch.setitem(__import__("sys").modules, "soundfile", fake_sf)
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", fake_sd)

    streamer = SoundDeviceAudioStreamer(target_buffer_seconds=15.0)
    streamer.start(chunk_audio_paths=[p1, p2])
    # With OutputStream available, the streamer should primarily use stream.write
    # rather than sd.play().
    assert len(nonzero_writes) >= 2
