"""
Command dialog for displaying build commands.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QWidget,
    QApplication,
)
from PySide6.QtCore import Qt

from ue_forge.shared.styles import COLORS, FONTS, RADIUS
from ue_forge.shared.localization import tr


class CommandDialog(QDialog):
    """Dialog for displaying and copying build command."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        command: str = "",
        title: str = None,
    ):
        super().__init__(parent)
        self._command = command
        
        self.setWindowTitle(title or tr("build_command"))
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setMinimumWidth(650)
        self.setMinimumHeight(300)
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title bar
        title_bar = QHBoxLayout()
        title_bar.setSpacing(8)
        
        title_label = QLabel(tr("build_command"))
        title_label.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: {FONTS['size_lg']};
            font-weight: 600;
        """)
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        
        # Close button
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

        # Description label
        desc_label = QLabel("Command to run in terminal:")
        desc_label.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: {FONTS['size_sm']};
        """)
        layout.addWidget(desc_label)

        # Command text area
        self._command_text = QTextEdit()
        self._command_text.setPlainText(self._command)
        self._command_text.setReadOnly(True)
        self._command_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_primary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['md']};
                color: {COLORS['text_secondary']};
                font-family: {FONTS['family_mono']};
                font-size: {FONTS['size_sm']};
                padding: 12px;
            }}
        """)
        layout.addWidget(self._command_text, 1)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        buttons_layout.addStretch()

        # Copy button
        self._copy_btn = QPushButton(tr("copy_command"))
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        buttons_layout.addWidget(self._copy_btn)

        # OK button
        ok_btn = QPushButton(tr("ok"))
        ok_btn.setProperty("class", "primary")
        ok_btn.setFixedWidth(80)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(ok_btn)

        layout.addLayout(buttons_layout)

    def _copy_to_clipboard(self) -> None:
        """Copy command to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._command)
        
        # Change button text temporarily
        self._copy_btn.setText(tr("copied"))
        self._copy_btn.setEnabled(False)
        
        # Reset after delay
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: (
            self._copy_btn.setText(tr("copy_command")),
            self._copy_btn.setEnabled(True),
        ))

    def get_command(self) -> str:
        """Get the command text."""
        return self._command
