from __future__ import annotations

import os
from pathlib import Path

import pytest

from voice_reader.shared import external_runtime


def test_exe_dir_prefers_argv0_exe_when_it_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    exe = tmp_path / "NarrateX.exe"
    exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(external_runtime.sys, "argv", [str(exe)])
    monkeypatch.setattr(external_runtime.sys, "executable", str(tmp_path / "python.exe"))

    assert external_runtime._exe_dir() == tmp_path


def test_exe_dir_falls_back_to_sys_executable_when_argv0_is_bad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(external_runtime.sys, "argv", [None])
    monkeypatch.setattr(external_runtime.sys, "executable", str(tmp_path / "python.exe"))

    assert external_runtime._exe_dir() == tmp_path


def test_exe_dir_falls_back_to_cwd_when_sys_executable_is_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(external_runtime.sys, "argv", [None])
    monkeypatch.setattr(external_runtime.sys, "executable", None)
    # _exe_dir() falls back to Path.cwd(), but returns cwd.parent.
    monkeypatch.setattr(external_runtime.Path, "cwd", classmethod(lambda cls: tmp_path))

    assert external_runtime._exe_dir() == tmp_path.parent


def test_add_external_site_packages_returns_none_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(external_runtime, "_exe_dir", lambda: tmp_path)
    assert external_runtime.add_external_site_packages(ext_dir_name="ext") is None


def test_add_external_site_packages_inserts_path_and_adds_dll_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(external_runtime, "_exe_dir", lambda: tmp_path)
    ext_dir = tmp_path / "ext"
    (ext_dir / "torch" / "lib").mkdir(parents=True)
    (ext_dir / "_soundfile_data").mkdir(parents=True)
    (ext_dir / "_sounddevice_data" / "portaudio-binaries").mkdir(parents=True)

    calls: list[str] = []

    def fake_add_dll_directory(p: str):
        calls.append(p)

    monkeypatch.setattr(os, "add_dll_directory", fake_add_dll_directory, raising=False)

    # Ensure the function inserts into sys.path.
    ext_str = str(ext_dir)
    if ext_str in external_runtime.sys.path:
        external_runtime.sys.path.remove(ext_str)

    inserted = external_runtime.add_external_site_packages(ext_dir_name="ext")

    assert inserted == ext_dir
    assert external_runtime.sys.path[0] == ext_str
    # One call for ext/, plus sub-dirs that exist.
    assert len(calls) >= 2


def test_add_external_site_packages_swallows_add_dll_directory_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(external_runtime, "_exe_dir", lambda: tmp_path)
    ext_dir = tmp_path / "ext"
    # Create a DLL subdir so we exercise the guarded add_dll_directory calls
    # inside the per-subdir loop as well.
    (ext_dir / "torch" / "lib").mkdir(parents=True)

    def boom(_: str):
        raise OSError("nope")

    monkeypatch.setattr(os, "add_dll_directory", boom, raising=False)

    inserted = external_runtime.add_external_site_packages(ext_dir_name="ext")

    assert inserted == ext_dir
    assert str(ext_dir) in external_runtime.sys.path


def test_configure_huggingface_cache_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(external_runtime, "_exe_dir", lambda: tmp_path)
    assert external_runtime.configure_huggingface_cache(cache_dir_name="hf-cache") is None


def test_configure_huggingface_cache_sets_env_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(external_runtime, "_exe_dir", lambda: tmp_path)
    cache_dir = tmp_path / "hf-cache"
    cache_dir.mkdir(parents=True)

    # Start clean to ensure we cover setdefault behavior.
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_CACHE", raising=False)

    configured = external_runtime.configure_huggingface_cache(cache_dir_name="hf-cache")

    assert configured == cache_dir
    assert os.environ["HF_HOME"] == str(cache_dir)
    assert os.environ["HF_HUB_CACHE"] == str(cache_dir)
    assert os.environ["TRANSFORMERS_CACHE"] == str(cache_dir)

