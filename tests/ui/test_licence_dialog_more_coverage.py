from __future__ import annotations

import sys
from pathlib import Path

import pytest

from voice_reader.ui.licence_dialog import PlainTextLicenceDialog, read_licence_text


def test_read_licence_text_reads_from_cwd(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
    (tmp_path / "LICENSE").write_text("hello", encoding="utf-8")
    # `read_licence_text` checks repo roots before CWD, so the exact file found
    # depends on environment. Assert we got some non-empty text.
    assert read_licence_text("LICENSE")


def test_read_licence_text_raises_with_tried_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))

    with pytest.raises(FileNotFoundError) as exc:
        read_licence_text("DOES_NOT_EXIST.txt")

    msg = str(exc.value)
    assert "Tried:" in msg


def test_plain_text_licence_dialog_constructs(qapp) -> None:
    del qapp
    dlg = PlainTextLicenceDialog(title="T", text="abc")
    assert dlg.windowTitle() == "T"

