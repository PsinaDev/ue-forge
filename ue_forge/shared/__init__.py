"""
UE Forge — shared infrastructure.

Styles, icons, localization, config, platform utilities,
and common widgets used by all tool modules.
"""

from .types import LogLevel, LogMessage
from .localization import (
    tr,
    get_current_language,
    set_language,
    get_available_languages,
    load_custom_locale,
    clear_custom_locale,
    init_localization,
    detect_system_language,
)
from .config import AppConfig, ConfigManager, get_config_manager
from .platform_utils import get_platform, platform_handler, PlatformHandler
from .styles import COLORS, FONTS, RADIUS, SPACING, get_main_stylesheet
from .icons import Icons, get_indicator_icon_path

__all__ = [
    # Types
    "LogLevel",
    "LogMessage",
    # Localization
    "tr",
    "get_current_language",
    "set_language",
    "get_available_languages",
    "load_custom_locale",
    "clear_custom_locale",
    "init_localization",
    "detect_system_language",
    # Config
    "AppConfig",
    "ConfigManager",
    "get_config_manager",
    # Platform
    "get_platform",
    "platform_handler",
    "PlatformHandler",
    # Styles
    "COLORS",
    "FONTS",
    "RADIUS",
    "SPACING",
    "get_main_stylesheet",
    # Icons
    "Icons",
    "get_indicator_icon_path",
]
