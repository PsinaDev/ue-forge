"""
UE Forge — Renamer module.

Rename Unreal Engine plugins (.uplugin) and projects (.uproject):
JSON files, .Build.cs, source code, config files, and more.
Can run standalone or as a page in the UE Forge host window.
"""

from . import strings  # noqa: F401 — register translations

from .core import (
    RenameStatus,
    ChangeType,
    RenameChange,
    RenameScope,
    RenameResult,
    PluginRenamer,
    ProjectRenamer,
)
from .page import RenamerPage

__all__ = [
    "RenameStatus",
    "ChangeType",
    "RenameChange",
    "RenameScope",
    "RenameResult",
    "PluginRenamer",
    "ProjectRenamer",
    "RenamerPage",
]
