"""
Configuration management for framekit.

Provides a minimal base ``AppConfig`` (language, theme, window geometry)
and a ``ConfigManager`` that persists it as JSON in the platform config
directory. Apps extend by subclassing ``AppConfig`` and injecting a
custom manager via :func:`set_config_manager`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar

from .platform import platform_handler


CONFIG_FILENAME = "config.json"


@dataclass
class AppConfig:
    """Base application configuration."""

    language: str = "en"
    theme: str = "dark"
    window_geometry: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls(
            language=data.get("language", "en"),
            theme=data.get("theme", "dark"),
            window_geometry=data.get("window_geometry", {}),
        )


class ConfigManager:
    """
    JSON-backed configuration manager.

    Generic over a concrete config class that must implement
    ``to_dict`` / ``from_dict``. Subclasses may add domain-specific
    persistence (engine paths, favourites, etc.) on top.
    """

    CONFIG_CLASS: ClassVar[type[AppConfig]] = AppConfig

    def __init__(
        self,
        config_dir: Path | None = None,
        config_class: type[AppConfig] | None = None,
    ):
        self._explicit_config_dir: Path | None = config_dir
        self._resolved_config_dir: Path | None = None
        self._config_class: type[AppConfig] = config_class or type(self).CONFIG_CLASS
        self._config: AppConfig | None = None
        self._on_change_callbacks: list[Callable[[], None]] = []

    # -- properties -----------------------------------------------------

    @property
    def _config_dir(self) -> Path:
        """
        Resolve the config directory lazily.

        Deferred so that ``ConfigManager`` (and its subclasses) can be
        constructed before a :class:`PlatformHandler` has been installed —
        as happens when an instance is passed into ``run_host`` /
        ``run_standalone`` via keyword argument.
        """
        if self._resolved_config_dir is None:
            if self._explicit_config_dir is not None:
                self._resolved_config_dir = self._explicit_config_dir
            else:
                self._resolved_config_dir = platform_handler().get_config_dir()
            self._resolved_config_dir.mkdir(parents=True, exist_ok=True)
        return self._resolved_config_dir

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @property
    def config_path(self) -> Path:
        return self._config_dir / CONFIG_FILENAME

    # -- change notification -------------------------------------------

    def add_change_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked after every successful save."""
        self._on_change_callbacks.append(callback)

    def _notify_change(self) -> None:
        for callback in self._on_change_callbacks:
            try:
                callback()
            except Exception:
                pass

    # -- config persistence --------------------------------------------

    def load_config(self) -> AppConfig:
        """Load configuration from disk, cached after first call."""
        if self._config is not None:
            return self._config

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._config = self._config_class.from_dict(data)
            except (json.JSONDecodeError, IOError, KeyError):
                self._config = self._config_class()
        else:
            self._config = self._config_class()

        return self._config

    def save_config(self, config: AppConfig | None = None) -> bool:
        """Write configuration to disk. Returns True on success."""
        if config is not None:
            self._config = config
        if self._config is None:
            return False

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
            self._notify_change()
            return True
        except (IOError, OSError):
            return False

    def update_config(self, **kwargs: Any) -> bool:
        """Update specific configuration fields and save."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return self.save_config(config)

    # -- internals -----------------------------------------------------

    def _ensure_config_dir(self) -> None:
        """Force lazy resolution of ``_config_dir`` (creates the dir if missing)."""
        _ = self._config_dir


# ---------------------------------------------------------------------------
# Injectable singleton
# ---------------------------------------------------------------------------

_config_manager: ConfigManager | None = None


def set_config_manager(manager: ConfigManager) -> None:
    """Install the global configuration manager instance."""
    global _config_manager
    _config_manager = manager


def get_config_manager() -> ConfigManager:
    """
    Return the global configuration manager instance.

    Raises:
        RuntimeError: if no manager has been installed via
            :func:`set_config_manager`.
    """
    if _config_manager is None:
        raise RuntimeError(
            "get_config_manager() called before set_config_manager(); "
            "install a manager at app startup"
        )
    return _config_manager
