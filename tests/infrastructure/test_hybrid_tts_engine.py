from __future__ import annotations

from pathlib import Path

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.infrastructure.tts.hybrid_engine import HybridTTSEngine


class _FakeEngine:
    def __init__(self, name: str) -> None:
        self._name = name
        self.calls: list[dict] = []

    @property
    def engine_name(self) -> str:
        return self._name

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
        device: str,
        language: str,
    ) -> Path:
        self.calls.append(
            {
                "text": text,
                "voice_profile": voice_profile,
                "output_path": output_path,
                "device": device,
                "language": language,
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self._name.encode("utf-8"))
        return output_path


def test_hybrid_uses_cloning_engine_when_reference_audio_present(tmp_path: Path) -> None:
    cloning = _FakeEngine("clone")
    native = _FakeEngine("native")
    engine = HybridTTSEngine(cloning_engine=cloning, native_engine=native)

    out = tmp_path / "o.wav"
    vp = VoiceProfile(name="any", reference_audio_paths=[tmp_path / "ref.wav"])
    (tmp_path / "ref.wav").write_bytes(b"x")

    engine.synthesize_to_file(
        text="hello",
        voice_profile=vp,
        output_path=out,
        device="cpu",
        language="en",
    )

    assert out.read_bytes() == b"clone"
    assert len(cloning.calls) == 1
    assert len(native.calls) == 0


def test_hybrid_uses_native_engine_when_no_reference_audio(tmp_path: Path) -> None:
    cloning = _FakeEngine("clone")
    native = _FakeEngine("native")
    engine = HybridTTSEngine(cloning_engine=cloning, native_engine=native)

    out = tmp_path / "o.wav"
    vp = VoiceProfile(name="bm_george", reference_audio_paths=[])

    engine.synthesize_to_file(
        text="hello",
        voice_profile=vp,
        output_path=out,
        device="cpu",
        language="en",
    )

    assert out.read_bytes() == b"native"
    assert len(cloning.calls) == 0
    assert len(native.calls) == 1

