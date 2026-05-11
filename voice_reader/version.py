"""Application identity and version.

Keep app identity in one place so the runtime UI, About dialog, logging, and
packaging metadata stay consistent.
"""

from __future__ import annotations

APP_NAME: str = "NarrateX"
APP_AUTHOR: str = "Oliver Ernster"
APP_COPYRIGHT: str = "© 2026 Oliver Ernster"

# Windows taskbar grouping / pinned icon identity.
#
# This should be stable over time; changing it can cause Windows to treat newer
# builds as a different app (separate taskbar grouping / pinned item).
APP_APPUSERMODELID: str = "com.oliverernster.narratex"

__version__: str = "2.6.2"
