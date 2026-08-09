"""Domain interface for the update check's release source.

The concrete implementation lives in infrastructure and queries the project's
GitHub releases; the application reads the latest release only through this
interface, so it never depends on the network or on GitHub's payload shape.
Only a published release is ever reported: the endpoint the adapter queries
excludes drafts, prereleases and bare tags, so a tag pushed mid-development
can never raise an update prompt.
"""

from __future__ import annotations

from typing import Protocol

from voice_reader.domain.value_objects.update_info import ReleaseInfo


class ReleaseSource(Protocol):
    """A source of the latest published release."""

    def latest_release(self) -> ReleaseInfo | None:
        """Return the latest published release or None if unreachable."""
