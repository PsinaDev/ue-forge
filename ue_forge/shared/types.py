"""
Shared data types used across all UE Forge modules.
Pure Python — no Qt dependencies.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class LogLevel(Enum):
    """Log message severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


@dataclass
class LogMessage:
    """Represents a single log message."""
    text: str
    level: LogLevel = LogLevel.INFO
    timestamp: Optional[str] = None
