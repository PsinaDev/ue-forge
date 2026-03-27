"""
Combined UE Forge entry point — all modules in one window.

Usage:
    python -m ue_forge
"""

import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    from ue_forge.shared.config import get_config_manager
    from ue_forge.shared.localization import set_language, detect_system_language

    config = get_config_manager().load_config()
    set_language(config.language or detect_system_language())

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont

    from ue_forge.host import HostWindow
    from ue_forge.plugin_builder import PluginBuilderPage
    from ue_forge.renamer import RenamerPage
    from ue_forge.include_optimizer import IncludeOptimizerPage
    from ue_forge.commandlet_runner import CommandletRunnerPage

    app = QApplication([sys.argv[0]])
    app.setApplicationName("UE Forge")
    app.setApplicationVersion("2.0.0")
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

    try:
        window = HostWindow()

        builder_page = PluginBuilderPage()
        window.add_page(builder_page)

        renamer_page = RenamerPage()
        window.add_page(renamer_page)

        optimizer_page = IncludeOptimizerPage()
        window.add_page(optimizer_page)

        commandlet_page = CommandletRunnerPage()
        window.add_page(commandlet_page)

        window.show()

        logger.info("UE Forge started")
        return app.exec()

    except Exception as e:
        logger.exception(f"Application error: {e}")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None, "Application Error",
            f"An unexpected error occurred:\n\n{e}",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
