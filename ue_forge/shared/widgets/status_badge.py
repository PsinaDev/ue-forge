"""
Status badge widget for displaying build status.
"""
from typing import Optional
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap, QTransform

from ue_forge.shared.styles import COLORS, FONTS, RADIUS
from ue_forge.shared.icons import Icons


class StatusBadge(QWidget):
    """
    Status badge with icon and text.

    Displays status with appropriate styling:
    - idle: gray
    - running: blue with animated spinner
    - success: green
    - failed: red
    - warning: amber
    """

    STYLES = {
        "idle": {
            "bg": COLORS["bg_tertiary"],
            "text": COLORS["text_muted"],
            "border": "transparent",
            "icon": "CLOCK",
        },
        "running": {
            "bg": "rgba(59, 130, 246, 0.2)",  # blue-500/20
            "text": "#60a5fa",  # blue-400
            "border": "rgba(59, 130, 246, 0.3)",
            "icon": "LOADER_2",
        },
        "success": {
            "bg": COLORS["success_bg"],
            "text": COLORS["success"],
            "border": COLORS["success_border"],
            "icon": "CHECK_CIRCLE_2",
        },
        "failed": {
            "bg": COLORS["error_bg"],
            "text": COLORS["error"],
            "border": COLORS["error_border"],
            "icon": "X_CIRCLE",
        },
        "warning": {
            "bg": COLORS["warning_bg"],
            "text": COLORS["warning"],
            "border": COLORS["warning_border"],
            "icon": "ALERT_TRIANGLE",
        },
    }

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        status: str = "idle",
        text: str = "Ready",
    ):
        super().__init__(parent)
        self._status = status
        self._text = text
        self._rotation = 0
        
        # Timer for spinner animation (created lazily)
        self._spin_timer: Optional[QTimer] = None

        self._setup_ui()
        self._update_style()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Icon label
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(12, 12)
        self._icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._icon_label)

        # Text label
        self._text_label = QLabel(self._text)
        self._text_label.setStyleSheet(f"""
            font-size: {FONTS['size_xs']};
            font-weight: 500;
        """)
        layout.addWidget(self._text_label)

        self.setFixedHeight(24)

    def _update_style(self) -> None:
        """Update style based on current status."""
        style = self.STYLES.get(self._status, self.STYLES["idle"])

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {style['bg']};
                border: 1px solid {style['border']};
                border-radius: {RADIUS['sm']};
            }}
        """)

        self._text_label.setStyleSheet(f"""
            color: {style['text']};
            font-size: {FONTS['size_xs']};
            font-weight: 500;
            background: transparent;
            border: none;
        """)

        # Update icon
        self._update_icon()

        # Start/stop spinner animation
        if self._status == "running":
            self._start_spinner()
        else:
            self._stop_spinner()

    def _start_spinner(self) -> None:
        """Start the spinner animation."""
        if self._spin_timer is None:
            self._spin_timer = QTimer(self)
            self._spin_timer.timeout.connect(self._rotate_icon)
        self._spin_timer.start(50)  # 20 fps

    def _stop_spinner(self) -> None:
        """Stop the spinner animation."""
        if self._spin_timer is not None:
            self._spin_timer.stop()
        self._rotation = 0
        self._update_icon()

    def _rotate_icon(self) -> None:
        """Rotate the icon for spinner effect."""
        self._rotation = (self._rotation + 18) % 360  # 18 degrees per frame
        self._update_icon()

    def _update_icon(self) -> None:
        """Update icon pixmap."""
        style = self.STYLES.get(self._status, self.STYLES["idle"])
        pixmap = Icons.get_pixmap(style["icon"], 12, style["text"])
        
        # Apply rotation for running status
        if self._status == "running" and self._rotation != 0:
            transform = QTransform()
            transform.rotate(self._rotation)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            # Re-center after rotation
            scaled = pixmap.scaled(12, 12, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pixmap = scaled
        
        self._icon_label.setPixmap(pixmap)

    def set_status(self, status: str, text: Optional[str] = None) -> None:
        """
        Set badge status.

        Args:
            status: One of 'idle', 'running', 'success', 'failed', 'warning'
            text: Optional status text
        """
        self._status = status
        if text:
            self._text = text
            self._text_label.setText(text)
        self._update_style()

    def get_status(self) -> str:
        """Get current status."""
        return self._status
