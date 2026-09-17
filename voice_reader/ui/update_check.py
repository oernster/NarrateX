"""Update-check ui: run checks off the ui thread and prompt on the result.

The controller owns the check triggers (a delayed launch check, a daily
re-check while running and the About dialog's manual check) and runs each
check on a worker thread so the one network call can never stall the ui. The
result crosses back to the ui thread through a queued signal to a bound
method of this controller, which lives on the ui thread.

An automatic check that finds a newer release prompts with Download, Skip
This Version and Later; a skipped version is persisted through the injected
preferences repository and never prompts again. Automatic checks are silent
on failure and when up to date; only the manual check reports those outcomes.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QMessageBox

from voice_reader.ui.links import open_externally
from voice_reader.version import APP_NAME

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from voice_reader.domain.value_objects.update_info import UpdateStatus
    from voice_reader.application.services.update_service import UpdateService
    from voice_reader.domain.interfaces.preferences_repository import (
        PreferencesRepository,
    )

__all__ = ["UpdateCheckController"]

# Delay before the automatic launch check, so startup is never contended.
_LAUNCH_CHECK_DELAY_MS = 3000
# One re-check per day while the app stays running.
_CHECK_INTERVAL_HOURS = 24
_MS_PER_HOUR = 60 * 60 * 1000

# Prompt and announcement copy.
_PROMPT_TITLE = "Update available"
_PROMPT_BODY = "{app} {latest} is available.\nYou are running {current}."
_DOWNLOAD_LABEL = "Download"
_SKIP_LABEL = "Skip This Version"
_LATER_LABEL = "Later"
_MANUAL_TITLE = "Check for updates"
_UP_TO_DATE_BODY = "You are running the latest version."
_UNREACHABLE_BODY = "The update check could not reach GitHub. Please try again later."


class UpdateCheckController(QObject):
    """Runs update checks off the ui thread and prompts on the result."""

    # Emitted from the worker thread; delivery is queued onto the ui thread
    # because the connected slot is a bound method of this ui-thread QObject.
    _result_ready = Signal(object, bool)

    def __init__(
        self,
        service: UpdateService,
        preferences_repo: PreferencesRepository,
        parent: QWidget,
    ) -> None:
        # The composition-root tests drive app.main with a stubbed window that
        # is not a QObject; the controller then simply takes no Qt parent.
        super().__init__(parent if isinstance(parent, QObject) else None)
        self._service = service
        self._preferences_repo = preferences_repo
        self._parent_widget = parent
        self._result_ready.connect(self._on_result)
        QTimer.singleShot(_LAUNCH_CHECK_DELAY_MS, self.check_automatically)
        self._periodic_timer = QTimer(self)
        self._periodic_timer.setInterval(_CHECK_INTERVAL_HOURS * _MS_PER_HOUR)
        self._periodic_timer.timeout.connect(self.check_automatically)
        self._periodic_timer.start()

    def check_automatically(self) -> None:
        """Run a silent check honouring a previously skipped version."""
        self._start(manual=False)

    def check_manually(self) -> None:
        """Run a check that reports every outcome, ignoring any skip."""
        self._start(manual=True)

    def _start(self, manual: bool) -> None:
        skipped = None
        if not manual:
            skipped = self._preferences_repo.load_skipped_update_version()
        thread = threading.Thread(target=self._run, args=(skipped, manual), daemon=True)
        thread.start()

    def _run(self, skipped: str | None, manual: bool) -> None:
        self._result_ready.emit(self._service.check(skipped), manual)

    def _on_result(self, status: UpdateStatus, manual: bool) -> None:
        if status.update_available:
            self._prompt_update(status)
        elif manual:
            _announce_no_update(status, self._parent_widget)

    def _prompt_update(self, status: UpdateStatus) -> None:
        """Offer Download, Skip This Version and Later for a newer release."""
        box = QMessageBox(self._parent_widget)
        box.setWindowTitle(_PROMPT_TITLE)
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(
            _PROMPT_BODY.format(
                app=APP_NAME, latest=status.latest, current=status.current
            )
        )
        download = box.addButton(_DOWNLOAD_LABEL, QMessageBox.ButtonRole.AcceptRole)
        skip = box.addButton(_SKIP_LABEL, QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(_LATER_LABEL, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(download)
        box.exec()
        clicked = box.clickedButton()
        if clicked is download:
            url = status.download_url or status.page_url
            if url:
                open_externally(url)
        elif clicked is skip and status.latest:
            self._preferences_repo.save_skipped_update_version(status.latest)


def _announce_no_update(status: UpdateStatus, parent: QWidget) -> None:
    """Report a manual check that found nothing to offer."""
    body = _UP_TO_DATE_BODY if status.latest is not None else _UNREACHABLE_BODY
    QMessageBox.information(parent, _MANUAL_TITLE, body)


def install_update_check(*, window, preferences_repo, resolver, sys_platform):
    """Compose the update check for the composition root.

    ``resolver`` returns the wired classes by name (the entrypoint's ``_g``),
    so this helper adds no layer imports of its own and the choice of
    concrete adapter stays with the whitelisted composition root. The
    controller is attached to the window so the About dialog's button can
    reach its manual check.
    """
    from voice_reader.version import __version__

    service = resolver("UpdateService")(
        source=resolver("GitHubReleaseSource")(),
        current_version=__version__,
        platform_key=resolver("platform_key_for")(sys_platform),
    )
    controller = UpdateCheckController(service, preferences_repo, window)
    window.update_controller = controller
    return controller
