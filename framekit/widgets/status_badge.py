"""
Status badge widget — small pill-shaped indicator with icon + text.

The visual category is driven by :class:`framekit.types.StatusKind`;
the text is free-form and supplied by the calling page.
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from framekit.icons import Icons
from framekit.styles import COLORS, FONTS, RADIUS
from framekit.types import StatusKind


class StatusBadge(QWidget):
    """
    Status badge with icon and text.

    - ``StatusKind.IDLE``    : gray
    - ``StatusKind.RUNNING`` : blue with animated spinner
    - ``StatusKind.SUCCESS`` : green
    - ``StatusKind.FAILED``  : red
    - ``StatusKind.WARNING`` : amber
    """

    STYLES: ClassVar[dict[StatusKind, dict[str, str]]] = {
        StatusKind.IDLE: {
            "bg": COLORS["bg_tertiary"],
            "text": COLORS["text_muted"],
            "border": "transparent",
            "icon": "CLOCK",
        },
        StatusKind.RUNNING: {
            "bg": "rgba(59, 130, 246, 0.2)",
            "text": "#60a5fa",
            "border": "rgba(59, 130, 246, 0.3)",
            "icon": "LOADER_2",
        },
        StatusKind.SUCCESS: {
            "bg": COLORS["success_bg"],
            "text": COLORS["success"],
            "border": COLORS["success_border"],
            "icon": "CHECK_CIRCLE_2",
        },
        StatusKind.FAILED: {
            "bg": COLORS["error_bg"],
            "text": COLORS["error"],
            "border": COLORS["error_border"],
            "icon": "X_CIRCLE",
        },
        StatusKind.WARNING: {
            "bg": COLORS["warning_bg"],
            "text": COLORS["warning"],
            "border": COLORS["warning_border"],
            "icon": "ALERT_TRIANGLE",
        },
    }

    def __init__(
        self,
        parent: QWidget | None = None,
        kind: StatusKind = StatusKind.IDLE,
        text: str = "Ready",
    ):
        super().__init__(parent)
        self._kind: StatusKind = kind
        self._text: str = text
        self._rotation: int = 0
        self._spin_timer: QTimer | None = None

        self._setup_ui()
        self._update_style()

    # -- public API ----------------------------------------------------

    def set_status(self, kind: StatusKind, text: str | None = None) -> None:
        """Update visual category and (optionally) label text."""
        self._kind = kind
        if text is not None:
            self._text = text
            self._text_label.setText(text)
        self._update_style()

    def get_status(self) -> StatusKind:
        """Return current visual category."""
        return self._kind

    # -- internals -----------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(12, 12)
        self._icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._icon_label)

        self._text_label = QLabel(self._text)
        self._text_label.setStyleSheet(
            f"font-size: {FONTS['size_xs']}; font-weight: 500;"
        )
        layout.addWidget(self._text_label)

        self.setFixedHeight(24)

    def _update_style(self) -> None:
        style = self.STYLES.get(self._kind, self.STYLES[StatusKind.IDLE])

        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {style['bg']};
                border: 1px solid {style['border']};
                border-radius: {RADIUS['sm']};
            }}
            """
        )
        self._text_label.setStyleSheet(
            f"""
            color: {style['text']};
            font-size: {FONTS['size_xs']};
            font-weight: 500;
            background: transparent;
            border: none;
            """
        )

        self._update_icon()

        if self._kind == StatusKind.RUNNING:
            self._start_spinner()
        else:
            self._stop_spinner()

    def _start_spinner(self) -> None:
        if self._spin_timer is None:
            self._spin_timer = QTimer(self)
            self._spin_timer.timeout.connect(self._rotate_icon)
        self._spin_timer.start(50)

    def _stop_spinner(self) -> None:
        if self._spin_timer is not None:
            self._spin_timer.stop()
        self._rotation = 0
        self._update_icon()

    def _rotate_icon(self) -> None:
        self._rotation = (self._rotation + 18) % 360
        self._update_icon()

    def _update_icon(self) -> None:
        style = self.STYLES.get(self._kind, self.STYLES[StatusKind.IDLE])
        pixmap = Icons.get_pixmap(style["icon"], 12, style["text"])

        if self._kind == StatusKind.RUNNING and self._rotation != 0:
            transform = QTransform()
            transform.rotate(self._rotation)
            pixmap = pixmap.transformed(
                transform, Qt.TransformationMode.SmoothTransformation
            )
            pixmap = pixmap.scaled(
                12, 12,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self._icon_label.setPixmap(pixmap)
