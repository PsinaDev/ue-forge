"""
UE Forge-specific configuration: extends the framekit base with
plugin paths, build options, engine registry, commandlet favourites,
and commandlet notes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, cast

from framekit.config import AppConfig, ConfigManager, get_config_manager


ENGINES_FILENAME = "engines.json"
FAVORITES_FILENAME = "commandlet_favorites.json"
NOTES_FILENAME = "commandlet_notes.json"


@dataclass
class UEForgeConfig(AppConfig):
    """Application configuration for UE Forge."""

    last_plugin_path: str = ""
    last_output_path: str = ""
    output_mode: str = "parent"
    default_platforms: list[str] = field(default_factory=lambda: ["Win64"])
    build_options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UEForgeConfig":
        return cls(
            language=data.get("language", "en"),
            theme=data.get("theme", "dark"),
            window_geometry=data.get("window_geometry", {}),
            last_plugin_path=data.get("last_plugin_path", ""),
            last_output_path=data.get("last_output_path", ""),
            output_mode=data.get("output_mode", "parent"),
            default_platforms=data.get("default_platforms", ["Win64"]),
            build_options=data.get("build_options", {}),
        )


class UEForgeConfigManager(ConfigManager):
    """Config manager with UE-specific auxiliary stores."""

    CONFIG_CLASS: ClassVar[type[AppConfig]] = UEForgeConfig

    def __init__(self, config_dir: Path | None = None):
        super().__init__(config_dir=config_dir, config_class=UEForgeConfig)
        self._engines: dict[str, str] = {}

    # -- engines --------------------------------------------------------

    @property
    def engines_path(self) -> Path:
        return self._config_dir / ENGINES_FILENAME

    def load_engines(self) -> dict[str, str]:
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

    def save_engines(self, engines: dict[str, str]) -> bool:
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

    def get_engine_path(self, version: str) -> str | None:
        """Get path for a specific engine version."""
        return self.load_engines().get(version)

    # -- commandlet favourites -----------------------------------------

    @property
    def favorites_path(self) -> Path:
        return self._config_dir / FAVORITES_FILENAME

    def load_favorites(self) -> set[str]:
        """Load favourited commandlet names."""
        if self.favorites_path.exists():
            try:
                with open(self.favorites_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return set(data.get("favorites", []))
            except (json.JSONDecodeError, IOError):
                pass
        return set()

    def save_favorites(self, favorites: set[str]) -> bool:
        """Save favourited commandlet names."""
        self._ensure_config_dir()
        try:
            with open(self.favorites_path, "w", encoding="utf-8") as f:
                json.dump({"favorites": sorted(favorites)}, f, indent=2)
            return True
        except (IOError, OSError):
            return False

    def toggle_favorite(self, name: str) -> bool:
        """Toggle a commandlet's favourite status. Returns the new state."""
        favs = self.load_favorites()
        if name in favs:
            favs.discard(name)
            is_fav = False
        else:
            favs.add(name)
            is_fav = True
        self.save_favorites(favs)
        return is_fav

    # -- commandlet notes ----------------------------------------------

    @property
    def notes_path(self) -> Path:
        return self._config_dir / NOTES_FILENAME

    def load_notes(self) -> dict[str, str]:
        """Load user notes for commandlets: ``{name: note_text}``."""
        if self.notes_path.exists():
            try:
                with open(self.notes_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("notes", {})
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def save_note(self, name: str, text: str) -> bool:
        """Save a note for a commandlet. Empty text deletes the entry."""
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


def get_ue_config_manager() -> UEForgeConfigManager:
    """Return the global config manager, typed as ``UEForgeConfigManager``."""
    return cast(UEForgeConfigManager, get_config_manager())
