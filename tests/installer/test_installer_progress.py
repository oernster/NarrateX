"""The installer must show progress while it works, and reach 100% visibly.

Two defects sat behind this. Extraction ran as one blocking call, so the bar
held at its opening value for the whole of the longest phase. And the finished
value was written after the controls were released, which takes the bar off
screen, so nobody ever saw it fill.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit, QProgressBar, QPushButton

from installer.ops.progress import (
    COMPLETE_PCT,
    EXTRACT_END_PCT,
    EXTRACT_START_PCT,
    report,
)
from installer.ops.staging import extract_payload_to
from installer.ui._main_window_progress import (
    clear_progress_display,
    on_progress,
    set_ui_busy,
    show_complete,
)

# Enough members, at enough different sizes, that a byte-weighted report has
# something to say between the start and end of the band.
_MEMBER_COUNT = 40
_MEMBER_BYTES = 4096


def _payload_zip(tmp_path: Path) -> Path:
    """A stand-in bundle carrying the two entries the installer insists on."""

    zip_path = tmp_path / "payload.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("NarrateX.exe", b"x" * _MEMBER_BYTES)
        zf.writestr("_internal/base_library.zip", b"y" * _MEMBER_BYTES)
        for index in range(_MEMBER_COUNT):
            zf.writestr(f"_internal/lib_{index}.pyd", b"z" * _MEMBER_BYTES)
    return zip_path


class _Reports:
    """Collects what the worker would have sent to the UI."""

    def __init__(self) -> None:
        self.payloads: list[object] = []

    def __call__(self, payload) -> None:  # noqa: ANN001
        self.payloads.append(payload)

    @property
    def percentages(self) -> list[int]:
        return [
            int(p["pct"])
            for p in self.payloads
            if isinstance(p, dict) and isinstance(p.get("pct"), int)
        ]


class TestExtractionReportsProgress:
    def test_extraction_reports_more_than_its_opening_value(
        self, tmp_path: Path
    ) -> None:
        reports = _Reports()

        extract_payload_to(
            tmp_path / "staging",
            progress=reports,
            zip_path=_payload_zip(tmp_path),
        )

        percentages = reports.percentages
        assert percentages, "extraction reported nothing at all"
        # The defect: a single report at the opening value, then silence.
        assert len(set(percentages)) > 1, f"bar never moved: {percentages}"

    def test_reported_progress_rises_and_stays_inside_the_band(
        self, tmp_path: Path
    ) -> None:
        reports = _Reports()

        extract_payload_to(
            tmp_path / "staging",
            progress=reports,
            zip_path=_payload_zip(tmp_path),
        )

        percentages = reports.percentages
        assert percentages == sorted(percentages)
        assert percentages[0] == EXTRACT_START_PCT
        assert max(percentages) <= EXTRACT_END_PCT

    def test_the_payload_still_lands_on_disk(self, tmp_path: Path) -> None:
        staging = tmp_path / "staging"

        extract_payload_to(staging, zip_path=_payload_zip(tmp_path))

        assert (staging / "NarrateX.exe").exists()
        assert (staging / "_internal").is_dir()
        assert len(list((staging / "_internal").iterdir())) == _MEMBER_COUNT + 1

    def test_cancelling_stops_the_extraction(self, tmp_path: Path) -> None:
        # A single blocking extractall had nowhere to observe a cancel.
        class _AlreadyCancelled:
            def is_set(self) -> bool:
                return True

        with pytest.raises(Exception, match="Cancelled"):
            extract_payload_to(
                tmp_path / "staging",
                cancel_event=_AlreadyCancelled(),
                zip_path=_payload_zip(tmp_path),
            )

    def test_an_empty_archive_does_not_divide_by_zero(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("NarrateX.exe", b"")
            zf.writestr("_internal/marker", b"")

        extract_payload_to(tmp_path / "staging", zip_path=zip_path)


class TestReportShape:
    def test_a_percentage_report_carries_both_fields(self) -> None:
        reports = _Reports()
        report(reports, pct=EXTRACT_START_PCT, message="Working")
        assert reports.payloads == [{"pct": EXTRACT_START_PCT, "message": "Working"}]

    def test_a_message_only_report_leaves_the_bar_alone(self) -> None:
        reports = _Reports()
        report(reports, pct=None, message="Working")
        assert reports.payloads == ["Working"]

    def test_no_listener_is_not_an_error(self) -> None:
        report(None, pct=EXTRACT_START_PCT, message="Working")


def _window(qapp) -> SimpleNamespace:
    del qapp
    return SimpleNamespace(
        _progress=QLabel(),
        _progress_bar=QProgressBar(),
        _btn_primary_left=QPushButton(),
        _btn_primary_right=QPushButton(),
        _btn_uninstall=QPushButton(),
        _licence_btn=QPushButton(),
        _theme_toggle_btn=QPushButton(),
        _install_dir_edit=QLineEdit(),
        _browse_btn=QPushButton(),
        _desktop_cb=QCheckBox(),
        _startmenu_cb=QCheckBox(),
    )


def test_busy_locks_the_browse_button_with_everything_else(qapp) -> None:
    # Browse used to stay enabled mid-install, inviting a directory change
    # while files were being replaced.
    window = _window(qapp)

    set_ui_busy(window, True)
    assert window._browse_btn.isEnabled() is False

    set_ui_busy(window, False)
    assert window._browse_btn.isEnabled() is True


class TestCompletionIsVisible:
    def test_completion_fills_the_bar_and_leaves_it_on_screen(self, qapp) -> None:
        window = _window(qapp)
        set_ui_busy(window, True)

        show_complete(window, message="Done")

        # The defect: the bar held the finished value while hidden. Releasing
        # the controls before filling it is what put it there, so the ordering
        # inside show_complete is the thing under test.
        assert window._progress_bar.value() == COMPLETE_PCT
        assert not window._progress_bar.isHidden()
        assert window._progress.text() == "Done"

    def test_releasing_the_controls_the_plain_way_still_hides_the_bar(
        self, qapp
    ) -> None:
        # Pins the discrimination in the test above: set_ui_busy(False) on its
        # own does hide the bar, which is exactly why completion must override.
        window = _window(qapp)
        set_ui_busy(window, True)

        set_ui_busy(window, False)

        assert window._progress_bar.isHidden()

    def test_completion_releases_the_controls(self, qapp) -> None:
        window = _window(qapp)
        set_ui_busy(window, True)
        assert not window._btn_uninstall.isEnabled()

        show_complete(window, message="Done")

        assert window._btn_uninstall.isEnabled()
        assert window._install_dir_edit.isEnabled()

    def test_clearing_retires_the_message_and_the_bar_together(self, qapp) -> None:
        window = _window(qapp)
        show_complete(window, message="Done")

        clear_progress_display(window)

        assert window._progress.text() == ""
        assert window._progress_bar.isHidden()


class TestApplyingReports:
    def test_a_percentage_payload_moves_the_bar(self, qapp) -> None:
        window = _window(qapp)

        on_progress(window, {"pct": 42, "message": "Extracting payload..."})

        assert window._progress_bar.value() == 42
        assert window._progress.text() == "Extracting payload..."

    def test_a_percentage_outside_the_range_is_clamped(self, qapp) -> None:
        window = _window(qapp)

        on_progress(window, {"pct": 500, "message": ""})
        assert window._progress_bar.value() == COMPLETE_PCT

        on_progress(window, {"pct": -20, "message": ""})
        assert window._progress_bar.value() == 0

    def test_a_bare_message_only_sets_the_text(self, qapp) -> None:
        window = _window(qapp)
        window._progress_bar.setValue(30)

        on_progress(window, "Registering uninstall entry...")

        assert window._progress.text() == "Registering uninstall entry..."
        assert window._progress_bar.value() == 30

    def test_an_unrecognised_payload_is_ignored(self, qapp) -> None:
        window = _window(qapp)
        window._progress.setText("unchanged")

        on_progress(window, None)
        on_progress(window, 17)

        assert window._progress.text() == "unchanged"
