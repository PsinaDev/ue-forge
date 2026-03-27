"""
UE Forge host window — sidebar navigation shell for multiple tool pages.
"""

from .host_window import HostWindow
from .single_page_shell import SinglePageShell
from .page_protocol import ToolPage

__all__ = ["HostWindow", "SinglePageShell", "ToolPage"]
