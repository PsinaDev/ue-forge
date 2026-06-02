"""
Shared data types used across framekit.
Pure Python — no Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LogLevel(Enum):
    """Log message severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class StatusKind(str, Enum):
    """
    Visual category of the status badge — drives colour and icon.

    The badge text is free-form and supplied by the page; this enum
    only fixes which visual style ``StatusBadge`` should render.
    """

    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class LogMessage:
    """Represents a single log message."""

    text: str
    level: LogLevel = LogLevel.INFO
    timestamp: str | None = None
