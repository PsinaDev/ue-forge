"""
Protocol that every tool page must implement.

Both the multi-page :class:`HostWindow` and the standalone
:class:`SinglePageShell` interact with pages through this interface.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PySide6.QtCore import Signal

from framekit.dialogs import SettingsTab


@runtime_checkable
class ToolPage(Protocol):
    """
    Interface for a tool page widget.

    Class-level attributes:
        PAGE_ID:   Unique slug (e.g. ``"plugin_builder"``).
        PAGE_ICON: Icon name from :class:`framekit.icons.Icons`.

    Signals:
        status_changed(StatusKind, str): ``(visual_category, free_text)``.
    """

    PAGE_ID: str
    PAGE_ICON: str
    status_changed: Signal

    def page_title(self) -> str:
        """Localised display title for sidebar / title bar."""
        ...

    def get_settings_tabs(self) -> list[SettingsTab]:
        """Return extra settings tabs contributed by this page."""
        ...

    def can_close(self) -> bool:
        """Return False to block window close (e.g. active build)."""
        ...

    def cleanup(self) -> None:
        """Release resources when the window is closing."""
        ...
