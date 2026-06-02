"""
Bootstrap helpers for framekit-based applications.

Collapses the per-app ``__main__.py`` boilerplate (QApplication,
font selection, platform handler, config manager, shell wiring)
down to a single call.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget

from framekit.config import ConfigManager, get_config_manager, set_config_manager
from framekit.localization import detect_system_language, set_language
from framekit.platform import (
    PlatformHandler,
    default_handler_for,
    set_platform_handler,
)
from framekit.shell import HostWindow, SinglePageShell


def _platform_font_family() -> str:
    if sys.platform == "win32":
        return "Segoe UI"
    if sys.platform == "darwin":
        return "SF Pro"
    return "Ubuntu"


def _build_qapp(
    app_name: str,
    org_name: str,
    font_family: str | None,
    font_size: int,
) -> QApplication:
    app = QApplication([sys.argv[0]])
    app.setApplicationName(app_name)
    app.setOrganizationName(org_name)

    font = QFont()
    font.setFamily(font_family or _platform_font_family())
    font.setPointSize(font_size)
    app.setFont(font)
    return app


def _bootstrap_state(
    app_slug: str,
    platform_handler: PlatformHandler | None,
    config_manager: ConfigManager | None,
) -> None:
    """Install platform handler and config manager singletons."""
    set_platform_handler(platform_handler or default_handler_for(app_slug))
    set_config_manager(config_manager or ConfigManager())

    cfg = get_config_manager().load_config()
    set_language(cfg.language or detect_system_language())


def run_standalone(
    page_factory: Callable[[], QWidget],
    *,
    app_name: str,
    org_name: str,
    app_slug: str,
    window_title: str | None = None,
    icon_path: Path | None = None,
    platform_handler: PlatformHandler | None = None,
    config_manager: ConfigManager | None = None,
    font_family: str | None = None,
    font_size: int = 10,
) -> int:
    """
    Boot a standalone single-page application.

    Args:
        page_factory: Callable producing the page widget. Called after
            state bootstrap so ``tr()`` / ``get_config_manager()`` work
            inside the page constructor.
        app_name: Human-readable app name (QApplication metadata).
        org_name: Organization name (QApplication metadata).
        app_slug: Slug used for the per-user config directory.
        window_title: Title shown in the frameless header. Defaults to ``app_name``.
        icon_path: Path to the window / title-bar icon (optional).
        platform_handler: Override the default per-OS handler.
        config_manager: Override the default :class:`ConfigManager`.
        font_family: Override the default per-OS font family.
        font_size: Point size for the application font.

    Returns:
        QApplication exit code.
    """
    app = _build_qapp(app_name, org_name, font_family, font_size)
    _bootstrap_state(app_slug, platform_handler, config_manager)

    page = page_factory()
    shell = SinglePageShell(
        page=page,
        title=window_title or app_name,
        icon_path=icon_path,
    )
    shell.show()
    return app.exec()


def run_host(
    page_factories: list[Callable[[], QWidget]],
    *,
    app_name: str,
    org_name: str,
    app_slug: str,
    window_title: str | None = None,
    icon_path: Path | None = None,
    platform_handler: PlatformHandler | None = None,
    config_manager: ConfigManager | None = None,
    font_family: str | None = None,
    font_size: int = 10,
    app_version: str | None = None,
) -> int:
    """
    Boot a multi-page host application.

    Args:
        page_factories: Callables producing each page widget, in sidebar order.
        app_name: Human-readable app name (QApplication metadata).
        org_name: Organization name (QApplication metadata).
        app_slug: Slug used for the per-user config directory.
        window_title: Title shown in the frameless header. Defaults to ``app_name``.
        icon_path: Path to the window / title-bar icon (optional).
        platform_handler: Override the default per-OS handler.
        config_manager: Override the default :class:`ConfigManager`.
        font_family: Override the default per-OS font family.
        font_size: Point size for the application font.
        app_version: Optional QApplication version string.

    Returns:
        QApplication exit code.
    """
    app = _build_qapp(app_name, org_name, font_family, font_size)
    if app_version:
        app.setApplicationVersion(app_version)
    _bootstrap_state(app_slug, platform_handler, config_manager)

    host = HostWindow(title=window_title or app_name, icon_path=icon_path)
    for factory in page_factories:
        host.add_page(factory())
    host.show()
    return app.exec()
