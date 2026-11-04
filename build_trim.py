"""What the frozen builds leave out, shared by every PyInstaller build script.

Measured on 2026-11-04 against a full Windows bundle (1,123 MB) and a run of
the app from source that imported every module, parsed a PDF and an EPUB,
synthesised speech in both English voices and opened the audio device, then
listed every module and DLL the process had loaded. Two kinds of thing were
shipped and never touched:

- Packages nothing on the app's path imports: numba with llvmlite (pulled in
  by an optional import, 102 MB), jieba and pypinyin (misaki's Chinese
  pipeline; the app builds English ones only) and pywin32's Pythonwin.
- Files no program executes: C and C++ sources, headers, static libraries,
  type stubs and test folders, 170 MB, most of it spaCy's .cpp files and
  torch's include folder and .lib files.

Qt modules the app does not load go too: the virtual keyboard plugin drags in
Quick, QML and OpenGL on Windows; the PDF image plugin drags in Qt6Pdf; the
app sets up no translator, so Qt's own translations are never read. Every Qt library
the app does load stays a separate file the user can replace, as the LGPL-3.0
asks of a shared library; nothing here merges or seals one.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

# PyInstaller --exclude-module names: never imported on the app's path.
EXCLUDED_MODULES = (
    "numba",
    "llvmlite",
    "jieba",
    "pypinyin",
    "pythonwin",
    "win32ui",
)

# Files a running program never reads.
NON_RUNTIME_SUFFIXES = frozenset(
    {".c", ".cpp", ".h", ".hpp", ".cuh", ".pyx", ".pxd", ".pxi", ".lib", ".a", ".pyi"}
)
NON_RUNTIME_DIRS = frozenset({"tests"})
# A test folder some code outside every test folder imports is runtime code
# after all and stays: numpy 2.2's numpy.testing imports
# numpy._core.tests._natype, which scipy.signal reaches via array_api_compat.
_TESTS_IMPORT = re.compile(
    r"^[ \t]*(?:from|import)[ \t]+((?:[A-Za-z_]\w*\.)+tests)\b", re.MULTILINE
)

# Qt modules the app never loads, named as Qt names them. VirtualKeyboard and
# Pdf are unreachable on every platform: on Linux, read from every library's
# DT_NEEDED in the 6.10.2 wheel, walking from the app's four Qt modules and
# every plugin a desktop session loads. Quick, QML and OpenGL are trimmed on
# Windows alone, where assert_trim_is_safe checks each build; on Linux the
# Wayland compositor plugins link them, so they stay there and on macOS.
UNUSED_QT_MODULES = ("VirtualKeyboard", "Pdf")
UNUSED_QT_MODULES_WINDOWS = (
    "Quick",
    "Qml",
    "QmlModels",
    "QmlMeta",
    "QmlWorkerScript",
    "OpenGL",
)
# Plugins that load the modules above, matched within the plugin file name.
UNUSED_QT_PLUGIN_MARKERS = ("virtualkeyboard", "qpdf")
# Software OpenGL for machines without a driver; only Quick asks for it.
UNUSED_QT_FILES = frozenset({"opengl32sw.dll"})
QT_TRANSLATIONS_DIR = "translations"

_MB = 1024 * 1024


def exclude_module_args() -> list[str]:
    """The PyInstaller flags that leave the unused packages out."""

    return [f"--exclude-module={name}" for name in EXCLUDED_MODULES]


def _qt_module_names(*, windows: bool) -> tuple[str, ...]:
    return UNUSED_QT_MODULES + (UNUSED_QT_MODULES_WINDOWS if windows else ())


def _is_unused_qt(path: Path, *, windows: bool) -> bool:
    name = path.name
    lowered = name.lower()
    if lowered in UNUSED_QT_FILES:
        return True
    if path.parent.parent.name == "plugins" and any(
        marker in lowered for marker in UNUSED_QT_PLUGIN_MARKERS
    ):
        return True
    for module in _qt_module_names(windows=windows):
        if name == f"Qt6{module}.dll" or name == f"Qt{module}.framework":
            return True
        if name.startswith(f"libQt6{module}.so"):
            return True
    return False


def _is_qt_translations(path: Path) -> bool:
    return path.name == QT_TRANSLATIONS_DIR and "PySide6" in path.parts


def _size(path: Path) -> int:
    if path.is_symlink():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(
        p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink()
    )


def _remove(path: Path) -> int:
    removed = _size(path)
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)
    return removed


def _in_test_dir(path: Path) -> bool:
    return any(part in NON_RUNTIME_DIRS for part in path.parts)


def imported_test_packages(root: Path) -> frozenset[tuple[str, ...]]:
    """Every test package that code outside a test folder in `root` imports.

    Answered as the package's dotted name split into parts, matched later
    against the tail of a folder's path, so it holds wherever the packages
    sit in the bundle (site-packages, PyInstaller's _internal, a .app).
    """

    found: set[tuple[str, ...]] = set()
    for source in root.rglob("*.py"):
        relative = source.relative_to(root)
        if _in_test_dir(relative.parent) or not source.is_file():
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        for match in _TESTS_IMPORT.finditer(text):
            found.add(tuple(match.group(1).split(".")))
    return frozenset(found)


def _is_needed_test_dir(path: Path, needed: frozenset[tuple[str, ...]]) -> bool:
    return any(path.parts[-len(parts) :] == parts for parts in needed)


def _doomed(
    path: Path, *, windows: bool, needed: frozenset[tuple[str, ...]] = frozenset()
) -> bool:
    if path.is_dir() and not path.is_symlink():
        return (
            (path.name in NON_RUNTIME_DIRS and not _is_needed_test_dir(path, needed))
            or _is_qt_translations(path)
            or _is_unused_qt(path, windows=windows)
        )
    return path.suffix.lower() in NON_RUNTIME_SUFFIXES or _is_unused_qt(
        path, windows=windows
    )


def _sweep_dangling(root: Path) -> bool:
    """Remove each link pointing at nothing and each empty folder; answer
    whether anything went.

    One pass is not enough: a folder emptied here can be the target of a link
    already checked in this pass (a macOS bundle's Frameworks link sits at the
    same depth as its Resources folder); removing a link can empty its folder
    in turn. The caller repeats until a pass removes nothing.
    """

    changed = False
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_symlink() and not path.exists():
            path.unlink()
            changed = True
        elif path.is_dir() and not path.is_symlink() and not any(path.iterdir()):
            path.rmdir()
            changed = True
    return changed


def trim_bundle(root: Path, *, windows: bool | None = None) -> int:
    """Remove from a built bundle what the app never uses; answer the bytes.

    A test folder that code outside every test folder imports is kept, since
    that code needs it at run time. Walks top down so a removed folder is not
    walked into. A macOS bundle
    links its files between Frameworks and Resources, so any link left
    pointing at nothing is removed too, then any folder left empty.
    """

    on_windows = os.name == "nt" if windows is None else windows
    needed = imported_test_packages(root)
    removed = 0
    for current, dirs, files in os.walk(root):
        here = Path(current)
        for name in list(dirs):
            path = here / name
            if _doomed(path, windows=on_windows, needed=needed):
                removed += _remove(path)
                dirs.remove(name)
        for name in files:
            path = here / name
            if _doomed(path, windows=on_windows):
                removed += _remove(path)
    while _sweep_dangling(root):
        pass
    print(f"  Trimmed {removed / _MB:.1f} MB the app never uses from {root}")
    return removed


def dangling_imports(root: Path) -> list[str]:
    """Every Windows binary in `root` importing a DLL that was trimmed away.

    Read from each binary's import table, so a trim that removed something
    still needed fails the build here rather than on the user's machine.
    """

    import pefile

    removed = {
        f"qt6{module}.dll".lower() for module in _qt_module_names(windows=True)
    } | set(UNUSED_QT_FILES)
    present = {p.name.lower() for p in root.rglob("*") if p.is_file()}
    missing = removed - present
    found: list[str] = []
    for binary in root.rglob("*"):
        if binary.suffix.lower() not in {".dll", ".pyd", ".exe"}:
            continue
        pe = pefile.PE(str(binary), fast_load=True)
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        )
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            name = entry.dll.decode("ascii", "replace").lower()
            if name in missing:
                found.append(f"{binary.relative_to(root)} imports {name}")
        pe.close()
    return found


def assert_trim_is_safe(root: Path) -> None:
    """Stop the build if a kept Windows binary needs a trimmed one."""

    problems = dangling_imports(root)
    if problems:
        raise SystemExit(
            "A trimmed library is still needed; restore it in build_trim.py:\n"
            + "\n".join(f"  {p}" for p in problems)
        )
    print("  No kept binary imports a trimmed one.")


def main(argv: list[str]) -> int:
    """Trim each folder named, as the Flatpak build does its site-packages."""

    if not argv:
        print("usage: python build_trim.py FOLDER [FOLDER ...]")
        return 2
    for folder in argv:
        trim_bundle(Path(folder))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
