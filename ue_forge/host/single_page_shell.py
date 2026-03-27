"""
Standalone shell for running a single tool page without the sidebar.

Used when building individual .exe files (e.g. Plugin Builder standalone).
Inherits :class:`FramelessWindow` and wraps a single page widget with
a simple title bar.
"""

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QPixmap, QIcon

from pyside_frameless import FramelessWindow
from ue_forge.shared.styles import COLORS, FONTS, get_main_stylesheet
from ue_forge.shared.icons import Icons
from ue_forge.shared.localization import tr
from ue_forge.shared.widgets import StatusBadge
from ue_forge.shared.dialogs import SettingsDialog


class SinglePageShell(FramelessWindow):
    """
    Frameless window hosting a single tool page (no sidebar).

    Usage::

        shell = SinglePageShell(PluginBuilderPage())
        shell.show()
    """

    def __init__(self, page: QWidget, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._page = page

        self._setup_window()
        self._setup_ui()

        # Connect status signal
        if hasattr(page, "status_changed"):
            page.status_changed.connect(self._on_status)

    def _setup_window(self) -> None:
        title = self._page.page_title() if hasattr(self._page, "page_title") else "UE Forge"
        self.setWindowTitle(title)
        self.setMinimumSize(1000, 600)
        self.resize(1100, 750)
        self.setStyleSheet(get_main_stylesheet())

        icon_path = self._get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

    def _get_icon_path(self) -> str:
        if getattr(sys, "frozen", False):
            base = Path(sys._MEIPASS)
            p = base / "ue_forge" / "shared" / "icon.png"
        else:
            p = Path(__file__).resolve().parent.parent / "shared" / "icon.png"
        return str(p) if p.exists() else ""

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = self._create_header()
        root.addWidget(header)
        root.addWidget(self._page, 1)

    def _create_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(40)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: none;
                border-bottom: 1px solid {COLORS['border_default']};
            }}
        """)
        self.set_title_bar_widget(header)

        lay = QHBoxLayout(header)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(10)

        # Icon
        icon_path = self._get_icon_path()
        logo = QLabel()
        if icon_path and Path(icon_path).exists():
            px = QPixmap(icon_path).scaled(
                24, 24,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo.setPixmap(px)
        else:
            logo.setPixmap(Icons.get_pixmap("ZAP", 20, COLORS["accent_primary"]))
        logo.setFixedSize(26, 26)
        logo.setStyleSheet("background: transparent;")
        lay.addWidget(logo)

        title_text = self._page.page_title() if hasattr(self._page, "page_title") else "UE Forge"
        title = QLabel(title_text)
        title.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: {FONTS['size_sm']};
            font-weight: 600;
        """)
        lay.addWidget(title)
        lay.addStretch()

        self._status_badge = StatusBadge(status="idle", text=tr("ready"))
        lay.addWidget(self._status_badge)

        # Settings
        settings_btn = QPushButton()
        settings_btn.setIcon(Icons.get_icon("SETTINGS", 16, COLORS["text_dim"]))
        settings_btn.setFixedSize(28, 28)
        settings_btn.setToolTip(tr("settings"))
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: 4px; padding: 6px;
            }}
            QPushButton:hover {{ background-color: {COLORS['bg_tertiary']}; }}
        """)
        settings_btn.clicked.connect(self._on_settings)
        lay.addWidget(settings_btn)

        lay.addSpacing(16)

        btn_style = f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: 4px; padding: 6px;
            }}
            QPushButton:hover {{ background-color: {COLORS['bg_tertiary']}; }}
        """
        close_style = f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: 4px; padding: 6px;
            }}
            QPushButton:hover {{ background-color: #ef4444; }}
        """

        min_btn = QPushButton()
        min_btn.setIcon(Icons.get_icon("MINUS", 14, COLORS["text_dim"]))
        min_btn.setFixedSize(32, 28)
        min_btn.setStyleSheet(btn_style)
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.clicked.connect(self.showMinimized)
        lay.addWidget(min_btn)

        self._max_btn = QPushButton()
        self._max_btn.setIcon(Icons.get_icon("SQUARE", 12, COLORS["text_dim"]))
        self._max_btn.setFixedSize(32, 28)
        self._max_btn.setStyleSheet(btn_style)
        self._max_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._max_btn.clicked.connect(self.toggle_maximize)
        lay.addWidget(self._max_btn)

        cls_btn = QPushButton()
        cls_btn.setIcon(Icons.get_icon("X", 14, COLORS["text_dim"]))
        cls_btn.setFixedSize(32, 28)
        cls_btn.setStyleSheet(close_style)
        cls_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cls_btn.clicked.connect(self.close)
        lay.addWidget(cls_btn)

        return header

    def on_maximize_changed(self, is_maximized: bool) -> None:
        icon = "MAXIMIZE_2" if is_maximized else "SQUARE"
        self._max_btn.setIcon(Icons.get_icon(icon, 12, COLORS["text_dim"]))

    def _on_settings(self) -> None:
        tabs = []
        if hasattr(self._page, "get_settings_tabs"):
            tabs = self._page.get_settings_tabs()
        SettingsDialog(self, extra_tabs=tabs).exec()

    def _on_status(self, badge: str, text: str) -> None:
        self._status_badge.set_status(badge, text)

    def closeEvent(self, event: QCloseEvent) -> None:
        if hasattr(self._page, "can_close") and not self._page.can_close():
            event.ignore()
            return
        if hasattr(self._page, "cleanup"):
            self._page.cleanup()
        event.accept()
