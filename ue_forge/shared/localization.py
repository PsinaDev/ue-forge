"""
Localization system for UE Forge.

Supports multiple languages with auto-detection, custom JSON locale files,
and per-module translation registration.

Shared (cross-module) strings live here. Each tool module registers
its own strings via ``register_translations()`` at import time.
"""
import json
import locale
from pathlib import Path
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Core translations — only strings used by shared/ components, host window,
# or referenced by two or more modules.
# ---------------------------------------------------------------------------

_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        # Host window / common status
        "app_title": "UE Forge",
        "host_title": "UE Forge",
        "coming_soon": "Coming Soon",
        "ready": "Ready",
        "building": "Building...",
        "success": "Success",
        "failed": "Failed",
        "cancelled": "Cancelled",

        # Common buttons / labels (shared dialogs, multiple modules)
        "yes": "Yes",
        "no": "No",
        "ok": "OK",
        "cancel": "Cancel",
        "browse": "Browse...",
        "add": "Add",
        "remove": "Remove",
        "close": "Close",
        "error": "Error",
        "settings": "Settings",
        "preview": "Preview",
        "description": "Description",
        "show_command": "Show Command",

        # Shared across renamer + include_optimizer
        "scope_backup": "Create backup before changes",

        # Shared across plugin_builder + renamer (drop zone / path input)
        "invalid_drop_file": "Invalid file or folder doesn't contain .uplugin",
        "path_to_plugin_file": "Path to plugin file...",

        # Console widget
        "console_output": "Console Output",
        "copied": "Copied!",
        "copy_tooltip": "Copy to clipboard",
        "clear_console": "Clear",
        "search_console": "Search (Ctrl+F)",
        "search_placeholder": "Search...",
        "no_matches": "No matches",
        "previous_match": "Previous (Shift+F3)",
        "next_match": "Next (F3)",

        # Combo copy easter egg
        "combo_copy_0": "Copied!",
        "combo_copy_1": "Double copy!",
        "combo_copy_2": "Triple copy!",
        "combo_copy_3": "Combo copy!",
        "combo_copy_4": "Mega copy!",
        "combo_copy_5": "Super copy!",
        "combo_copy_6": "Ultra copy!",
        "combo_copy_7": "GIGA COPY!!!",
        "combo_copy_8": "☆ LEGENDARY ☆",
        "combo_copy_9": "✦ DIVINE ✦",
        "combo_copy_10": "⚡ COSMIC ⚡",
        "combo_copy_11": "🔥 APOCALYPSE 🔥",
        "combo_post_0": "Maybe that's enough?",
        "combo_post_1": "Seriously, stop",
        "combo_post_2": "Last warning!",
        "combo_post_3": "Button will be taken away in...",
        "combo_button_gone": "Bye-bye button! 👋",

        # Language / settings dialog
        "language": "Language",
        "language_settings": "Language Settings",
        "select_language": "Select language",
        "load_custom_locale": "Load custom locale (JSON)",
        "no_custom_locale": "No custom locale loaded",
        "language_restart_note": "Note: Language change requires application restart.",
        "locale_loaded": "Locale loaded successfully",
        "locale_load_error": "Failed to load locale file",
        "restart_to_apply": "Please restart the application to apply the language change.",
    },

    "ru": {
        # Host window / common status
        "app_title": "UE Forge",
        "host_title": "UE Forge",
        "coming_soon": "Скоро",
        "ready": "Готово",
        "building": "Сборка...",
        "success": "Успех",
        "failed": "Провал",
        "cancelled": "Отменено",

        # Common buttons / labels
        "yes": "Да",
        "no": "Нет",
        "ok": "ОК",
        "cancel": "Отмена",
        "browse": "Обзор...",
        "add": "Добавить",
        "remove": "Удалить",
        "close": "Закрыть",
        "error": "Ошибка",
        "settings": "Настройки",
        "preview": "Предварительный просмотр",
        "description": "Описание",
        "show_command": "Команда",

        # Shared across renamer + include_optimizer
        "scope_backup": "Создать резервную копию",

        # Shared across plugin_builder + renamer
        "invalid_drop_file": "Неверный файл или папка не содержит .uplugin",
        "path_to_plugin_file": "Путь к файлу плагина...",

        # Console widget
        "console_output": "Консоль",
        "copied": "Скопировано!",
        "copy_tooltip": "Копировать в буфер обмена",
        "clear_console": "Очистить",
        "search_console": "Поиск (Ctrl+F)",
        "search_placeholder": "Поиск...",
        "no_matches": "Не найдено",
        "previous_match": "Предыдущий (Shift+F3)",
        "next_match": "Следующий (F3)",

        # Combo copy easter egg
        "combo_copy_0": "Скопировано!",
        "combo_copy_1": "Двойное копирование!",
        "combo_copy_2": "Тройное копирование!",
        "combo_copy_3": "Комбо копирование!",
        "combo_copy_4": "Мега копирование!",
        "combo_copy_5": "Супер копирование!",
        "combo_copy_6": "Ультра копирование!",
        "combo_copy_7": "ГИГА КОПИРОВАНИЕ!!!",
        "combo_copy_8": "☆ ЛЕГЕНДАРНОЕ ☆",
        "combo_copy_9": "✦ БОЖЕСТВЕННОЕ ✦",
        "combo_copy_10": "⚡ КОСМИЧЕСКОЕ ⚡",
        "combo_copy_11": "🔥 АПОКАЛИПСИС 🔥",
        "combo_post_0": "Может уже хватит?",
        "combo_post_1": "Серьёзно, прекрати",
        "combo_post_2": "Последнее предупреждение!",
        "combo_post_3": "Кнопка будет отобрана через...",
        "combo_button_gone": "Пока-пока, кнопка! 👋",

        # Language / settings dialog
        "language": "Язык",
        "language_settings": "Язык интерфейса",
        "select_language": "Выберите язык",
        "load_custom_locale": "Загрузить локализацию (JSON)",
        "no_custom_locale": "Локализация не загружена",
        "language_restart_note": "Примечание: Для смены языка требуется перезапуск приложения.",
        "locale_loaded": "Локализация загружена",
        "locale_load_error": "Ошибка загрузки локализации",
        "restart_to_apply": "Перезапустите приложение для применения изменений.",
    },
}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_current_lang: str = "en"
_custom_translations: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Module registration API
# ---------------------------------------------------------------------------

def register_translations(translations: Dict[str, Dict[str, str]]) -> None:
    """
    Register module-specific translations.

    Called by each tool module at import time to merge its strings
    into the global lookup table.

    Args:
        translations: ``{"en": {"key": "text", ...}, "ru": {...}}``
    """
    for lang, strings in translations.items():
        if lang not in _TRANSLATIONS:
            _TRANSLATIONS[lang] = {}
        _TRANSLATIONS[lang].update(strings)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_system_language() -> str:
    """Detect system language and return 'ru' if Russian, otherwise 'en'."""
    try:
        system_locale = locale.getdefaultlocale()[0]
        if system_locale and system_locale.lower().startswith("ru"):
            return "ru"
    except Exception:
        pass
    return "en"


def get_current_language() -> str:
    """Get current language code."""
    return _current_lang


def set_language(lang: str) -> None:
    """Set current language."""
    global _current_lang
    if lang in _TRANSLATIONS:
        _current_lang = lang
    else:
        _current_lang = "en"


def get_available_languages() -> Dict[str, str]:
    """Get available languages with their display names."""
    return {
        "en": "English",
        "ru": "Русский",
    }


def load_custom_locale(file_path: Path) -> bool:
    """
    Load custom locale from JSON file.

    Args:
        file_path: Path to JSON file with translations

    Returns:
        True if loaded successfully
    """
    global _custom_translations
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                _custom_translations = data
                return True
    except Exception:
        pass
    return False


def clear_custom_locale() -> None:
    """Clear custom locale."""
    global _custom_translations
    _custom_translations = {}


def tr(key: str, **kwargs) -> str:
    """
    Get translated string by key.

    Lookup order:
    1. Custom translations (loaded from JSON)
    2. Current language (shared + registered module strings)
    3. English fallback
    4. Raw key (if nothing found)

    Args:
        key: Translation key
        **kwargs: Format arguments

    Returns:
        Translated string
    """
    if key in _custom_translations:
        text = _custom_translations[key]
    elif key in _TRANSLATIONS.get(_current_lang, {}):
        text = _TRANSLATIONS[_current_lang][key]
    elif key in _TRANSLATIONS.get("en", {}):
        text = _TRANSLATIONS["en"][key]
    else:
        return key

    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text


def init_localization(saved_language: Optional[str] = None) -> None:
    """
    Initialize localization.

    Args:
        saved_language: Previously saved language from config, or None to auto-detect
    """
    global _current_lang
    if saved_language and saved_language in _TRANSLATIONS:
        _current_lang = saved_language
    else:
        _current_lang = detect_system_language()