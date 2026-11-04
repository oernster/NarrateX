"""Tests for what the frozen builds leave out (`build_trim.py`)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

import build_trim

KEPT_WINDOWS = (
    "_internal/torch/lib/torch_cpu.dll",
    "_internal/spacy/tokenizer.cp311-win_amd64.pyd",
    "_internal/PySide6/Qt6Core.dll",
    "_internal/PySide6/Qt6Widgets.dll",
    "_internal/PySide6/plugins/platforms/qwindows.dll",
    "_internal/PySide6/plugins/imageformats/qico.dll",
    "_internal/numpy/testing/utils.py",
)
TRIMMED_WINDOWS = (
    "_internal/torch/include/ATen/ATen.h",
    "_internal/torch/lib/torch_cpu.lib",
    "_internal/spacy/tokenizer.cpp",
    "_internal/spacy/tokens/doc.pyx",
    "_internal/torch/_C/__init__.pyi",
    "_internal/spacy/tests/test_x.py",
    "_internal/PySide6/Qt6Quick.dll",
    "_internal/PySide6/Qt6Qml.dll",
    "_internal/PySide6/Qt6OpenGL.dll",
    "_internal/PySide6/Qt6Pdf.dll",
    "_internal/PySide6/Qt6VirtualKeyboard.dll",
    "_internal/PySide6/opengl32sw.dll",
    "_internal/PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
    "_internal/PySide6/plugins/imageformats/qpdf.dll",
    "_internal/PySide6/translations/qt_de.qm",
)


def _tree(root: Path, paths: tuple[str, ...]) -> None:
    for rel in paths:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 10)


def test_a_windows_bundle_loses_only_what_the_app_never_uses(tmp_path: Path) -> None:
    _tree(tmp_path, KEPT_WINDOWS + TRIMMED_WINDOWS)

    removed = build_trim.trim_bundle(tmp_path, windows=True)

    assert removed == 10 * len(TRIMMED_WINDOWS)
    assert all((tmp_path / rel).exists() for rel in KEPT_WINDOWS)
    assert not any((tmp_path / rel).exists() for rel in TRIMMED_WINDOWS)
    # Folders the trim emptied go with it.
    assert not (tmp_path / "_internal/torch/include").exists()
    assert not (tmp_path / "_internal/PySide6/plugins/platforminputcontexts").exists()


def test_elsewhere_only_the_unreachable_qt_modules_go(tmp_path: Path) -> None:
    # Linux's Wayland compositor plugins link Quick, QML and OpenGL, so those
    # stay off Windows; the keyboard and PDF modules are unreachable anywhere.
    kept = (
        "PySide6/Qt/lib/libQt6OpenGL.so.6",
        "PySide6/Qt/lib/libQt6Core.so.6",
        "PySide6/Qt/lib/libQt6Quick.so.6",
        "PySide6/Qt/lib/libQt6QuickControls2.so.6",
        "PySide6/Qt/lib/QtQml.framework/Versions/A/QtQml",
        "PySide6/Qt/plugins/platforminputcontexts/libcomposeplatforminputcontextplugin.so",
    )
    trimmed = (
        "PySide6/Qt/lib/libQt6Pdf.so.6",
        "PySide6/Qt/lib/libQt6VirtualKeyboard.so.6",
        "PySide6/Qt/lib/QtPdf.framework/Versions/A/QtPdf",
        "PySide6/Qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.so",
        "PySide6/Qt/plugins/imageformats/libqpdf.dylib",
        "PySide6/Qt/translations/qt_fr.qm",
    )
    _tree(tmp_path, kept + trimmed)

    build_trim.trim_bundle(tmp_path, windows=False)

    assert all((tmp_path / rel).exists() for rel in kept)
    assert not any((tmp_path / rel).exists() for rel in trimmed)


def test_a_test_folder_runtime_code_imports_is_kept(tmp_path: Path) -> None:
    # numpy 2.2's numpy.testing imports numpy._core.tests._natype; trimming
    # that folder stopped scipy.signal importing at all, so Kokoro failed too.
    utils = tmp_path / "_internal/numpy/testing/_private/utils.py"
    _tree(
        tmp_path,
        (
            "_internal/numpy/_core/tests/_natype.py",
            "_internal/numpy/_core/tests/test_x.py",
            "_internal/numpy/linalg/tests/test_linalg.py",
            "_internal/spacy/tests/conftest.py",
        ),
    )
    utils.parent.mkdir(parents=True)
    utils.write_text("import os\n    from numpy._core.tests._natype import pd_NA\n")
    # An import written inside a test folder keeps nothing.
    (tmp_path / "_internal/spacy/tests/conftest.py").write_text(
        "from numpy.linalg.tests import test_linalg\n"
    )

    build_trim.trim_bundle(tmp_path, windows=True)

    assert (tmp_path / "_internal/numpy/_core/tests/_natype.py").exists()
    assert utils.exists()
    assert not (tmp_path / "_internal/numpy/linalg/tests").exists()
    assert not (tmp_path / "_internal/spacy/tests").exists()


def test_a_link_left_pointing_at_a_trimmed_file_goes_too(tmp_path: Path) -> None:
    target = tmp_path / "Frameworks" / "spacy" / "vocab.cpp"
    _tree(tmp_path, ("Frameworks/spacy/vocab.cpp", "Frameworks/spacy/keep.so"))
    link = tmp_path / "Resources" / "vocab.cpp.link"
    link.parent.mkdir()
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("this account may not create symbolic links")

    build_trim.trim_bundle(tmp_path, windows=False)

    assert not link.is_symlink()
    assert (tmp_path / "Frameworks/spacy/keep.so").exists()


def test_the_command_line_trims_each_folder_named(tmp_path: Path) -> None:
    _tree(tmp_path, ("a/spacy/vocab.cpp", "a/spacy/vocab.so", "b/torch/x.h"))

    assert build_trim.main([str(tmp_path / "a"), str(tmp_path / "b")]) == 0

    assert (tmp_path / "a/spacy/vocab.so").exists()
    assert not (tmp_path / "a/spacy/vocab.cpp").exists()
    assert not (tmp_path / "b/torch").exists()


def test_the_command_line_without_a_folder_says_how_to_use_it() -> None:
    assert build_trim.main([]) == 2


def test_the_unused_packages_are_excluded_by_name() -> None:
    args = build_trim.exclude_module_args()

    assert "--exclude-module=llvmlite" in args
    assert "--exclude-module=jieba" in args
    assert all(a.startswith("--exclude-module=") for a in args)


def _pyside_dll(name: str) -> Path:
    import PySide6

    return Path(PySide6.__file__).parent / name


@pytest.mark.skipif(os.name != "nt", reason="reads Windows import tables")
def test_a_kept_binary_needing_a_trimmed_one_is_reported(tmp_path: Path) -> None:
    shutil.copy(_pyside_dll("Qt6Quick.dll"), tmp_path)

    problems = build_trim.dangling_imports(tmp_path)

    assert "Qt6Quick.dll imports qt6qml.dll" in problems
    with pytest.raises(SystemExit):
        build_trim.assert_trim_is_safe(tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="reads Windows import tables")
def test_binaries_needing_only_kept_libraries_pass(tmp_path: Path) -> None:
    shutil.copy(_pyside_dll("Qt6Core.dll"), tmp_path)
    shutil.copy(_pyside_dll("Qt6Gui.dll"), tmp_path)

    assert build_trim.dangling_imports(tmp_path) == []
    build_trim.assert_trim_is_safe(tmp_path)
