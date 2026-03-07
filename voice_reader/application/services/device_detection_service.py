"""Detect execution device for torch-based models."""

from __future__ import annotations


class DeviceDetectionService:
    def detect(self) -> str:
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            # Import errors or runtime errors should not prevent CPU usage.
            return "cpu"
