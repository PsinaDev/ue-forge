"""
Engines management settings tab for Plugin Builder.

Provides scanning, manual adding, and removal of UE engine installations.
Plugs into the dynamic :class:`SettingsDialog` via the :class:`SettingsTab` protocol.
"""

from pathlib import Path
from typing import Optional, Dict

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QGroupBox,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QLineEdit,
)
from PySide6.QtCore import Qt, Signal

from ue_forge.shared.styles import COLORS, FONTS
from ue_forge.shared.localization import tr
from ue_forge.shared.dialogs import MessageDialog, SettingsTab
from .engine_finder import EngineFinder


class EnginesSettingsTab(SettingsTab):
    """Settings tab for managing registered Unreal Engine installations."""

    engines_changed = Signal(dict)

    def __init__(
        self,
        engine_finder: Optional[EngineFinder] = None,
        existing_engines: Optional[Dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._engine_finder = EngineFinder()
        self._engines: Dict[str, str] = dict(existing_engines or {})
        self._setup_ui()
        self._populate_engines()

    def tab_title(self) -> str:
        return tr("registered_engines")

    def on_apply(self) -> None:
        self.engines_changed.emit(self._engines.copy())

    # -- UI -------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS['bg_primary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px 14px;
                border-radius: 6px;
                color: {COLORS['text_primary']};
                margin: 2px 0px;
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['accent_bg']};
            }}
            QListWidget::item:hover {{
                background-color: {COLORS['bg_tertiary']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        hint = QLabel(tr("double_click_hint"))
        hint.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: {FONTS['size_xs']};
            font-style: italic;
        """)
        layout.addWidget(hint)

        self._engine_list = QListWidget()
        self._engine_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._engine_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._engine_list.itemDoubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self._engine_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._remove_btn = QPushButton(tr("remove_selected"))
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(self._remove_btn)
        btn_row.addStretch()
        scan_btn = QPushButton(tr("scan_for_engines"))
        scan_btn.clicked.connect(self._scan_engines)
        btn_row.addWidget(scan_btn)
        layout.addLayout(btn_row)

        # Manual add section
        add_group = QGroupBox(tr("add_engine_manually"))
        add_layout = QVBoxLayout(add_group)
        add_layout.setSpacing(8)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(tr("path_to_ue_installation"))
        self._path_edit.textChanged.connect(self._validate_path)
        path_row.addWidget(self._path_edit)
        browse_btn = QPushButton(tr("browse"))
        browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(browse_btn)
        add_layout.addLayout(path_row)

        ver_row = QHBoxLayout()
        ver_row.setSpacing(8)
        ver_row.addWidget(QLabel(tr("version") + ":"))
        self._version_edit = QLineEdit()
        self._version_edit.setPlaceholderText(tr("auto_detect"))
        self._version_edit.setMaximumWidth(100)
        ver_row.addWidget(self._version_edit)
        ver_row.addStretch()
        self._add_btn = QPushButton(tr("add_engine"))
        self._add_btn.setEnabled(False)
        self._add_btn.setProperty("class", "primary")
        self._add_btn.clicked.connect(self._add_manually)
        ver_row.addWidget(self._add_btn)
        add_layout.addLayout(ver_row)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        add_layout.addWidget(self._status_label)

        layout.addWidget(add_group)

    # -- Actions --------------------------------------------------------

    def _populate_engines(self) -> None:
        self._engine_list.clear()
        for ver in sorted(self._engines.keys(), reverse=True):
            path = self._engines[ver]
            item = QListWidgetItem(f"UE {ver}  —  {path}")
            item.setData(Qt.UserRole, ver)
            item.setData(Qt.UserRole + 1, path)
            self._engine_list.addItem(item)

    def _on_selection_changed(self) -> None:
        self._remove_btn.setEnabled(bool(self._engine_list.selectedItems()))

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        import os, sys, subprocess
        path = item.data(Qt.UserRole + 1)
        if path and Path(path).exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(path))
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(path)], check=True)
                else:
                    subprocess.run(["xdg-open", str(path)], check=True)
            except Exception as e:
                MessageDialog.error(self, tr("error"), f"{tr('could_not_open_folder')}:\n{e}")

    def _remove_selected(self) -> None:
        selected = self._engine_list.selectedItems()
        if not selected:
            return
        count = len(selected)
        if count == 1:
            msg = tr("remove_engine_confirm", version=selected[0].data(Qt.UserRole))
        else:
            msg = f"Remove {count} selected engines from the list?"
        result = MessageDialog.question(self, tr("remove"), msg, [tr("no"), tr("yes")])
        if result == tr("yes"):
            for item in selected:
                ver = item.data(Qt.UserRole)
                self._engines.pop(ver, None)
            self._populate_engines()

    def _scan_engines(self) -> None:
        found = self._engine_finder.find_all_engines(force_rescan=True)
        if found:
            for ver, info in found.items():
                self._engines[ver] = str(info.path)
            self._populate_engines()
            msg = tr("found_engines", count=len(found)) + "\n\n" + tr("found_engines_hint")
            MessageDialog.information(self, tr("scan_for_engines"), msg)
        else:
            MessageDialog.information(self, tr("scan_for_engines"), tr("no_engines_found"))

    def _browse_path(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, tr("select_ue_installation"), str(Path.home()),
        )
        if path:
            self._path_edit.setText(path)

    def _validate_path(self) -> None:
        text = self._path_edit.text().strip()
        if not text:
            self._add_btn.setEnabled(False)
            self._status_label.setText("")
            self._version_edit.setText("")
            return
        p = Path(text)
        if not p.exists():
            self._add_btn.setEnabled(False)
            self._status_label.setText(tr("path_not_exist"))
            self._status_label.setStyleSheet(f"color: {COLORS['error']};")
            self._version_edit.setText("")
            return
        if not self._engine_finder.is_valid_engine_path(p):
            self._add_btn.setEnabled(False)
            self._status_label.setText(tr("not_valid_engine"))
            self._status_label.setStyleSheet(f"color: {COLORS['error']};")
            self._version_edit.setText("")
            return
        ver = self._engine_finder.extract_version(p)
        if ver:
            self._version_edit.setText(ver)
            self._status_label.setText(f"{tr('detected_ue')} {ver}")
            self._status_label.setStyleSheet(f"color: {COLORS['success']};")
        else:
            self._version_edit.setText("")
            self._status_label.setText(tr("valid_engine_unknown_version"))
            self._status_label.setStyleSheet(f"color: {COLORS['warning']};")
        self._add_btn.setEnabled(True)

    def _add_manually(self) -> None:
        text = self._path_edit.text().strip()
        ver = self._version_edit.text().strip()
        if not text:
            return
        if not ver:
            MessageDialog.warning(self, tr("version"), tr("version_required"))
            return
        if ver in self._engines:
            res = MessageDialog.question(
                self, tr("version"), tr("version_exists", version=ver),
                [tr("no"), tr("yes")],
            )
            if res != tr("yes"):
                return
        self._engines[ver] = text
        self._populate_engines()
        self._path_edit.clear()
        self._version_edit.clear()
        self._status_label.setText(tr("engine_added"))
        self._status_label.setStyleSheet(f"color: {COLORS['success']};")
