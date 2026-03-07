from __future__ import annotations

import builtins

from voice_reader.application.services.device_detection_service import (
    DeviceDetectionService,
)


def test_device_detection_falls_back_to_cpu_when_torch_missing(
    monkeypatch,
) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("no torch")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert DeviceDetectionService().detect() == "cpu"


def test_device_detection_uses_cuda_when_available(monkeypatch) -> None:
    class FakeCuda:
        @staticmethod
        def is_available() -> bool:
            return True

    class FakeTorch:
        cuda = FakeCuda()

    monkeypatch.setitem(__import__("sys").modules, "torch", FakeTorch)
    assert DeviceDetectionService().detect() == "cuda"
