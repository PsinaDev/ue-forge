"""
Platform-specific utilities for framekit.

Provides a minimal cross-platform abstraction: per-user config directory
resolution and process-tree termination. Consumers may subclass to add
their own domain methods (e.g. engine discovery).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path


def get_platform() -> str:
    """Get current platform identifier: 'windows', 'macos', or 'linux'."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


class PlatformHandler(ABC):
    """
    Abstract base class for platform-specific operations.

    Subclasses provide per-OS config directory resolution and process
    termination. Apps may further subclass to add domain utilities.
    """

    def __init__(self, app_slug: str):
        if not app_slug:
            raise ValueError("app_slug must be a non-empty string")
        self._app_slug = app_slug

    @property
    def app_slug(self) -> str:
        """Application slug used for config directory naming."""
        return self._app_slug

    @abstractmethod
    def get_config_dir(self) -> Path:
        """Return the per-user config directory for this app."""

    @abstractmethod
    def kill_process_tree(self, pid: int) -> bool:
        """Kill a process and all its children. Return True on success."""


class WindowsHandler(PlatformHandler):
    """Windows-specific platform handler."""

    def get_config_dir(self) -> Path:
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            return Path(local_appdata) / self._app_slug
        return Path.home() / "AppData" / "Local" / self._app_slug

    def kill_process_tree(self, pid: int) -> bool:
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid), "/T"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=creation_flags,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False


class LinuxHandler(PlatformHandler):
    """Linux-specific platform handler."""

    def get_config_dir(self) -> Path:
        xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
        if xdg_config:
            return Path(xdg_config) / self._app_slug
        return Path.home() / ".config" / self._app_slug

    def kill_process_tree(self, pid: int) -> bool:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(pid, signal.SIGKILL)
                return True
            except (ProcessLookupError, PermissionError, OSError):
                return False


class MacOSHandler(PlatformHandler):
    """macOS-specific platform handler."""

    def get_config_dir(self) -> Path:
        return Path.home() / "Library" / "Application Support" / self._app_slug

    def kill_process_tree(self, pid: int) -> bool:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(pid, signal.SIGKILL)
                return True
            except (ProcessLookupError, PermissionError, OSError):
                return False


# ---------------------------------------------------------------------------
# Injectable singleton
# ---------------------------------------------------------------------------

_handler: PlatformHandler | None = None


def set_platform_handler(handler: PlatformHandler) -> None:
    """Install the global platform handler instance."""
    global _handler
    _handler = handler


def platform_handler() -> PlatformHandler:
    """
    Return the global platform handler instance.

    Raises:
        RuntimeError: if no handler has been installed via
            :func:`set_platform_handler`.
    """
    if _handler is None:
        raise RuntimeError(
            "platform_handler() called before set_platform_handler(); "
            "install a handler at app startup"
        )
    return _handler


def default_handler_for(app_slug: str) -> PlatformHandler:
    """Build the default per-OS handler bound to ``app_slug``."""
    platform = get_platform()
    if platform == "windows":
        return WindowsHandler(app_slug)
    if platform == "macos":
        return MacOSHandler(app_slug)
    return LinuxHandler(app_slug)
