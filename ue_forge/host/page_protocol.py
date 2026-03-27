"""
Protocol that every tool page must implement.

Both the multi-page HostWindow and the standalone SinglePageShell
interact with pages through this interface.
"""

from typing import List, Protocol, runtime_checkable

from PySide6.QtCore import Signal

from ue_forge.shared.dialogs.settings_dialog import SettingsTab


@runtime_checkable
class ToolPage(Protocol):
    """
    Interface for a tool page widget.

    Class-level constants (set as class attributes):
        PAGE_ID:   str  — unique slug, e.g. ``"plugin_builder"``
        PAGE_ICON: str  — icon name from :class:`Icons`, e.g. ``"HAMMER"``

    Signals:
        status_changed(str, str)  — (badge_status, text)
    """

    PAGE_ID: str
    PAGE_ICON: str
    status_changed: Signal

    def page_title(self) -> str:
        """Localised display title for sidebar / title bar."""
        ...

    def get_settings_tabs(self) -> List[SettingsTab]:
        """Return extra settings tabs contributed by this page."""
        ...

    def can_close(self) -> bool:
        """Return False to block window close (e.g. active build)."""
        ...

    def cleanup(self) -> None:
        """Release resources when the window is closing."""
        ...
