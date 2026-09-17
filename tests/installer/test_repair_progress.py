"""Repair moves the progress bar as it works, not only at the end.

Repair used to send message-only reports, which by contract leave the bar where
it is, so the bar sat at 0% for the whole run and jumped to 100% on completion.
This runs the real repair over a temporary install and a small payload, with
only the registry and the shortcut calls replaced; it reads every report.
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from types import SimpleNamespace

import pytest

from installer.ops import progress as progress_bands
from installer.ops import repair_ops
from installer.ops.payload import ManifestEntry, PayloadManifest
from installer.ops.repair_ops import RepairOptions, repair

pytestmark = pytest.mark.skipif(os.name != "nt", reason="repair is Windows-only")

# Three files of very different sizes, one already intact, so the bar has to
# move by bytes rather than by file count.
_FILES = {"NarrateX.exe": b"x" * 4000, "lib/a.dll": b"a" * 1000, "b.txt": b"b" * 10}
_INTACT = "b.txt"


def _run_repair(tmp_path, monkeypatch) -> list:
    install = tmp_path / "install"
    install.mkdir()
    (install / _INTACT).write_bytes(_FILES[_INTACT])

    payload = tmp_path / "payload.zip"
    with zipfile.ZipFile(payload, "w") as zf:
        for name, data in _FILES.items():
            zf.writestr(name, data)
    manifest = PayloadManifest(
        installer_version="0",
        entries=tuple(
            ManifestEntry(
                path=name, size=len(data), sha256=hashlib.sha256(data).hexdigest()
            )
            for name, data in _FILES.items()
        ),
    )

    entry = SimpleNamespace(
        install_location=install,
        uninstall_string="",
        display_version="0",
        installer_path="",
    )
    shortcuts = SimpleNamespace(
        desktop_lnk=tmp_path / "desktop.lnk", start_menu_lnk=tmp_path / "start.lnk"
    )
    monkeypatch.setattr(repair_ops, "read_uninstall_entry", lambda key: entry)
    monkeypatch.setattr(repair_ops, "is_app_running", lambda exe: False)
    monkeypatch.setattr(repair_ops, "load_manifest", lambda: manifest)
    monkeypatch.setattr(repair_ops, "payload_zip_path", lambda: payload)
    monkeypatch.setattr(repair_ops, "get_shortcut_paths", lambda identity: shortcuts)
    monkeypatch.setattr(repair_ops, "create_shortcut", lambda *a, **k: None)
    monkeypatch.setattr(repair_ops, "write_uninstall_entry", lambda *a, **k: None)

    reports: list = []
    repair(
        SimpleNamespace(uninstall_key="k"),
        RepairOptions(restore_desktop_shortcut=True, restore_start_menu_shortcut=True),
        progress=reports.append,
    )
    for name, data in _FILES.items():
        assert (install / name).read_bytes() == data
    return reports


def test_repair_reports_rising_percentages_that_finish_full(
    tmp_path, monkeypatch
) -> None:
    reports = _run_repair(tmp_path, monkeypatch)
    pcts = [r["pct"] for r in reports if isinstance(r, dict)]

    assert pcts, "repair sent no percentage at all, so the bar cannot move"
    assert pcts == sorted(pcts)
    assert pcts[-1] == progress_bands.COMPLETE_PCT
    # The bar is somewhere between empty and full while files are checked.
    assert any(0 < p < progress_bands.COMPLETE_PCT for p in pcts)


def test_repair_progress_follows_bytes_not_file_count(tmp_path, monkeypatch) -> None:
    reports = _run_repair(tmp_path, monkeypatch)
    verifying = [
        r["pct"]
        for r in reports
        if isinstance(r, dict) and r["message"].startswith("Verifying")
    ]
    # The first file is 4000 of 5010 bytes: after it the bar has covered most
    # of the verification band, not a third of it.
    span = progress_bands.REPAIR_VERIFY_END_PCT - progress_bands.REPAIR_VERIFY_START_PCT
    assert verifying[0] == progress_bands.REPAIR_VERIFY_START_PCT
    assert verifying[1] - verifying[0] >= span * 3 // 4


def test_uninstall_reports_rising_percentages_that_finish_full(
    tmp_path, monkeypatch
) -> None:
    from installer.ops import uninstall_ops
    from installer.ops.uninstall_ops import UninstallOptions, uninstall_with_feedback

    install = tmp_path / "install"
    install.mkdir()
    entry = SimpleNamespace(
        install_location=install, shortcut_desktop=True, shortcut_start_menu=True
    )
    shortcuts = SimpleNamespace(
        desktop_lnk=tmp_path / "desktop.lnk", start_menu_lnk=tmp_path / "start.lnk"
    )
    scheduled: list = []
    monkeypatch.setattr(uninstall_ops, "read_uninstall_entry", lambda key: entry)
    monkeypatch.setattr(uninstall_ops, "is_app_running", lambda exe: False)
    monkeypatch.setattr(uninstall_ops, "get_shortcut_paths", lambda identity: shortcuts)
    monkeypatch.setattr(uninstall_ops, "remove_shortcut", lambda path: None)
    monkeypatch.setattr(uninstall_ops, "delete_uninstall_entry", lambda key: None)
    monkeypatch.setattr(uninstall_ops, "user_data_dir", lambda *a: str(tmp_path / "d"))
    monkeypatch.setattr(uninstall_ops, "user_cache_dir", lambda *a: str(tmp_path / "c"))
    monkeypatch.setattr(uninstall_ops, "_schedule_delete_after_exit", scheduled.append)

    reports: list = []
    uninstall_with_feedback(
        SimpleNamespace(uninstall_key="k"),
        UninstallOptions(remove_user_data=True),
        progress=reports.append,
    )
    pcts = [r["pct"] for r in reports if isinstance(r, dict)]
    assert scheduled == [install.resolve()]
    assert len(pcts) == len(reports)
    assert pcts == sorted(pcts)
    assert pcts[-1] == progress_bands.COMPLETE_PCT
    assert any(0 < p < progress_bands.COMPLETE_PCT for p in pcts)
