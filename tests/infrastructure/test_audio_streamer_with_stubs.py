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

    def fake_read(path: str, dtype: str, always_2d: bool):
        del path, dtype, always_2d
        return np.zeros(800, dtype=np.float32), 8000

    def fake_play(data, sr, blocking: bool):
        del data, sr, blocking
        played.append(1)

    def fake_stop():
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
        sleep=lambda ms: None,
    )
    monkeypatch.setitem(__import__("sys").modules, "soundfile", fake_sf)
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", fake_sd)

    streamer = SoundDeviceAudioStreamer(target_buffer_seconds=15.0)
    streamer.start(chunk_audio_paths=[p1, p2])
    assert len(played) == 2
