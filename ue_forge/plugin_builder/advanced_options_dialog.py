"""
Advanced build options dialog.
"""
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QCheckBox,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QWidget,
)
from PySide6.QtCore import Qt

from ue_forge.shared.styles import COLORS, FONTS, RADIUS
from ue_forge.shared.localization import tr


class StyledCheckBox(QCheckBox):
    """Checkbox with proper cyan styling."""
    
    def __init__(self, text: str, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        from ue_forge.shared.icons import get_indicator_icon_path
        
        checkbox_unchecked = get_indicator_icon_path('checkbox_unchecked', COLORS['text_dim'])
        checkbox_unchecked_hover = get_indicator_icon_path('checkbox_unchecked', COLORS['text_muted'])
        checkbox_checked = get_indicator_icon_path('checkbox_checked', COLORS['accent_primary'], COLORS['accent_primary'])
        
        self.setStyleSheet(f"""
            QCheckBox {{
                background: transparent;
                color: {COLORS['text_secondary']};
                font-size: {FONTS['size_sm']};
                spacing: 12px;
                padding: 4px 0px;
                min-height: 24px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
            }}
            QCheckBox::indicator:unchecked {{
                image: url("{checkbox_unchecked}");
            }}
            QCheckBox::indicator:checked {{
                image: url("{checkbox_checked}");
            }}
            QCheckBox::indicator:unchecked:hover {{
                image: url("{checkbox_unchecked_hover}");
            }}
        """)


class AdvancedOptionsDialog(QDialog):
    """Dialog for configuring advanced build options."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("advanced_build_options"))
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setMinimumWidth(500)
        self.setMinimumHeight(520)  # Increased to fit better spacing
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: 8px;
            }}
            QGroupBox {{
                margin-top: 8px;
                padding-top: 24px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)
        
        # Custom title bar
        title_bar = QHBoxLayout()
        title_bar.setSpacing(8)
        
        title_label = QLabel(tr("advanced_build_options"))
        title_label.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: {FONTS['size_lg']};
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

        # Platforms group
        platforms_group = self._create_platforms_group()
        layout.addWidget(platforms_group)

        # Build options group
        options_group = self._create_options_group()
        layout.addWidget(options_group)

        # Extra parameters
        extra_group = self._create_extra_params_group()
        layout.addWidget(extra_group)

        layout.addStretch()

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_platforms_group(self) -> QGroupBox:
        """Create platforms selection group."""
        group = QGroupBox(tr("target_platforms"))
        layout = QVBoxLayout(group)
        layout.setSpacing(8)  # Increased spacing between checkboxes
        layout.setContentsMargins(12, 16, 12, 12)

        self._platform_checkboxes: Dict[str, QCheckBox] = {}
        
        platforms = [
            ("Win64", tr("windows_64"), True),
            ("Win32", tr("windows_32"), False),
            ("Linux", tr("linux"), False),
            ("Mac", tr("macos"), False),
        ]

        for platform_id, label, default_checked in platforms:
            checkbox = StyledCheckBox(label)
            checkbox.setChecked(default_checked)
            self._platform_checkboxes[platform_id] = checkbox
            layout.addWidget(checkbox)

        return group

    def _create_options_group(self) -> QGroupBox:
        """Create build options group."""
        group = QGroupBox(tr("build_options"))
        layout = QVBoxLayout(group)
        layout.setSpacing(8)  # Increased spacing between checkboxes
        layout.setContentsMargins(12, 16, 12, 12)

        self._no_host_platform_cb = StyledCheckBox(tr("no_host_platform"))
        layout.addWidget(self._no_host_platform_cb)

        self._strict_includes_cb = StyledCheckBox(tr("strict_includes"))
        layout.addWidget(self._strict_includes_cb)

        self._unversioned_cb = StyledCheckBox(tr("unversioned"))
        layout.addWidget(self._unversioned_cb)

        return group

    def _create_extra_params_group(self) -> QGroupBox:
        """Create extra parameters group."""
        group = QGroupBox(tr("additional_parameters"))
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        hint = QLabel(tr("additional_params_hint"))
        hint.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: {FONTS['size_xs']};
        """)
        layout.addWidget(hint)

        self._extra_params_edit = QLineEdit()
        self._extra_params_edit.setPlaceholderText("-Param=Value -Flag")
        layout.addWidget(self._extra_params_edit)

        return group

    def get_options(self) -> Dict[str, Any]:
        """
        Get the selected build options.
        
        Returns:
            Dictionary of option names to values
        """
        options: Dict[str, Any] = {}

        # Collect selected platforms
        selected_platforms = []
        for platform_id, checkbox in self._platform_checkboxes.items():
            if checkbox.isChecked():
                selected_platforms.append(platform_id)
        
        if selected_platforms:
            options["TargetPlatforms"] = "+".join(selected_platforms)

        # Collect checkboxes (using correct UAT parameter names)
        if self._no_host_platform_cb.isChecked():
            options["NoHostPlatform"] = True

        if self._strict_includes_cb.isChecked():
            options["StrictIncludes"] = True

        if self._unversioned_cb.isChecked():
            options["Unversioned"] = True

        # Store extra parameters as raw text (will be parsed when building)
        extra_text = self._extra_params_edit.text().strip()
        if extra_text:
            options["ExtraParams"] = extra_text

        return options

    def set_options(self, options: Dict[str, Any]) -> None:
        """
        Set the dialog options from a dictionary.
        
        Args:
            options: Dictionary of option names to values
        """
        # Set platforms
        platforms_str = options.get("TargetPlatforms", "Win64")
        selected_platforms = platforms_str.split("+") if platforms_str else []
        
        for platform_id, checkbox in self._platform_checkboxes.items():
            checkbox.setChecked(platform_id in selected_platforms)

        # Set checkboxes (using correct UAT parameter names)
        self._no_host_platform_cb.setChecked(
            options.get("NoHostPlatform", False)
        )
        self._strict_includes_cb.setChecked(
            options.get("StrictIncludes", False)
        )
        self._unversioned_cb.setChecked(
            options.get("Unversioned", False)
        )
        
        # Set extra params
        extra_params = options.get("ExtraParams", "")
        self._extra_params_edit.setText(extra_params)

    def get_selected_platforms(self) -> list[str]:
        """Get list of selected platforms."""
        return [
            platform_id
            for platform_id, checkbox in self._platform_checkboxes.items()
            if checkbox.isChecked()
        ]
