from __future__ import annotations

from pathlib import Path

import pytest

from voice_reader.shared import startup_ui


class _FakeApp:
    """Looks like a PySide6 app for the module heuristic."""

    __module__ = "PySide6.QtWidgets"

    def __init__(self) -> None:
        self.events = 0

    def processEvents(self) -> None:
        self.events += 1


def test_is_mp_child_process_handles_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        startup_ui.mp,
        "parent_process",
        lambda: (_ for _ in ()).throw(RuntimeError("x")),
    )
    assert startup_ui.is_mp_child_process() is False


def test_is_real_pyside_app_false_for_plain_object() -> None:
    assert startup_ui.is_real_pyside_app(object()) is False


def test_setup_single_instance_returns_primary_when_allow_multi(tmp_path: Path) -> None:
    g, is_primary = startup_ui.setup_single_instance(
        app=_FakeApp(),
        app_id="com.oliverernster.narratex",
        allow_multi=True,
        lock_dir=tmp_path,
        on_activate=lambda: None,
    )
    assert g is None
    assert is_primary is True


def test_maybe_show_splash_returns_none_when_disabled(tmp_path: Path) -> None:
    app = _FakeApp()
    out = startup_ui.maybe_show_splash(
        app=app, icon=None, project_root=tmp_path, enabled=False
    )
    assert out is None


def test_activate_window_calls_all_methods() -> None:
    calls = {"n": 0}

    class _W:
        def showNormal(self):
            calls["n"] += 1

        def raise_(self):
            calls["n"] += 1

        def activateWindow(self):
            calls["n"] += 1

    startup_ui.activate_window(_W())
    assert calls["n"] == 3


def test_activate_window_swallow_exceptions() -> None:
    class _W:
        def showNormal(self):
            raise RuntimeError("x")

        def raise_(self):
            raise RuntimeError("x")

        def activateWindow(self):
            raise RuntimeError("x")

    startup_ui.activate_window(_W())


def test_default_lock_dir_uses_cwd_when_temp_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("TEMP", raising=False)
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
    out = startup_ui.default_lock_dir(app_name="NarrateX")
    assert out == tmp_path / "NarrateX"


def test_is_real_pyside_app_true_for_fake_pyside_like_object() -> None:
    # __class__.__module__ is used; emulate that.
    class _C:
        __module__ = "PySide6.QtWidgets"

    o = object.__new__(_C)
    assert startup_ui.is_real_pyside_app(o) is True


def test_is_real_pyside_app_handles_attribute_errors() -> None:
    class _Bad:
        def __getattribute__(self, name: str):  # noqa: ANN204
            if name == "__class__":
                raise RuntimeError("no")
            return super().__getattribute__(name)

    assert startup_ui.is_real_pyside_app(_Bad()) is False


def test_setup_single_instance_skips_for_child_process(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(startup_ui, "is_mp_child_process", lambda: True)
    g, is_primary = startup_ui.setup_single_instance(
        app=_FakeApp(),
        app_id="com.oliverernster.narratex",
        allow_multi=False,
        lock_dir=tmp_path,
        on_activate=lambda: None,
    )
    assert g is None
    assert is_primary is True


def test_setup_single_instance_resolves_paths_and_calls_guard(
    tmp_path: Path, monkeypatch
) -> None:
    called = {"n": 0}

    class _G:
        def __init__(self, *, paths, on_activate):  # noqa: ANN001
            self.paths = paths
            self.on_activate = on_activate

        def try_become_primary(self) -> bool:
            called["n"] += 1
            return True

    monkeypatch.setattr(startup_ui, "SingleInstance", _G)
    monkeypatch.setattr(startup_ui, "is_real_pyside_app", lambda app: True)
    g, is_primary = startup_ui.setup_single_instance(
        app=_FakeApp(),
        app_id="com.oliverernster.narratex",
        allow_multi=False,
        lock_dir=tmp_path,
        on_activate=lambda: None,
    )
    assert g is not None
    assert is_primary is True
    assert called["n"] == 1


def test_maybe_show_splash_import_failure_returns_none(
    tmp_path: Path, monkeypatch
) -> None:
    # Force import failure branch.
    monkeypatch.setattr(startup_ui, "is_real_pyside_app", lambda app: True)

    class _A:
        pass

    _A.__module__ = "PySide6.QtWidgets"

    # Remove PySide6 in sys.modules so imports fail (and ensure it is reverted).
    import sys

    monkeypatch.setitem(sys.modules, "PySide6.QtGui", None)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", None)
    assert (
        startup_ui.maybe_show_splash(
            app=_A(),
            icon=None,
            project_root=tmp_path,
            enabled=True,
        )
        is None
    )


def test_maybe_show_splash_no_file_returns_none(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(startup_ui, "is_real_pyside_app", lambda app: True)
    monkeypatch.setattr(startup_ui, "find_splash_image_path", lambda project_root: None)
    assert (
        startup_ui.maybe_show_splash(
            app=_FakeApp(), icon=None, project_root=tmp_path, enabled=True
        )
        is None
    )


def test_maybe_show_splash_happy_path_shows_and_finishes(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(startup_ui, "is_real_pyside_app", lambda app: True)
    monkeypatch.setattr(
        startup_ui,
        "find_splash_image_path",
        lambda project_root: tmp_path / "narratex_256.png",
    )

    class _Pm:
        def __init__(self, _path: str) -> None:
            self._null = False

        def isNull(self) -> bool:  # noqa: N802
            return self._null

    events = {"n": 0}

    class _Splash:
        def __init__(self, pm) -> None:  # noqa: ANN001
            self.pm = pm
            self.icon_set = 0
            self.shown = 0

        def setWindowIcon(self, _icon):  # noqa: ANN001, N802
            self.icon_set += 1

        def show(self) -> None:
            self.shown += 1

    # Provide fake PySide6 modules importable by maybe_show_splash.
    import sys
    import types

    fake_gui = types.SimpleNamespace(QPixmap=_Pm)
    fake_widgets = types.SimpleNamespace(QSplashScreen=_Splash)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", fake_gui)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", fake_widgets)

    app = _FakeApp()
    splash = startup_ui.maybe_show_splash(
        app=app,
        icon=object(),
        project_root=tmp_path,
        enabled=True,
    )
    assert splash is not None
    assert getattr(splash, "shown") == 1
    assert app.events == 1


def test_maybe_show_splash_returns_none_when_pixmap_is_null(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        startup_ui,
        "find_splash_image_path",
        lambda project_root: tmp_path / "narratex_256.png",
    )

    class _Pm:
        def __init__(self, _path: str) -> None:
            return

        def isNull(self) -> bool:  # noqa: N802
            return True

    class _Splash:
        def __init__(self, _pm) -> None:  # noqa: ANN001
            raise AssertionError("should not be constructed")

    import sys
    import types

    monkeypatch.setitem(
        sys.modules, "PySide6.QtGui", types.SimpleNamespace(QPixmap=_Pm)
    )
    monkeypatch.setitem(
        sys.modules, "PySide6.QtWidgets", types.SimpleNamespace(QSplashScreen=_Splash)
    )

    assert (
        startup_ui.maybe_show_splash(
            app=_FakeApp(), icon=None, project_root=tmp_path, enabled=True
        )
        is None
    )


def test_maybe_show_splash_swallow_set_window_icon_error(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        startup_ui,
        "find_splash_image_path",
        lambda project_root: tmp_path / "narratex_256.png",
    )

    class _Pm:
        def __init__(self, _path: str) -> None:
            self._null = False

        def isNull(self) -> bool:  # noqa: N802
            return self._null

    class _Splash:
        def __init__(self, pm) -> None:  # noqa: ANN001
            self.pm = pm
            self.shown = 0

        def setWindowIcon(self, _icon):  # noqa: ANN001, N802
            raise RuntimeError("no")

        def show(self) -> None:
            self.shown += 1

    import sys
    import types

    monkeypatch.setitem(
        sys.modules, "PySide6.QtGui", types.SimpleNamespace(QPixmap=_Pm)
    )
    monkeypatch.setitem(
        sys.modules, "PySide6.QtWidgets", types.SimpleNamespace(QSplashScreen=_Splash)
    )

    app = _FakeApp()
    splash = startup_ui.maybe_show_splash(
        app=app,
        icon=object(),
        project_root=tmp_path,
        enabled=True,
    )
    assert splash is not None
    assert getattr(splash, "shown") == 1
    assert app.events == 1


def test_maybe_show_splash_outer_exception_returns_none(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        startup_ui,
        "find_splash_image_path",
        lambda project_root: tmp_path / "narratex_256.png",
    )

    class _Pm:
        def __init__(self, _path: str) -> None:
            raise RuntimeError("boom")

    class _Splash:
        def __init__(self, _pm) -> None:  # noqa: ANN001
            raise AssertionError("should not be constructed")

    import sys
    import types

    monkeypatch.setitem(
        sys.modules, "PySide6.QtGui", types.SimpleNamespace(QPixmap=_Pm)
    )
    monkeypatch.setitem(
        sys.modules, "PySide6.QtWidgets", types.SimpleNamespace(QSplashScreen=_Splash)
    )

    assert (
        startup_ui.maybe_show_splash(
            app=_FakeApp(), icon=None, project_root=tmp_path, enabled=True
        )
        is None
    )
