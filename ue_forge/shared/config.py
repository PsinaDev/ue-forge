"""
Configuration management for UE Forge.
Handles saving/loading engine paths and user preferences.
"""
import json
import os
from pathlib import Path
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field, asdict

from .platform_utils import platform_handler


CONFIG_FILENAME = "config.json"
ENGINES_FILENAME = "engines.json"


@dataclass
class AppConfig:
    """Application configuration settings."""
    language: str = "en"
    theme: str = "dark"
    last_plugin_path: str = ""
    last_output_path: str = ""
    output_mode: str = "parent"  # "parent" or "custom"
    default_platforms: list = field(default_factory=lambda: ["Win64"])
    window_geometry: Dict[str, int] = field(default_factory=dict)
    build_options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        return cls(
            language=data.get("language", "en"),
            theme=data.get("theme", "dark"),
            last_plugin_path=data.get("last_plugin_path", ""),
            last_output_path=data.get("last_output_path", ""),
            output_mode=data.get("output_mode", "parent"),
            default_platforms=data.get("default_platforms", ["Win64"]),
            window_geometry=data.get("window_geometry", {}),
            build_options=data.get("build_options", {}),
        )


class ConfigManager:
    """Manages application configuration and engine paths."""

    def __init__(self, config_dir: Optional[Path] = None):
        self._config_dir = config_dir or platform_handler().get_config_dir()
        self._config: Optional[AppConfig] = None
        self._engines: Dict[str, str] = {}
        self._on_change_callbacks: list[Callable[[], None]] = []
        
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @property
    def config_path(self) -> Path:
        return self._config_dir / CONFIG_FILENAME

    @property
    def engines_path(self) -> Path:
        return self._config_dir / ENGINES_FILENAME

    def add_change_callback(self, callback: Callable[[], None]) -> None:
        """Add a callback to be called when configuration changes."""
        self._on_change_callbacks.append(callback)

    def _notify_change(self) -> None:
        """Notify all registered callbacks of a configuration change."""
        for callback in self._on_change_callbacks:
            try:
                callback()
            except Exception:
                pass

    def load_config(self) -> AppConfig:
        """Load application configuration from file."""
        if self._config is not None:
            return self._config

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._config = AppConfig.from_dict(data)
            except (json.JSONDecodeError, IOError, KeyError):
                self._config = AppConfig()
        else:
            self._config = AppConfig()

        return self._config

    def save_config(self, config: Optional[AppConfig] = None) -> bool:
        """Save application configuration to file."""
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

    def update_config(self, **kwargs) -> bool:
        """Update specific configuration values."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return self.save_config(config)

    def load_engines(self) -> Dict[str, str]:
        """Load engine paths from file."""
        if self._engines:
            return self._engines.copy()

        if self.engines_path.exists():
            try:
                with open(self.engines_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._engines = data.get("engines", {})
            except (json.JSONDecodeError, IOError):
                self._engines = {}
        else:
            self._engines = {}

        return self._engines.copy()

    def save_engines(self, engines: Dict[str, str]) -> bool:
        """Save engine paths to file."""
        self._engines = engines.copy()
        try:
            with open(self.engines_path, "w", encoding="utf-8") as f:
                json.dump({"engines": engines}, f, indent=2)
            self._notify_change()
            return True
        except (IOError, OSError):
            return False

    def add_engine(self, version: str, path: str) -> bool:
        """Add a single engine to the configuration."""
        engines = self.load_engines()
        engines[version] = path
        return self.save_engines(engines)

    def remove_engine(self, version: str) -> bool:
        """Remove an engine from the configuration."""
        engines = self.load_engines()
        if version in engines:
            del engines[version]
            return self.save_engines(engines)
        return False

    def clear_engines(self) -> bool:
        """Clear all saved engines."""
        self._engines = {}
        return self.save_engines({})

    def get_engine_path(self, version: str) -> Optional[str]:
        """Get path for a specific engine version."""
        engines = self.load_engines()
        return engines.get(version)

    # ------------------------------------------------------------------
    # Commandlet favorites
    # ------------------------------------------------------------------

    @property
    def favorites_path(self) -> Path:
        return self._config_dir / "commandlet_favorites.json"

    def load_favorites(self) -> set[str]:
        """Load favorited commandlet names."""
        if self.favorites_path.exists():
            try:
                with open(self.favorites_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return set(data.get("favorites", []))
            except (json.JSONDecodeError, IOError):
                pass
        return set()

    def save_favorites(self, favorites: set[str]) -> bool:
        """Save favorited commandlet names."""
        self._ensure_config_dir()
        try:
            with open(self.favorites_path, "w", encoding="utf-8") as f:
                json.dump({"favorites": sorted(favorites)}, f, indent=2)
            return True
        except (IOError, OSError):
            return False

    def toggle_favorite(self, name: str) -> bool:
        """Toggle a commandlet's favorite status. Returns new state."""
        favs = self.load_favorites()
        if name in favs:
            favs.discard(name)
            is_fav = False
        else:
            favs.add(name)
            is_fav = True
        self.save_favorites(favs)
        return is_fav

    # ------------------------------------------------------------------
    # Commandlet notes
    # ------------------------------------------------------------------

    @property
    def notes_path(self) -> Path:
        return self._config_dir / "commandlet_notes.json"

    def load_notes(self) -> Dict[str, str]:
        """Load user notes for commandlets. Returns {name: note_text}."""
        if self.notes_path.exists():
            try:
                with open(self.notes_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("notes", {})
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def save_note(self, name: str, text: str) -> bool:
        """Save a note for a commandlet. Empty text deletes the note."""
        self._ensure_config_dir()
        notes = self.load_notes()
        text = text.strip()
        if text:
            notes[name] = text
        else:
            notes.pop(name, None)
        try:
            with open(self.notes_path, "w", encoding="utf-8") as f:
                json.dump({"notes": notes}, f, indent=2, ensure_ascii=False)
            return True
        except (IOError, OSError):
            return False

    def get_note(self, name: str) -> str:
        """Get note for a commandlet."""
        return self.load_notes().get(name, "")


# Global instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
