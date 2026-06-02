"""
Standalone shell for running a single tool page without a sidebar.

Used when building an individual tool into its own standalone executable.
Inherits :class:`pyside_frameless.FramelessWindow` and wraps a single
page widget with a simple title bar.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyside_frameless import FramelessWindow

from framekit.dialogs import SettingsDialog
from framekit.icons import Icons
from framekit.localization import tr
from framekit.styles import COLORS, FONTS, get_main_stylesheet
from framekit.types import StatusKind
from framekit.widgets import StatusBadge


class SinglePageShell(FramelessWindow):
    """
    Frameless window hosting a single tool page (no sidebar).

    Usage::

        shell = SinglePageShell(
            page=MyPage(),
            title="My App",
            icon_path=Path("icons/my_app.png"),
        )
        shell.show()
    """

    def __init__(
        self,
        page: QWidget,
        title: str,
        icon_path: Path | None = None,
        parent: QWidget | None = None,
        min_width: int = 1000,
        min_height: int = 600,
        width: int = 1100,
        height: int = 750,
    ):
        super().__init__(parent)
        self._page = page
        self._title = title
        self._icon_path = icon_path

        self._setup_window(min_width, min_height, width, height)
        self._setup_ui()

        if hasattr(page, "status_changed"):
            page.status_changed.connect(self._on_status)

    # -- Qt overrides ---------------------------------------------------

    def on_maximize_changed(self, is_maximized: bool) -> None:
        icon = "MAXIMIZE_2" if is_maximized else "SQUARE"
        self._max_btn.setIcon(Icons.get_icon(icon, 12, COLORS["text_dim"]))

    def closeEvent(self, event: QCloseEvent) -> None:
        if hasattr(self._page, "can_close") and not self._page.can_close():
            event.ignore()
            return
        if hasattr(self._page, "cleanup"):
            self._page.cleanup()
        event.accept()

    # -- setup ----------------------------------------------------------

    def _setup_window(
        self, min_width: int, min_height: int, width: int, height: int
    ) -> None:
        window_title = (
            self._page.page_title()
            if hasattr(self._page, "page_title")
            else self._title
        )
        self.setWindowTitle(window_title)
        self.setMinimumSize(min_width, min_height)
        self.resize(width, height)
        self.setStyleSheet(get_main_stylesheet())

        if self._icon_path and self._icon_path.exists():
            self.setWindowIcon(QIcon(str(self._icon_path)))

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
        header.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: none;
                border-bottom: 1px solid {COLORS['border_default']};
            }}
            """
        )
        self.set_title_bar_widget(header)

        lay = QHBoxLayout(header)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(10)

        logo = QLabel()
        if self._icon_path and self._icon_path.exists():
            px = QPixmap(str(self._icon_path)).scaled(
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

        title_text = (
            self._page.page_title()
            if hasattr(self._page, "page_title")
            else self._title
        )
        title = QLabel(title_text)
        title.setStyleSheet(
            f"""
            color: {COLORS['text_primary']};
            font-size: {FONTS['size_sm']};
            font-weight: 600;
            """
        )
        lay.addWidget(title)
        lay.addStretch()

        self._status_badge = StatusBadge(kind=StatusKind.IDLE, text=tr("ready"))
        lay.addWidget(self._status_badge)

        settings_btn = QPushButton()
        settings_btn.setIcon(Icons.get_icon("SETTINGS", 16, COLORS["text_dim"]))
        settings_btn.setFixedSize(28, 28)
        settings_btn.setToolTip(tr("settings"))
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: 4px; padding: 6px;
            }}
            QPushButton:hover {{ background-color: {COLORS['bg_tertiary']}; }}
            """
        )
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

    # -- handlers -------------------------------------------------------

    def _on_settings(self) -> None:
        tabs = []
        if hasattr(self._page, "get_settings_tabs"):
            tabs = self._page.get_settings_tabs()
        SettingsDialog(self, extra_tabs=tabs).exec()

    def _on_status(self, kind: StatusKind, text: str) -> None:
        self._status_badge.set_status(kind, text)
