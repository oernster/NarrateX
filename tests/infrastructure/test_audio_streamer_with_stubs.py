from __future__ import annotations

import types
from pathlib import Path

import numpy as np

from voice_reader.infrastructure.audio.audio_streamer import SoundDeviceAudioStreamer
from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume


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
    streamer.set_playback_rate(PlaybackRate(1.25))
    streamer.set_volume(PlaybackVolume(0.5))
    streamer.start(chunk_audio_paths=[p1, p2])
    # With OutputStream available, the streamer should primarily use stream.write
    # rather than sd.play().
    assert len(nonzero_writes) >= 2


def test_audio_volume_scales_samples(monkeypatch, tmp_path: Path) -> None:
    p1 = tmp_path / "1.wav"
    p1.write_bytes(b"x")

    writes: list[np.ndarray] = []

    def fake_read(path: str, dtype: str, always_2d: bool):
        del path, dtype, always_2d
        # Small deterministic waveform.
        return np.array([0.2, -0.4, 0.6, -0.8], dtype=np.float32), 8000

    class FakeOutputStream:
        def __init__(self, samplerate, channels, dtype, device=None):
            del samplerate, channels, dtype, device

        def start(self):
            return

        def write(self, data):
            writes.append(np.asarray(data, dtype=np.float32).copy())

        def stop(self):
            return

        def close(self):
            return

    fake_sf = types.SimpleNamespace(read=fake_read)
    fake_sd = types.SimpleNamespace(
        stop=lambda: None,
        query_devices=lambda dev=None, kind=None: {"index": dev, "kind": kind},
        default=types.SimpleNamespace(device=[-1, -1]),
        OutputStream=FakeOutputStream,
        sleep=lambda ms: None,
    )
    monkeypatch.setitem(__import__("sys").modules, "soundfile", fake_sf)
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", fake_sd)

    streamer = SoundDeviceAudioStreamer(target_buffer_seconds=0.1)
    streamer.pre_chunk_silence_min_ms = 0
    streamer.pre_chunk_silence_max_ms = 0
    streamer.set_playback_rate(PlaybackRate.default())

    streamer.set_volume(PlaybackVolume(1.0))
    streamer.start(chunk_audio_paths=[p1])
    # Find at least one non-silent write (ignore any gaps).
    nonzero = [w for w in writes if bool((w != 0).any())]
    assert nonzero
    wrote_full = nonzero[-1].reshape(-1)
    assert np.allclose(wrote_full, np.array([0.2, -0.4, 0.6, -0.8], np.float32))

    # Now at half volume.
    writes.clear()
    streamer = SoundDeviceAudioStreamer(target_buffer_seconds=0.1)
    streamer.pre_chunk_silence_min_ms = 0
    streamer.pre_chunk_silence_max_ms = 0
    streamer.set_playback_rate(PlaybackRate.default())
    streamer.set_volume(PlaybackVolume(0.5))
    streamer.start(chunk_audio_paths=[p1])
    nonzero = [w for w in writes if bool((w != 0).any())]
    wrote_half = nonzero[-1].reshape(-1)
    assert np.allclose(wrote_half, np.array([0.1, -0.2, 0.3, -0.4], np.float32))

    # Mute.
    writes.clear()
    streamer = SoundDeviceAudioStreamer(target_buffer_seconds=0.1)
    streamer.pre_chunk_silence_min_ms = 0
    streamer.pre_chunk_silence_max_ms = 0
    streamer.set_playback_rate(PlaybackRate.default())
    streamer.set_volume(PlaybackVolume(0.0))
    streamer.start(chunk_audio_paths=[p1])
    nonzero = [w for w in writes if bool((w != 0).any())]
    assert not nonzero


def test_audio_volume_updates_mid_chunk(monkeypatch, tmp_path: Path) -> None:
    p1 = tmp_path / "1.wav"
    p1.write_bytes(b"x")

    writes: list[np.ndarray] = []
    streamer_ref: dict[str, object] = {"streamer": None}

    def fake_read(path: str, dtype: str, always_2d: bool):
        del path, dtype, always_2d
        # Longer waveform so we can observe multiple writes.
        return np.ones(8192, dtype=np.float32), 8000

    class FakeOutputStream:
        def __init__(self, samplerate, channels, dtype, device=None):
            del samplerate, channels, dtype, device

        def start(self):
            return

        def write(self, data):
            arr = np.asarray(data, dtype=np.float32).copy()
            writes.append(arr)
            # After the first non-silent write, change volume to 0.0.
            if len([w for w in writes if bool((w != 0).any())]) == 1:
                s = streamer_ref.get("streamer")
                try:
                    if s is not None:
                        # The dict is typed loosely for test simplicity.
                        getattr(s, "set_volume")(PlaybackVolume(0.0))
                except Exception:
                    pass

        def stop(self):
            return

        def close(self):
            return

    fake_sf = types.SimpleNamespace(read=fake_read)
    fake_sd = types.SimpleNamespace(
        stop=lambda: None,
        query_devices=lambda dev=None, kind=None: {"index": dev, "kind": kind},
        default=types.SimpleNamespace(device=[-1, -1]),
        OutputStream=FakeOutputStream,
        sleep=lambda ms: None,
    )
    monkeypatch.setitem(__import__("sys").modules, "soundfile", fake_sf)
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", fake_sd)

    streamer = SoundDeviceAudioStreamer(target_buffer_seconds=0.1)
    streamer_ref["streamer"] = streamer
    streamer.pre_chunk_silence_min_ms = 0
    streamer.pre_chunk_silence_max_ms = 0
    streamer.set_playback_rate(PlaybackRate.default())
    streamer.set_volume(PlaybackVolume(1.0))
    streamer.start(chunk_audio_paths=[p1])

    nonzero = [w for w in writes if bool((w != 0).any())]
    assert nonzero
    # At least one nonzero write should occur before the volume is set to 0.
    assert float(nonzero[0].max()) == 1.0

    # After the volume change, subsequent writes should be silent.
    # (We don't assert exact timing, only that silence occurs after the first.)
    later = nonzero[1:]
    assert not later
