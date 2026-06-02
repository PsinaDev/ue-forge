"""
Dynamic settings dialog with pluggable tabs.

Each tool page can contribute its own settings tabs via
``get_settings_tabs() -> List[SettingsTab]``.  The host window
(or standalone shell) collects them and passes them to this dialog.

The dialog always includes a built-in Language tab.
"""

from abc import abstractmethod
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QGroupBox,
    QTabWidget,
    QFileDialog,
)
from PySide6.QtCore import Qt

from framekit.styles import COLORS, FONTS
from framekit.config import get_config_manager
from framekit.localization import (
    tr,
    get_current_language,
    set_language,
    get_available_languages,
    load_custom_locale,
)
from .message_dialog import MessageDialog


# ---------------------------------------------------------------------------
# Public protocol
# ---------------------------------------------------------------------------

class SettingsTab(QWidget):
    """
    Base class for a pluggable settings tab.

    Subclass and implement ``tab_title`` and ``on_apply``.
    The widget itself is added as a tab in :class:`SettingsDialog`.
    """

    @abstractmethod
    def tab_title(self) -> str:
        """Return a short title used as the tab label."""
        ...

    @abstractmethod
    def on_apply(self) -> None:
        """Called when the user clicks OK.  Persist your changes here."""
        ...


# ---------------------------------------------------------------------------
# Built-in Language tab
# ---------------------------------------------------------------------------

class _LanguageTab(QWidget):
    """Built-in language / locale settings tab."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._initial_language = get_current_language()
        self._language_changed = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # Language selection
        lang_group = QGroupBox(tr("select_language"))
        lang_layout = QVBoxLayout(lang_group)

        self._lang_combo = QComboBox()
        for code, name in get_available_languages().items():
            self._lang_combo.addItem(name, code)

        idx = self._lang_combo.findData(self._initial_language)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)

        self._lang_combo.currentIndexChanged.connect(self._on_changed)
        lang_layout.addWidget(self._lang_combo)

        note = QLabel(tr("language_restart_note"))
        note.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: {FONTS['size_xs']};
            font-style: italic;
        """)
        lang_layout.addWidget(note)
        layout.addWidget(lang_group)

        # Custom locale
        custom_group = QGroupBox(tr("load_custom_locale"))
        custom_layout = QHBoxLayout(custom_group)

        self._locale_label = QLabel(tr("no_custom_locale"))
        self._locale_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        custom_layout.addWidget(self._locale_label, 1)

        browse_btn = QPushButton(tr("browse"))
        browse_btn.clicked.connect(self._load_locale)
        custom_layout.addWidget(browse_btn)

        layout.addWidget(custom_group)
        layout.addStretch()

    def _on_changed(self, _index: int) -> None:
        if self._lang_combo.currentData() != self._initial_language:
            self._language_changed = True

    def _load_locale(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("load_custom_locale"), str(Path.home()),
            "JSON Files (*.json)",
        )
        if path:
            if load_custom_locale(Path(path)):
                self._locale_label.setText(Path(path).name)
                MessageDialog.information(self, tr("language"), tr("locale_loaded"))
            else:
                MessageDialog.error(self, tr("error"), tr("locale_load_error"))

    # -- called by SettingsDialog on OK ---------------------------------

    @property
    def language_changed(self) -> bool:
        return self._language_changed

    @property
    def selected_language(self) -> str:
        return self._lang_combo.currentData()


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------

class SettingsDialog(QDialog):
    """
    Application settings dialog with dynamic tabs.

    Always contains a Language tab.  Additional tabs from tool pages
    are passed in via *extra_tabs*.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        extra_tabs: Optional[List[SettingsTab]] = None,
    ):
        super().__init__(parent)
        self._extra_tabs: List[SettingsTab] = extra_tabs or []
        self._config = get_config_manager()

        self.setWindowTitle(tr("settings"))
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: 8px;
            }}
            QTabWidget::pane {{
                border: 1px solid {COLORS['border_default']};
                border-radius: 6px;
                background-color: {COLORS['bg_primary']};
            }}
            QTabBar::tab {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_muted']};
                padding: 8px 16px;
                border: none;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_primary']};
            }}
            QTabBar::tab:hover {{
                color: {COLORS['text_secondary']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title bar
        title_bar = QHBoxLayout()
        title_label = QLabel(tr("settings"))
        title_label.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 14px;
            font-weight: 600;
        """)
        title_bar.addWidget(title_label)
        title_bar.addStretch()

        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLORS['text_dim']};
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {COLORS['text_primary']};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        title_bar.addWidget(close_btn)
        layout.addLayout(title_bar)

        # Tabs
        self._tabs = QTabWidget()

        # Extra tabs first (module-specific go before language)
        for tab in self._extra_tabs:
            self._tabs.addTab(tab, tab.tab_title())

        # Built-in language tab last
        self._language_tab = _LanguageTab()
        self._tabs.addTab(self._language_tab, tr("language"))

        layout.addWidget(self._tabs)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        # Apply extra tabs
        for tab in self._extra_tabs:
            tab.on_apply()

        # Apply language
        lang = self._language_tab.selected_language
        set_language(lang)
        self._config.update_config(language=lang)

        if self._language_tab.language_changed:
            MessageDialog.information(
                self, tr("language"), tr("restart_to_apply"),
            )

        self.accept()
