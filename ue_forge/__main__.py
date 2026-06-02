"""
Combined UE Forge entry point — all modules in one window.

Usage:
    python -m ue_forge
"""

from __future__ import annotations

import logging
import sys

from framekit import run_host

from ue_forge import APP_NAME, APP_ORG, APP_SLUG, __version__
from ue_forge.assets import icon_path
from ue_forge.config import UEForgeConfigManager
from ue_forge.platform import ue_handler_for


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main() -> int:
    from ue_forge.commandlet_runner import CommandletRunnerPage
    from ue_forge.include_optimizer import IncludeOptimizerPage
    from ue_forge.plugin_builder import PluginBuilderPage
    from ue_forge.renamer import RenamerPage

    page_factories = [
        PluginBuilderPage,
        RenamerPage,
        IncludeOptimizerPage,
        CommandletRunnerPage,
    ]

    # Optional private pages. ue_forge/private/ is a git-ignored package present
    # only on the maintainer's machine; it self-discovers its own pages. In a
    # public build the import fails and the app runs with the public tools alone.
    try:
        from ue_forge.private import get_pages
    except ImportError:
        get_pages = None

    try:
        if get_pages is not None:
            page_factories.extend(get_pages())
        return run_host(
            page_factories=page_factories,
            app_name=APP_NAME,
            org_name=APP_ORG,
            app_slug=APP_SLUG,
            icon_path=icon_path(),
            platform_handler=ue_handler_for(APP_SLUG),
            config_manager=UEForgeConfigManager(),
            app_version=__version__,
        )
    except Exception as e:
        logger.exception("Application error: %s", e)
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(
            None, "Application Error",
            f"An unexpected error occurred:\n\n{e}",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
