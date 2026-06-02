"""Resolve per-build resource paths (frozen PyInstaller or dev checkout)."""

from __future__ import annotations

import sys
from pathlib import Path


def _base_dir() -> Path:
    """Return the directory that holds bundled resources."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "ue_forge"
    return Path(__file__).resolve().parent


def icon_path() -> Path | None:
    """Return the ``icon.png`` path if the file exists, else None."""
    candidate = _base_dir() / "resources" / "icon.png"
    if candidate.exists():
        return candidate
    legacy = _base_dir() / "shared" / "icon.png"
    return legacy if legacy.exists() else None


def ico_path() -> Path | None:
    """Return the ``icon.ico`` path if the file exists, else None."""
    candidate = _base_dir() / "resources" / "icon.ico"
    if candidate.exists():
        return candidate
    legacy = _base_dir() / "shared" / "icon.ico"
    return legacy if legacy.exists() else None
