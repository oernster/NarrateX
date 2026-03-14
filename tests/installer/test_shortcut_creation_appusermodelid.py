from __future__ import annotations

import os
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from installer.ops.shortcuts import create_shortcut
from voice_reader.version import APP_APPUSERMODELID


def _is_windows() -> bool:
    return os.name == "nt"


def test_create_shortcut_uses_shell_link_com_and_stamps_appusermodelid(
    monkeypatch, tmp_path: Path
) -> None:
    """Unit test: verify COM call-path without touching real COM.

    This runs cross-platform by mocking the COM modules used by
    [`installer.ops.shortcuts.create_shortcut()`](installer/ops/shortcuts.py:60).
    """

    calls: list[tuple[str, object]] = []

    iid_property_store = object()
    iid_persist_file = object()

    class _FakePropertyStore:
        def SetValue(self, key, pv) -> None:  # noqa: N802, ANN001
            calls.append(("SetValue", (key, pv)))

        def Commit(self) -> None:  # noqa: N802
            calls.append(("Commit", None))

    class _FakePersistFile:
        def Save(self, path: str, flags: int) -> None:  # noqa: N802
            calls.append(("Save", (path, flags)))

    class _FakeShellLink:
        def SetPath(self, path: str) -> None:  # noqa: N802
            calls.append(("SetPath", path))

        def SetWorkingDirectory(self, path: str) -> None:  # noqa: N802
            calls.append(("SetWorkingDirectory", path))

        def SetIconLocation(self, path: str, index: int) -> None:  # noqa: N802
            calls.append(("SetIconLocation", (path, index)))

        def QueryInterface(self, iid):  # noqa: ANN001
            calls.append(("QueryInterface", iid))
            if iid is iid_property_store:
                return _FakePropertyStore()
            if iid is iid_persist_file:
                return _FakePersistFile()
            raise AssertionError(f"Unexpected IID: {iid!r}")

    # Patch module imports inside create_shortcut by pre-inserting into sys.modules.
    #
    # create_shortcut imports:
    # - `import pythoncom`
    # - `from win32com.propsys import propsys`
    # - `from win32com.shell import shell`
    import sys
    import installer.ops.shortcuts as shortcuts

    monkeypatch.setattr(shortcuts, "_require_windows", lambda: None)

    fake_link = _FakeShellLink()

    fake_pythoncom = ModuleType("pythoncom")
    setattr(fake_pythoncom, "CLSCTX_INPROC_SERVER", 1)
    setattr(fake_pythoncom, "IID_IPersistFile", iid_persist_file)

    def _co_initialize() -> None:
        calls.append(("CoInitialize", None))

    def _co_uninitialize() -> None:
        calls.append(("CoUninitialize", None))

    def _co_create_instance(clsid, _, ctx, iid):  # noqa: ANN001
        calls.append(("CoCreateInstance", (clsid, ctx, iid)))
        return fake_link

    fake_pythoncom.CoInitialize = _co_initialize  # type: ignore[attr-defined]
    fake_pythoncom.CoUninitialize = _co_uninitialize  # type: ignore[attr-defined]
    fake_pythoncom.CoCreateInstance = _co_create_instance  # type: ignore[attr-defined]

    fake_propsys_mod = ModuleType("win32com.propsys.propsys")
    setattr(fake_propsys_mod, "IID_IPropertyStore", iid_property_store)

    def _ps_get_property_key_from_name(name: str):  # noqa: ANN001
        calls.append(("PSGetPropertyKeyFromName", name))
        return f"key:{name}"

    def _propvariant_type(value: str):  # noqa: ANN001
        calls.append(("PROPVARIANTType", value))
        return f"pv:{value}"

    fake_propsys_mod.PSGetPropertyKeyFromName = _ps_get_property_key_from_name  # type: ignore[attr-defined]
    fake_propsys_mod.PROPVARIANTType = _propvariant_type  # type: ignore[attr-defined]

    fake_shell_mod = ModuleType("win32com.shell.shell")
    setattr(fake_shell_mod, "CLSID_ShellLink", object())
    setattr(fake_shell_mod, "IID_IShellLink", object())

    fake_win32com = ModuleType("win32com")
    fake_win32com_propsys = ModuleType("win32com.propsys")
    fake_win32com_shell = ModuleType("win32com.shell")
    fake_win32com_propsys.propsys = fake_propsys_mod  # type: ignore[attr-defined]
    fake_win32com_shell.shell = fake_shell_mod  # type: ignore[attr-defined]
    fake_win32com.propsys = fake_win32com_propsys  # type: ignore[attr-defined]
    fake_win32com.shell = fake_win32com_shell  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "pythoncom", fake_pythoncom)
    monkeypatch.setitem(sys.modules, "win32com", fake_win32com)
    monkeypatch.setitem(sys.modules, "win32com.propsys", fake_win32com_propsys)
    monkeypatch.setitem(sys.modules, "win32com.propsys.propsys", fake_propsys_mod)
    monkeypatch.setitem(sys.modules, "win32com.shell", fake_win32com_shell)
    monkeypatch.setitem(sys.modules, "win32com.shell.shell", fake_shell_mod)

    target_exe = tmp_path / "NarrateX.exe"
    target_exe.write_text("stub")
    shortcut_path = tmp_path / "NarrateX.lnk"
    working_dir = tmp_path

    create_shortcut(target_exe, shortcut_path, working_dir=working_dir)

    # High-level assertions: we initialize COM, create IShellLink, set path/dir/icon,
    # stamp app user model ID via IPropertyStore, then persist.
    assert ("CoInitialize", None) in calls
    assert any(name == "CoCreateInstance" for name, _ in calls)
    assert ("SetPath", str(target_exe)) in calls
    assert ("SetWorkingDirectory", str(working_dir)) in calls
    icon_calls = [args for name, args in calls if name == "SetIconLocation"]
    assert icon_calls, "Expected SetIconLocation to be called"
    icon_args = cast(tuple[str, int], icon_calls[-1])
    assert icon_args[1] == 0
    assert ("PSGetPropertyKeyFromName", "System.AppUserModel.ID") in calls
    assert ("PROPVARIANTType", APP_APPUSERMODELID) in calls
    assert any(name == "Commit" for name, _ in calls)
    assert ("Save", (str(shortcut_path), 0)) in calls
    assert ("CoUninitialize", None) in calls


@pytest.mark.skipif(not _is_windows(), reason="Windows-only COM integration test")
def test_create_shortcut_writes_appusermodelid_property(tmp_path: Path) -> None:
    """Integration test: create a real .lnk and read back System.AppUserModel.ID."""

    pythoncom = pytest.importorskip("pythoncom")
    propsys = pytest.importorskip("win32com.propsys.propsys")
    shell = pytest.importorskip("win32com.shell.shell")

    target = (
        Path(os.environ.get("SystemRoot", r"C:\\Windows")) / "System32" / "notepad.exe"
    )
    if not target.exists():
        pytest.skip("notepad.exe not found; cannot create representative shortcut")

    shortcut_path = tmp_path / "NarrateX_Test.lnk"

    # Act: use production shortcut creation.
    create_shortcut(target, shortcut_path, working_dir=target.parent)
    assert shortcut_path.exists(), "Expected .lnk to be created"

    # Assert: read back property via IShellLink + IPropertyStore.
    pythoncom.CoInitialize()
    try:
        key = propsys.PSGetPropertyKeyFromName("System.AppUserModel.ID")
        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink,
            None,
            pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IShellLink,
        )
        persist = link.QueryInterface(pythoncom.IID_IPersistFile)
        persist.Load(str(shortcut_path), 0)
        store = link.QueryInterface(propsys.IID_IPropertyStore)
        pv = store.GetValue(key)
        assert pv.GetValue() == APP_APPUSERMODELID
    finally:
        pythoncom.CoUninitialize()
