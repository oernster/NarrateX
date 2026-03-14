"""Installer operation errors."""

from __future__ import annotations


class InstallerOperationError(RuntimeError):
    pass


class AppRunningError(InstallerOperationError):
    """Raised when NarrateX is running and the operation requires it to be closed."""
