"""Widgets shipped with framekit."""

from .console_widget import ConsoleHighlighter, ConsoleWidget
from .path_input import PathInput
from .scrolling_label import ElidedLabel, ScrollingLabel
from .status_badge import StatusBadge

__all__ = [
    "ConsoleHighlighter",
    "ConsoleWidget",
    "ElidedLabel",
    "PathInput",
    "ScrollingLabel",
    "StatusBadge",
]
