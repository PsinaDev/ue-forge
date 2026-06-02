"""
Dialog for manually adding Unreal Engine installations.
"""
import os
import sys
import subprocess
from typing import Optional, Dict, List
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QWidget,
    QGroupBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt

from framekit.styles import COLORS, FONTS, RADIUS
from framekit.dialogs import MessageDialog
from .engine_finder import EngineFinder
from framekit.localization import tr


class EngineEntryDialog(QDialog):
    """Dialog for managing Unreal Engine installations with multi-selection."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        engine_finder: Optional[EngineFinder] = None,
        existing_engines: Optional[Dict[str, str]] = None,
    ):
        super().__init__(parent)
        self._engine_finder = engine_finder or EngineFinder()
        self._engines: Dict[str, str] = dict(existing_engines or {})
        
        self.setWindowTitle(tr("manage_engine_installations"))
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self._setup_ui()
        self._populate_list()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: 8px;
            }}
            QListWidget {{
                background-color: {COLORS['bg_primary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 12px 16px;
                border-radius: 6px;
                color: {COLORS['text_primary']};
                margin: 2px 0px;
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['accent_bg']};
                border: none;
                outline: none;
            }}
            QListWidget::item:hover {{
                background-color: {COLORS['bg_tertiary']};
            }}
            QListWidget:focus {{
                outline: none;
                border: 1px solid {COLORS['border_focus']};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Custom title bar
        title_bar = QHBoxLayout()
        title_bar.setSpacing(8)
        
        title_label = QLabel(tr("manage_engine_installations"))
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

        # Current engines list
        list_group = QGroupBox(tr("registered_engines"))
        list_layout = QVBoxLayout(list_group)

        # Hint label
        hint_label = QLabel(tr("double_click_hint"))
        hint_label.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: {FONTS['size_xs']};
            font-style: italic;
            background: transparent;
            padding: 0px 0px 4px 0px;
        """)
        list_layout.addWidget(hint_label)

        self._engine_list = QListWidget()
        self._engine_list.setAlternatingRowColors(False)
        # Enable multi-selection
        self._engine_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._engine_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._engine_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        list_layout.addWidget(self._engine_list)

        # Selection info
        self._selection_info = QLabel("")
        self._selection_info.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: {FONTS['size_xs']};
            background: transparent;
        """)
        list_layout.addWidget(self._selection_info)

        # List buttons
        list_buttons = QHBoxLayout()
        list_buttons.setSpacing(8)

        self._remove_btn = QPushButton(tr("remove_selected"))
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._remove_selected)
        list_buttons.addWidget(self._remove_btn)

        list_buttons.addStretch()

        self._scan_btn = QPushButton(tr("scan_for_engines"))
        self._scan_btn.clicked.connect(self._scan_engines)
        list_buttons.addWidget(self._scan_btn)

        list_layout.addLayout(list_buttons)
        layout.addWidget(list_group)

        # Add engine section
        add_group = QGroupBox(tr("add_engine_manually"))
        add_layout = QVBoxLayout(add_group)

        # Path input row
        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(tr("path_to_ue_installation"))
        self._path_edit.textChanged.connect(self._validate_path)
        path_row.addWidget(self._path_edit)

        self._browse_btn = QPushButton(tr("browse"))
        self._browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(self._browse_btn)

        add_layout.addLayout(path_row)

        # Version input row
        version_row = QHBoxLayout()
        version_row.setSpacing(8)

        version_label = QLabel(tr("version") + ":")
        version_row.addWidget(version_label)

        self._version_edit = QLineEdit()
        self._version_edit.setPlaceholderText(tr("auto_detect"))
        self._version_edit.setMaximumWidth(120)
        version_row.addWidget(self._version_edit)

        version_row.addStretch()

        self._add_btn = QPushButton(tr("add_engine"))
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._add_engine)
        self._add_btn.setProperty("class", "primary")
        version_row.addWidget(self._add_btn)

        add_layout.addLayout(version_row)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        add_layout.addWidget(self._status_label)

        layout.addWidget(add_group)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_list(self) -> None:
        """Populate the engine list."""
        self._engine_list.clear()
        
        for version in sorted(self._engines.keys(), reverse=True):
            path = self._engines[version]
            item = QListWidgetItem(f"UE {version}  —  {path}")
            item.setData(Qt.UserRole, version)
            item.setData(Qt.UserRole + 1, path)  # Store path for easy access
            self._engine_list.addItem(item)

    def _on_selection_changed(self) -> None:
        """Handle selection change in list."""
        selected = self._engine_list.selectedItems()
        count = len(selected)
        self._remove_btn.setEnabled(count > 0)
        
        if count == 0:
            self._selection_info.setText("")
        elif count == 1:
            version = selected[0].data(Qt.UserRole)
            self._selection_info.setText(f"Selected: UE {version}")
        else:
            self._selection_info.setText(f"Selected: {count} engines")
    
    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on item to open engine folder."""
        path = item.data(Qt.UserRole + 1)
        if path and Path(path).exists():
            self._open_folder(path)
    
    def _open_folder(self, path: str) -> None:
        """Open folder in system file manager."""
        path_obj = Path(path)
        if not path_obj.exists():
            MessageDialog.warning(
                self,
                tr("folder_not_found"),
                f"{tr('folder_not_found')}:\n{path}"
            )
            return
        
        try:
            if sys.platform == "win32":
                os.startfile(str(path_obj))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path_obj)], check=True)
            else:  # Linux and others
                subprocess.run(["xdg-open", str(path_obj)], check=True)
        except Exception as e:
            MessageDialog.warning(
                self,
                tr("error"),
                f"{tr('could_not_open_folder')}:\n{e}"
            )

    def _remove_selected(self) -> None:
        """Remove selected engines from list."""
        selected = self._engine_list.selectedItems()
        if not selected:
            return

        count = len(selected)
        
        if count == 1:
            version = selected[0].data(Qt.UserRole)
            message = tr("remove_engine_confirm", version=version)
        else:
            message = f"Remove {count} selected engines from the list?"
        
        result = MessageDialog.question(
            self,
            tr("remove"),
            message,
            [tr("no"), tr("yes")]
        )
        
        if result == tr("yes"):
            for item in selected:
                version = item.data(Qt.UserRole)
                if version in self._engines:
                    del self._engines[version]
            self._populate_list()

    def _browse_path(self) -> None:
        """Browse for engine directory."""
        path = QFileDialog.getExistingDirectory(
            self,
            tr("select_uplugin_file"),
            str(Path.home()),
        )
        
        if path:
            self._path_edit.setText(path)

    def _validate_path(self) -> None:
        """Validate the entered path."""
        path_str = self._path_edit.text().strip()
        
        if not path_str:
            self._add_btn.setEnabled(False)
            self._status_label.setText("")
            self._version_edit.setText("")
            return

        path = Path(path_str)
        
        if not path.exists():
            self._add_btn.setEnabled(False)
            self._status_label.setText(tr("path_not_exist"))
            self._status_label.setStyleSheet(f"color: {COLORS['error']};")
            self._version_edit.setText("")
            return

        if not self._engine_finder.is_valid_engine_path(path):
            self._add_btn.setEnabled(False)
            self._status_label.setText(tr("not_valid_engine"))
            self._status_label.setStyleSheet(f"color: {COLORS['error']};")
            self._version_edit.setText("")
            return

        # Try to detect version
        version = self._engine_finder.extract_version(path)
        if version:
            self._version_edit.setText(version)
            self._status_label.setText(f"{tr('detected_ue')} {version}")
            self._status_label.setStyleSheet(f"color: {COLORS['success']};")
        else:
            self._version_edit.setText("")
            self._status_label.setText(tr("valid_engine_unknown_version"))
            self._status_label.setStyleSheet(f"color: {COLORS['warning']};")

        self._add_btn.setEnabled(True)

    def _add_engine(self) -> None:
        """Add the engine to the list."""
        path_str = self._path_edit.text().strip()
        version = self._version_edit.text().strip()
        
        if not path_str:
            return

        if not version:
            MessageDialog.warning(
                self,
                tr("version"),
                tr("version_required"),
            )
            return

        # Check for duplicate version
        if version in self._engines:
            result = MessageDialog.question(
                self,
                tr("version"),
                tr("version_exists", version=version),
                [tr("no"), tr("yes")]
            )
            if result != tr("yes"):
                return

        self._engines[version] = path_str
        self._populate_list()
        
        # Clear inputs
        self._path_edit.clear()
        self._version_edit.clear()
        self._status_label.setText(tr("engine_added"))
        self._status_label.setStyleSheet(f"color: {COLORS['success']};")

    def _scan_engines(self) -> None:
        """Scan for engines and add found ones."""
        self._status_label.setText(tr("scanning_engines"))
        self._status_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        
        # Force rescan
        found = self._engine_finder.find_all_engines(force_rescan=True)
        
        if found:
            for version, info in found.items():
                self._engines[version] = str(info.path)
            
            self._populate_list()
            self._status_label.setText(tr("found_engines", count=len(found)) + ". " + tr("found_engines_hint"))
            self._status_label.setStyleSheet(f"color: {COLORS['success']};")
        else:
            self._status_label.setText(tr("no_engines_found"))
            self._status_label.setStyleSheet(f"color: {COLORS['warning']};")

    def get_engines(self) -> Dict[str, str]:
        """Get the configured engines."""
        return self._engines.copy()
    
    def get_selected_versions(self) -> List[str]:
        """Get list of selected engine versions."""
        selected = self._engine_list.selectedItems()
        return [item.data(Qt.UserRole) for item in selected]
