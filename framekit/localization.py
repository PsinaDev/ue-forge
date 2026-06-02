"""
Localization system for framekit.

Supports multiple languages with auto-detection, custom JSON locale files,
and per-module translation registration.

Core (cross-module) strings live here. Each consumer module registers
its own strings via :func:`register_translations` at import time.
"""

from __future__ import annotations

import json
import locale
from pathlib import Path


# ---------------------------------------------------------------------------
# Core translations — strings used by framekit itself (shell, dialogs,
# widgets, localization UI). App-specific strings live in the app.
# ---------------------------------------------------------------------------

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # Common status text (used by default StatusBadge "Ready" label)
        "ready": "Ready",
        "success": "Success",
        "failed": "Failed",
        "cancelled": "Cancelled",

        # Common buttons / labels
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
        "combo_copy_8": "\u2606 LEGENDARY \u2606",
        "combo_copy_9": "\u2726 DIVINE \u2726",
        "combo_copy_10": "\u26a1 COSMIC \u26a1",
        "combo_copy_11": "\U0001f525 APOCALYPSE \U0001f525",
        "combo_post_0": "Maybe that's enough?",
        "combo_post_1": "Seriously, stop",
        "combo_post_2": "Last warning!",
        "combo_post_3": "Button will be taken away in...",
        "combo_button_gone": "Bye-bye button! \U0001f44b",

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
        "ready": "\u0413\u043e\u0442\u043e\u0432\u043e",
        "success": "\u0423\u0441\u043f\u0435\u0445",
        "failed": "\u041f\u0440\u043e\u0432\u0430\u043b",
        "cancelled": "\u041e\u0442\u043c\u0435\u043d\u0435\u043d\u043e",

        "yes": "\u0414\u0430",
        "no": "\u041d\u0435\u0442",
        "ok": "\u041e\u041a",
        "cancel": "\u041e\u0442\u043c\u0435\u043d\u0430",
        "browse": "\u041e\u0431\u0437\u043e\u0440...",
        "add": "\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c",
        "remove": "\u0423\u0434\u0430\u043b\u0438\u0442\u044c",
        "close": "\u0417\u0430\u043a\u0440\u044b\u0442\u044c",
        "error": "\u041e\u0448\u0438\u0431\u043a\u0430",
        "settings": "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438",
        "preview": "\u041f\u0440\u0435\u0434\u0432\u0430\u0440\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0439 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440",
        "description": "\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435",
        "show_command": "\u041a\u043e\u043c\u0430\u043d\u0434\u0430",

        "console_output": "\u041a\u043e\u043d\u0441\u043e\u043b\u044c",
        "copied": "\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u043e!",
        "copy_tooltip": "\u041a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0432 \u0431\u0443\u0444\u0435\u0440 \u043e\u0431\u043c\u0435\u043d\u0430",
        "clear_console": "\u041e\u0447\u0438\u0441\u0442\u0438\u0442\u044c",
        "search_console": "\u041f\u043e\u0438\u0441\u043a (Ctrl+F)",
        "search_placeholder": "\u041f\u043e\u0438\u0441\u043a...",
        "no_matches": "\u041d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e",
        "previous_match": "\u041f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0439 (Shift+F3)",
        "next_match": "\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 (F3)",

        "combo_copy_0": "\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u043e!",
        "combo_copy_1": "\u0414\u0432\u043e\u0439\u043d\u043e\u0435 \u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435!",
        "combo_copy_2": "\u0422\u0440\u043e\u0439\u043d\u043e\u0435 \u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435!",
        "combo_copy_3": "\u041a\u043e\u043c\u0431\u043e \u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435!",
        "combo_copy_4": "\u041c\u0435\u0433\u0430 \u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435!",
        "combo_copy_5": "\u0421\u0443\u043f\u0435\u0440 \u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435!",
        "combo_copy_6": "\u0423\u043b\u044c\u0442\u0440\u0430 \u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435!",
        "combo_copy_7": "\u0413\u0418\u0413\u0410 \u041a\u041e\u041f\u0418\u0420\u041e\u0412\u0410\u041d\u0418\u0415!!!",
        "combo_copy_8": "\u2606 \u041b\u0415\u0413\u0415\u041d\u0414\u0410\u0420\u041d\u041e\u0415 \u2606",
        "combo_copy_9": "\u2726 \u0411\u041e\u0416\u0415\u0421\u0422\u0412\u0415\u041d\u041d\u041e\u0415 \u2726",
        "combo_copy_10": "\u26a1 \u041a\u041e\u0421\u041c\u0418\u0427\u0415\u0421\u041a\u041e\u0415 \u26a1",
        "combo_copy_11": "\U0001f525 \u0410\u041f\u041e\u041a\u0410\u041b\u0418\u041f\u0421\u0418\u0421 \U0001f525",
        "combo_post_0": "\u041c\u043e\u0436\u0435\u0442 \u0443\u0436\u0435 \u0445\u0432\u0430\u0442\u0438\u0442?",
        "combo_post_1": "\u0421\u0435\u0440\u044c\u0451\u0437\u043d\u043e, \u043f\u0440\u0435\u043a\u0440\u0430\u0442\u0438",
        "combo_post_2": "\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u0435\u0435 \u043f\u0440\u0435\u0434\u0443\u043f\u0440\u0435\u0436\u0434\u0435\u043d\u0438\u0435!",
        "combo_post_3": "\u041a\u043d\u043e\u043f\u043a\u0430 \u0431\u0443\u0434\u0435\u0442 \u043e\u0442\u043e\u0431\u0440\u0430\u043d\u0430 \u0447\u0435\u0440\u0435\u0437...",
        "combo_button_gone": "\u041f\u043e\u043a\u0430-\u043f\u043e\u043a\u0430, \u043a\u043d\u043e\u043f\u043a\u0430! \U0001f44b",

        "language": "\u042f\u0437\u044b\u043a",
        "language_settings": "\u042f\u0437\u044b\u043a \u0438\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441\u0430",
        "select_language": "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u044f\u0437\u044b\u043a",
        "load_custom_locale": "\u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u043b\u043e\u043a\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044e (JSON)",
        "no_custom_locale": "\u041b\u043e\u043a\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f \u043d\u0435 \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u0430",
        "language_restart_note": "\u041f\u0440\u0438\u043c\u0435\u0447\u0430\u043d\u0438\u0435: \u0414\u043b\u044f \u0441\u043c\u0435\u043d\u044b \u044f\u0437\u044b\u043a\u0430 \u0442\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f \u043f\u0435\u0440\u0435\u0437\u0430\u043f\u0443\u0441\u043a \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f.",
        "locale_loaded": "\u041b\u043e\u043a\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u0430",
        "locale_load_error": "\u041e\u0448\u0438\u0431\u043a\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438 \u043b\u043e\u043a\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u0438",
        "restart_to_apply": "\u041f\u0435\u0440\u0435\u0437\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u0435 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0434\u043b\u044f \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u0438\u044f \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0439.",
    },
}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_current_lang: str = "en"
_custom_translations: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Module registration API
# ---------------------------------------------------------------------------

def register_translations(translations: dict[str, dict[str, str]]) -> None:
    """
    Register module-specific translations.

    Called by each app module at import time to merge its strings
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


def get_available_languages() -> dict[str, str]:
    """Get available languages with their display names."""
    return {
        "en": "English",
        "ru": "\u0420\u0443\u0441\u0441\u043a\u0438\u0439",
    }


def load_custom_locale(file_path: Path) -> bool:
    """
    Load custom locale from JSON file.

    Args:
        file_path: Path to JSON file with translations.

    Returns:
        True if loaded successfully.
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


def tr(key: str, **kwargs: object) -> str:
    """
    Get translated string by key.

    Lookup order:
        1. Custom translations (loaded from JSON).
        2. Current language (shared + registered module strings).
        3. English fallback.
        4. Raw key (if nothing found).
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


def init_localization(saved_language: str | None = None) -> None:
    """
    Initialize localization.

    Args:
        saved_language: Previously saved language from config, or None to auto-detect.
    """
    global _current_lang
    if saved_language and saved_language in _TRANSLATIONS:
        _current_lang = saved_language
    else:
        _current_lang = detect_system_language()
