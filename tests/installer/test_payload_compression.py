"""The installer reads the payload exactly as the build compresses it."""

from __future__ import annotations

import zipfile
from pathlib import Path

from installer.build_payload import PAYLOAD_COMPRESSION
from installer.ops.staging import extract_payload_to

_BODY = bytes(range(256)) * 64


def test_a_payload_compressed_as_the_build_does_lands_intact(tmp_path: Path) -> None:
    zip_path = tmp_path / "payload.zip"
    with zipfile.ZipFile(zip_path, "w", compression=PAYLOAD_COMPRESSION) as zf:
        zf.writestr("NarrateX.exe", _BODY)
        zf.writestr("_internal/torch_cpu.dll", _BODY[::-1])
    staging = tmp_path / "staging"

    extract_payload_to(staging, zip_path=zip_path)

    assert (staging / "NarrateX.exe").read_bytes() == _BODY
    assert (staging / "_internal/torch_cpu.dll").read_bytes() == _BODY[::-1]


def test_the_payload_is_lzma_compressed() -> None:
    # Measured on the bundle's binaries: about 37% smaller than deflate.
    assert PAYLOAD_COMPRESSION == zipfile.ZIP_LZMA
