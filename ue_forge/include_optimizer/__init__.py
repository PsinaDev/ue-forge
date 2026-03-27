"""
UE Forge — Include Optimizer module.

Optimizes Unreal Engine C++ source includes:
    - Adds missing ``UE_INLINE_GENERATED_CPP_BY_NAME`` macros.
    - Replaces ``CoreMinimal.h`` with specific headers.
    - Removes duplicate ``#include`` lines.
Can run standalone or as a page in the UE Forge host window.
"""

from . import strings  # noqa: F401 — register translations

from .core import (
    ChangeType,
    IncludeChange,
    IncludeAnalyzer,
    OptimizeScope,
    OptimizeResult,
    OptimizeStatus,
    PluginInfo,
    find_plugins,
)
from .page import IncludeOptimizerPage

__all__ = [
    "ChangeType",
    "IncludeChange",
    "IncludeAnalyzer",
    "OptimizeScope",
    "OptimizeResult",
    "OptimizeStatus",
    "PluginInfo",
    "find_plugins",
    "IncludeOptimizerPage",
]
