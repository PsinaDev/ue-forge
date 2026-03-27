"""
Path input widget with browse button and icon.
"""
from pathlib import Path
from typing import Optional, Callable
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QFileDialog,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from ue_forge.shared.styles import COLORS, FONTS, RADIUS
from ue_forge.shared.icons import Icons


class PathInput(QWidget):
    """
    Path input field with browse button and optional icon.
    
    Features:
    - SVG icon displayed inside the input (left side)
    - Browse button for file/directory selection
    - Optional label above the input
    - Optional hint text below the input
    - Path validation
    """
    
    path_changed = Signal(str)
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        label: str = "",
        placeholder: str = "Path...",
        hint: str = "",
        icon_name: str = "FOLDER_OPEN",
        file_filter: str = "",
        directory_mode: bool = False,
        validator: Optional[Callable[[str], bool]] = None,
    ):
        super().__init__(parent)
        
        self._file_filter = file_filter
        self._directory_mode = directory_mode
        self._validator = validator
        self._icon_name = icon_name
        
        self._setup_ui(label, placeholder, hint)
    
    def _setup_ui(self, label: str, placeholder: str, hint: str) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Label
        if label:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"""
                color: {COLORS['text_muted']};
                font-size: {FONTS['size_xs']};
                font-weight: 500;
            """)
            layout.addWidget(lbl)
        
        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        
        # Container for input with icon
        input_container = QWidget()
        input_container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_input']};
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
            }}
            QWidget:focus-within {{
                border-color: {COLORS['border_focus']};
            }}
        """)
        
        container_layout = QHBoxLayout(input_container)
        container_layout.setContentsMargins(12, 0, 4, 0)
        container_layout.setSpacing(8)
        
        # Icon label
        icon_label = QLabel()
        icon_label.setPixmap(Icons.get_pixmap(self._icon_name, 16, COLORS['text_dim']))
        icon_label.setStyleSheet(f"""
            background: transparent;
            border: none;
        """)
        icon_label.setFixedWidth(20)
        container_layout.addWidget(icon_label)
        
        # Input field
        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                padding: 10px 0;
                color: {COLORS['text_primary']};
                font-size: {FONTS['size_sm']};
            }}
        """)
        self._input.textChanged.connect(self._on_text_changed)
        container_layout.addWidget(self._input, 1)
        
        input_row.addWidget(input_container, 1)
        
        # Browse button
        browse_btn = QPushButton("...")
        browse_btn.setProperty("class", "browse")
        browse_btn.setFixedWidth(42)
        browse_btn.setFixedHeight(42)
        browse_btn.clicked.connect(self._browse)
        browse_btn.setCursor(Qt.PointingHandCursor)
        input_row.addWidget(browse_btn)
        
        layout.addLayout(input_row)
        
        # Hint
        if hint:
            hint_label = QLabel(hint)
            hint_label.setStyleSheet(f"""
                color: {COLORS['text_placeholder']};
                font-size: {FONTS['size_xs']};
            """)
            layout.addWidget(hint_label)
    
    def _on_text_changed(self, text: str) -> None:
        """Handle text change."""
        self.path_changed.emit(text)
    
    def _browse(self) -> None:
        """Open file/directory browser."""
        if self._directory_mode:
            path = QFileDialog.getExistingDirectory(
                self,
                "Select Directory",
                self._input.text() or "",
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select File",
                self._input.text() or "",
                self._file_filter or "All Files (*)",
            )
        
        if path:
            self._input.setText(path)
    
    def path(self) -> str:
        """Get current path."""
        return self._input.text()
    
    def set_path(self, path: str) -> None:
        """Set the path."""
        self._input.setText(path)
    
    def set_placeholder(self, text: str) -> None:
        """Set placeholder text."""
        self._input.setPlaceholderText(text)
    
    def is_valid(self) -> bool:
        """Check if the current path is valid."""
        path = self._input.text()
        if not path:
            return False
        
        if self._validator:
            return self._validator(path)
        
        p = Path(path)
        if self._directory_mode:
            return p.is_dir()
        return p.exists()
