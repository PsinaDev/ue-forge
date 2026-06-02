"""
Standalone entry point for the UE Renamer.

Usage:
    python -m ue_forge.renamer
"""

from __future__ import annotations

import logging
import sys

from framekit import run_standalone

from ue_forge import APP_ORG, APP_SLUG
from ue_forge.assets import icon_path
from ue_forge.config import UEForgeConfigManager
from ue_forge.platform import ue_handler_for


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main() -> int:
    from ue_forge.renamer.page import RenamerPage

    return run_standalone(
        page_factory=RenamerPage,
        app_name="UE Renamer",
        org_name=APP_ORG,
        app_slug=APP_SLUG,
        icon_path=icon_path(),
        platform_handler=ue_handler_for(APP_SLUG),
        config_manager=UEForgeConfigManager(),
    )


if __name__ == "__main__":
    sys.exit(main())
