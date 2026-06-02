"""
Custom styled message dialog to replace QMessageBox.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from PySide6.QtCore import Qt

from framekit.styles import COLORS, FONTS, RADIUS
from framekit.localization import tr


class MessageDialog(QDialog):
    """Custom styled message dialog."""
    
    # Dialog types
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    QUESTION = "question"
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: str = "",
        message: str = "",
        dialog_type: str = INFO,
        buttons: list[str] = None,
    ):
        super().__init__(parent)
        self._dialog_type = dialog_type
        self._title = title
        self._message = message
        self._buttons = buttons or [tr("ok")]
        self._result_button = None
        
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setMinimumWidth(350)
        self.setMaximumWidth(500)
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)
        
        # Title bar
        title_bar = QHBoxLayout()
        title_bar.setSpacing(8)
        
        # Icon based on type
        icon_color = {
            self.INFO: COLORS['accent_primary'],
            self.WARNING: COLORS['warning'],
            self.ERROR: COLORS['error'],
            self.QUESTION: COLORS['accent_primary'],
        }.get(self._dialog_type, COLORS['text_primary'])
        
        icon_char = {
            self.INFO: "ℹ",
            self.WARNING: "⚠",
            self.ERROR: "✕",
            self.QUESTION: "?",
        }.get(self._dialog_type, "")
        
        if icon_char:
            icon_label = QLabel(icon_char)
            icon_label.setStyleSheet(f"""
                color: {icon_color};
                font-size: 18px;
                font-weight: bold;
            """)
            title_bar.addWidget(icon_label)
        
        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: {FONTS['size_base']};
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
        
        # Message
        message_label = QLabel(self._message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: {FONTS['size_sm']};
            line-height: 1.5;
        """)
        layout.addWidget(message_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()
        
        for i, btn_text in enumerate(self._buttons):
            btn = QPushButton(btn_text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(80)
            
            # First button is primary for non-questions, last for questions
            is_primary = (i == 0 and self._dialog_type != self.QUESTION) or \
                        (i == len(self._buttons) - 1 and self._dialog_type == self.QUESTION)
            
            if is_primary:
                btn.setProperty("class", "primary")
            
            btn.clicked.connect(lambda checked, t=btn_text: self._on_button_clicked(t))
            btn_layout.addWidget(btn)
        
        layout.addLayout(btn_layout)
    
    def _on_button_clicked(self, button_text: str) -> None:
        """Handle button click."""
        self._result_button = button_text
        self.accept()
    
    def get_result(self) -> Optional[str]:
        """Get the clicked button text."""
        return self._result_button
    
    @classmethod
    def information(
        cls,
        parent: Optional[QWidget],
        title: str,
        message: str,
    ) -> None:
        """Show information dialog."""
        dialog = cls(parent, title, message, cls.INFO, [tr("ok")])
        dialog.exec()
    
    @classmethod
    def warning(
        cls,
        parent: Optional[QWidget],
        title: str,
        message: str,
    ) -> None:
        """Show warning dialog."""
        dialog = cls(parent, title, message, cls.WARNING, [tr("ok")])
        dialog.exec()
    
    @classmethod
    def error(
        cls,
        parent: Optional[QWidget],
        title: str,
        message: str,
    ) -> None:
        """Show error dialog."""
        dialog = cls(parent, title, message, cls.ERROR, [tr("ok")])
        dialog.exec()
    
    @classmethod
    def question(
        cls,
        parent: Optional[QWidget],
        title: str,
        message: str,
        buttons: list[str] = None,
    ) -> str:
        """Show question dialog. Returns clicked button text."""
        if buttons is None:
            buttons = [tr("no"), tr("yes")]
        dialog = cls(parent, title, message, cls.QUESTION, buttons)
        dialog.exec()
        return dialog.get_result()
