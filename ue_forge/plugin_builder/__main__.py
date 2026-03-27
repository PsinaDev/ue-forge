"""
Standalone entry point for UE Forge.

Usage:
    python -m ue_forge.plugin_builder
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main() -> int:
    from ue_forge.shared.config import get_config_manager
    from ue_forge.shared.localization import set_language, detect_system_language

    config = get_config_manager().load_config()
    set_language(config.language or detect_system_language())

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont

    from ue_forge.host import SinglePageShell
    from ue_forge.plugin_builder.page import PluginBuilderPage

    app = QApplication([sys.argv[0]])
    app.setApplicationName("UE Forge")
    app.setOrganizationName("UEAutomation")

    font = QFont()
    if sys.platform == "win32":
        font.setFamily("Segoe UI")
    elif sys.platform == "darwin":
        font.setFamily("SF Pro")
    else:
        font.setFamily("Ubuntu")
    font.setPointSize(10)
    app.setFont(font)

    page = PluginBuilderPage()
    shell = SinglePageShell(page)
    shell.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
