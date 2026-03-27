"""
Host window for UE Forge.

Inherits :class:`FramelessWindow` and adds sidebar navigation
with animated expand/collapse and stacked page management.
"""

import sys
from pathlib import Path
from typing import Optional, Dict

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QStackedWidget,
)
from PySide6.QtCore import Qt, QSize, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QCloseEvent, QPixmap, QIcon

from pyside_frameless import FramelessWindow
from ue_forge.shared.styles import COLORS, FONTS, get_main_stylesheet
from ue_forge.shared.icons import Icons
from ue_forge.shared.localization import tr
from ue_forge.shared.widgets import StatusBadge
from ue_forge.shared.dialogs import SettingsDialog


# ---------------------------------------------------------------------------
# Sidebar button
# ---------------------------------------------------------------------------

class _SidebarButton(QPushButton):
    """Navigation button supporting collapsed (icon-only) and expanded (icon + label) modes."""

    def __init__(self, page_id: str, icon_name: str, label_text: str, parent=None):
        super().__init__(parent)
        self.page_id = page_id
        self._icon_name = icon_name
        self._label_text = label_text
        self._active = False
        self._expanded = False

        self.setFixedHeight(40)
        self.setFixedWidth(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(label_text)
        self._update_style()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._update_style()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        if expanded:
            self.setText(f"  {self._label_text}")
            self.setToolTip("")
        else:
            self.setText("")
            self.setToolTip(self._label_text)
        self.setFixedWidth(16777215 if expanded else 40)
        self._update_style()

    def _update_style(self) -> None:
        color = COLORS["accent_primary"] if self._active else COLORS["text_dim"]
        self.setIcon(Icons.get_icon(self._icon_name, 20, color))
        self.setIconSize(QSize(20, 20))

        bg = COLORS["bg_tertiary"] if self._active else "transparent"
        border_left = f"2px solid {COLORS['accent_primary']}" if self._active else "2px solid transparent"
        text_color = COLORS["text_primary"] if self._active else COLORS["text_muted"]
        align = "left" if self._expanded else "center"
        padding = "0px 0px 0px 10px" if self._expanded else "0px"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: none;
                border-left: {border_left};
                border-radius: 0px;
                padding: {padding};
                color: {text_color};
                font-size: {FONTS['size_sm']};
                font-weight: 500;
                text-align: {align};
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_secondary']};
            }}
        """)


# ---------------------------------------------------------------------------
# HostWindow
# ---------------------------------------------------------------------------

class HostWindow(FramelessWindow):
    """
    Main application window with sidebar navigation and stacked pages.

    Usage::

        host = HostWindow()
        host.add_page(builder_page)
        host.add_page(renamer_page)
        host.show()
    """

    SIDEBAR_COLLAPSED_WIDTH = 48
    SIDEBAR_EXPANDED_WIDTH = 180

    def __init__(self):
        super().__init__()

        self._pages: Dict[str, tuple] = {}
        self._active_page_id: Optional[str] = None
        self._sidebar_expanded: bool = False
        self._sidebar_anim: Optional[QVariantAnimation] = None
        self._page_statuses: Dict[str, tuple] = {}  # page_id -> (badge_status, text)

        self._setup_window()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle(tr("host_title"))
        self.setMinimumSize(1100, 650)
        self.resize(1200, 800)
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

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._sidebar = self._create_sidebar()
        body_layout.addWidget(self._sidebar)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {COLORS['border_default']};")
        body_layout.addWidget(sep)

        self._page_stack = QStackedWidget()
        body_layout.addWidget(self._page_stack, 1)

        root.addWidget(body, 1)

    # ------------------------------------------------------------------
    # Header (title bar)
    # ------------------------------------------------------------------

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

        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(10)

        # App icon
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
        layout.addWidget(logo)

        title = QLabel(tr("host_title"))
        title.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: {FONTS['size_sm']};
            font-weight: 600;
        """)
        layout.addWidget(title)
        layout.addStretch()

        self._status_badge = StatusBadge(status="idle", text=tr("ready"))
        layout.addWidget(self._status_badge)

        # Settings button
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
        settings_btn.clicked.connect(self._on_settings_clicked)
        layout.addWidget(settings_btn)

        layout.addSpacing(16)

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
        layout.addWidget(min_btn)

        self._maximize_btn = QPushButton()
        self._maximize_btn.setIcon(Icons.get_icon("SQUARE", 12, COLORS["text_dim"]))
        self._maximize_btn.setFixedSize(32, 28)
        self._maximize_btn.setStyleSheet(btn_style)
        self._maximize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._maximize_btn.clicked.connect(self.toggle_maximize)
        layout.addWidget(self._maximize_btn)

        close_btn = QPushButton()
        close_btn.setIcon(Icons.get_icon("X", 14, COLORS["text_dim"]))
        close_btn.setFixedSize(32, 28)
        close_btn.setStyleSheet(close_style)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        return header

    def on_maximize_changed(self, is_maximized: bool) -> None:
        icon = "MAXIMIZE_2" if is_maximized else "SQUARE"
        self._maximize_btn.setIcon(Icons.get_icon(icon, 12, COLORS["text_dim"]))

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFixedWidth(self.SIDEBAR_COLLAPSED_WIDTH)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: none;
            }}
        """)

        self._sidebar_layout = QVBoxLayout(sidebar)
        self._sidebar_layout.setContentsMargins(4, 8, 4, 8)
        self._sidebar_layout.setSpacing(4)
        self._sidebar_layout.addStretch()

        self._sidebar_toggle = QPushButton()
        self._sidebar_toggle.setFixedHeight(32)
        self._sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sidebar_toggle.clicked.connect(self._toggle_sidebar)
        self._update_toggle_icon()
        self._sidebar_layout.addWidget(self._sidebar_toggle)

        return sidebar

    def _toggle_sidebar(self) -> None:
        target = not self._sidebar_expanded
        start_w = self._sidebar.width()
        end_w = self.SIDEBAR_EXPANDED_WIDTH if target else self.SIDEBAR_COLLAPSED_WIDTH

        if self._sidebar_anim is not None:
            self._sidebar_anim.stop()

        self._sidebar_anim = QVariantAnimation()
        self._sidebar_anim.setDuration(180)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._sidebar_anim.setStartValue(float(start_w))
        self._sidebar_anim.setEndValue(float(end_w))
        self._sidebar_anim.valueChanged.connect(
            lambda v: self._sidebar.setFixedWidth(int(v))
        )
        self._sidebar_anim.finished.connect(
            lambda: self._on_sidebar_done(target)
        )

        if target:
            for _pid, (_w, btn) in self._pages.items():
                btn.set_expanded(True)

        self._sidebar_anim.start()

    def _on_sidebar_done(self, expanded: bool) -> None:
        self._sidebar_expanded = expanded
        if not expanded:
            for _pid, (_w, btn) in self._pages.items():
                btn.set_expanded(False)
        self._update_toggle_icon()

    def _update_toggle_icon(self) -> None:
        icon_name = "CHEVRON_LEFT" if self._sidebar_expanded else "CHEVRON_RIGHT"
        self._sidebar_toggle.setIcon(Icons.get_icon(icon_name, 14, COLORS["text_dim"]))
        self._sidebar_toggle.setIconSize(QSize(14, 14))
        self._sidebar_toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: 4px; padding: 0px;
            }}
            QPushButton:hover {{ background-color: {COLORS['bg_tertiary']}; }}
        """)

    # ------------------------------------------------------------------
    # Page management
    # ------------------------------------------------------------------

    def add_page(self, widget: QWidget) -> None:
        """
        Register a tool page.

        The widget must expose ``PAGE_ID``, ``PAGE_ICON``, ``page_title()``,
        and optionally ``status_changed``, ``can_close``, ``cleanup``,
        ``get_settings_tabs``.
        """
        page_id = widget.PAGE_ID
        icon_name = widget.PAGE_ICON
        title = widget.page_title()

        self._page_stack.addWidget(widget)

        btn = _SidebarButton(page_id, icon_name, title)
        btn.clicked.connect(lambda _=False, pid=page_id: self._switch_page(pid))

        insert_idx = self._sidebar_layout.count() - 2
        self._sidebar_layout.insertWidget(insert_idx, btn)

        if hasattr(widget, "status_changed"):
            widget.status_changed.connect(self._on_page_status)

        self._pages[page_id] = (widget, btn)
        btn.set_expanded(self._sidebar_expanded)

        if len(self._pages) == 1:
            self._switch_page(page_id)

    def _switch_page(self, page_id: str) -> None:
        if page_id not in self._pages:
            return
        widget, btn = self._pages[page_id]

        if self._active_page_id and self._active_page_id in self._pages:
            _, prev_btn = self._pages[self._active_page_id]
            prev_btn.set_active(False)

        self._active_page_id = page_id
        btn.set_active(True)
        self._page_stack.setCurrentWidget(widget)

        # Restore saved status for this page, or default to "Ready"
        saved = self._page_statuses.get(page_id)
        if saved:
            self._status_badge.set_status(saved[0], saved[1])
        else:
            self._status_badge.set_status("idle", tr("ready"))

    # ------------------------------------------------------------------
    # Settings — delegates to active page's tabs
    # ------------------------------------------------------------------

    def _on_settings_clicked(self) -> None:
        extra_tabs = []
        if self._active_page_id and self._active_page_id in self._pages:
            widget, _ = self._pages[self._active_page_id]
            if hasattr(widget, "get_settings_tabs"):
                extra_tabs = widget.get_settings_tabs()

        dlg = SettingsDialog(self, extra_tabs=extra_tabs)
        dlg.exec()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _on_page_status(self, badge_status: str, text: str) -> None:
        sender = self.sender()
        # Find which page emitted this and save its status
        for pid, (widget, _btn) in self._pages.items():
            if widget is sender:
                self._page_statuses[pid] = (badge_status, text)
                # Update badge only if this page is currently active
                if pid == self._active_page_id:
                    self._status_badge.set_status(badge_status, text)
                break

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        for _pid, (widget, _btn) in self._pages.items():
            if hasattr(widget, "can_close") and not widget.can_close():
                event.ignore()
                return
        for _pid, (widget, _btn) in self._pages.items():
            if hasattr(widget, "cleanup"):
                widget.cleanup()
        event.accept()
