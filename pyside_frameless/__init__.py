"""
PySide6 Frameless Window Library.

Provides a production-ready frameless QMainWindow with:
- Windows Aero Snap support (WM_NCHITTEST / WM_NCCALCSIZE)
- DPI-aware resize handling
- Custom title bar with double-click maximize
- Cross-platform fallback resize (mouse events)
- Animated drag-and-drop overlay and drop zone widget

No application-specific dependencies — reusable across any PySide6 project.
"""

from .frameless_window import FramelessWindow
from .drop_overlay import DropOverlay, DropZoneWidget

__all__ = [
    "FramelessWindow",
    "DropOverlay",
    "DropZoneWidget",
]
