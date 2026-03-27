"""
Drag-and-drop overlay and base widget.

Provides animated visual feedback during file drops.
No application-specific dependencies — colors, icons, and text
are injected by the consumer.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import (
    Qt,
    Signal,
    QPropertyAnimation,
    Property,
    QEasingCurve,
    QMimeData,
    QTimer,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QPixmap,
)


class DropOverlay(QWidget):
    """
    Animated overlay shown during drag-and-drop.

    By default draws a translucent cyan background with a dashed border
    for valid drops and red for invalid.  Override colours / pixmaps with
    the ``configure`` method.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._opacity = 0.0
        self._is_valid = True

        # Configurable visuals
        self._valid_bg = QColor(34, 211, 238, 25)
        self._valid_border = QColor(34, 211, 238, 180)
        self._invalid_bg = QColor(248, 113, 113, 25)
        self._invalid_border = QColor(248, 113, 113, 180)
        self._valid_pixmap: QPixmap | None = None
        self._invalid_pixmap: QPixmap | None = None
        self._invalid_text: str = "Invalid file"
        self._font_family: str = "Segoe UI, SF Pro Display, Ubuntu, sans-serif"

        self._animation = QPropertyAnimation(self, b"opacity")
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hide_connected = False

        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    # -- Configuration --------------------------------------------------

    def configure(
        self,
        *,
        valid_bg: QColor | None = None,
        valid_border: QColor | None = None,
        invalid_bg: QColor | None = None,
        invalid_border: QColor | None = None,
        valid_pixmap: QPixmap | None = None,
        invalid_pixmap: QPixmap | None = None,
        invalid_text: str | None = None,
        font_family: str | None = None,
    ) -> None:
        """Set visual parameters.  Pass only the values you want to change."""
        if valid_bg is not None:
            self._valid_bg = valid_bg
        if valid_border is not None:
            self._valid_border = valid_border
        if invalid_bg is not None:
            self._invalid_bg = invalid_bg
        if invalid_border is not None:
            self._invalid_border = invalid_border
        if valid_pixmap is not None:
            self._valid_pixmap = valid_pixmap
        if invalid_pixmap is not None:
            self._invalid_pixmap = invalid_pixmap
        if invalid_text is not None:
            self._invalid_text = invalid_text
        if font_family is not None:
            self._font_family = font_family

    # -- Property for animation -----------------------------------------

    def get_opacity(self) -> float:
        return self._opacity

    def set_opacity(self, value: float) -> None:
        self._opacity = value
        self.update()

    opacity = Property(float, get_opacity, set_opacity)

    # -- Show / hide ----------------------------------------------------

    def show_overlay(self, valid: bool = True) -> None:
        self._is_valid = valid
        self.show()
        self.raise_()
        self.setGeometry(self.parent().rect())

        # Defer animation start to the main event loop — drag events on
        # Windows may arrive from a helper thread, and QPropertyAnimation
        # internally uses QTimer which must run on the GUI thread.
        QTimer.singleShot(0, self._start_show_animation)

    def _start_show_animation(self) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._opacity)
        self._animation.setEndValue(1.0)
        self._animation.start()

    def hide_overlay(self) -> None:
        QTimer.singleShot(0, self._start_hide_animation)

    def _start_hide_animation(self) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._opacity)
        self._animation.setEndValue(0.0)
        if self._hide_connected:
            self._animation.finished.disconnect(self._on_hide_finished)
            self._hide_connected = False
        self._animation.finished.connect(self._on_hide_finished)
        self._hide_connected = True
        self._animation.start()

    def _on_hide_finished(self) -> None:
        if self._hide_connected:
            self._animation.finished.disconnect(self._on_hide_finished)
            self._hide_connected = False
        if self._opacity <= 0.01:
            self.hide()

    # -- Paint ----------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._is_valid:
            bg = QColor(self._valid_bg)
            border = QColor(self._valid_border)
            pixmap = self._valid_pixmap
            text = None
        else:
            bg = QColor(self._invalid_bg)
            border = QColor(self._invalid_border)
            pixmap = self._invalid_pixmap
            text = self._invalid_text

        bg.setAlphaF(bg.alphaF() * self._opacity)
        border.setAlphaF(border.alphaF() * self._opacity)

        painter.fillRect(self.rect(), bg)

        pen = QPen(border, 2, Qt.PenStyle.DashLine)
        pen.setDashPattern([8, 4])
        painter.setPen(pen)
        margin = 16
        painter.drawRoundedRect(
            margin, margin,
            self.width() - 2 * margin,
            self.height() - 2 * margin,
            8, 8,
        )

        if pixmap and not pixmap.isNull():
            icon_size = pixmap.width()
            icon_x = (self.width() - icon_size) // 2
            icon_y = (self.height() // 2) - icon_size - 8 if text else (self.height() - icon_size) // 2
            painter.setOpacity(self._opacity)
            painter.drawPixmap(icon_x, icon_y, pixmap)
            painter.setOpacity(1.0)

        if text:
            text_color = QColor(border)
            text_color.setAlphaF(self._opacity)
            painter.setPen(text_color)
            fnt = QFont(self._font_family.split(",")[0].strip())
            fnt.setPixelSize(14)
            fnt.setWeight(QFont.Weight.Medium)
            painter.setFont(fnt)
            painter.drawText(
                self.rect().adjusted(0, 40, 0, 0),
                Qt.AlignmentFlag.AlignCenter,
                text,
            )


class DropZoneWidget(QWidget):
    """
    Base widget that accepts file drops.

    Emits ``file_dropped(path_str)`` on a valid drop.
    Use ``setup_drop_overlay()`` after child widgets are laid out.
    """

    file_dropped = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        valid_extensions: list[str] | None = None,
        allow_directories: bool = False,
    ):
        super().__init__(parent)
        self._valid_extensions = valid_extensions or []
        self._allow_directories = allow_directories
        self._drop_callback: Callable[[str], None] | None = None
        self._overlay: DropOverlay | None = None

        self.setAcceptDrops(True)

    def setup_drop_overlay(self) -> DropOverlay:
        """Create and return the overlay.  Call after layout is ready."""
        self._overlay = DropOverlay(self)
        self._overlay.setGeometry(self.rect())
        return self._overlay

    def set_drop_callback(self, callback: Callable[[str], None]) -> None:
        self._drop_callback = callback

    # -- Validation -----------------------------------------------------

    def _is_valid_drop(self, mime: QMimeData) -> bool:
        if not mime.hasUrls():
            return False
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            p = Path(url.toLocalFile())
            if p.is_dir():
                if self._allow_directories:
                    for ext in self._valid_extensions:
                        if list(p.glob(f"*{ext}")):
                            return True
                continue
            if not self._valid_extensions:
                return True
            if p.suffix.lower() in [e.lower() for e in self._valid_extensions]:
                return True
        return False

    def _find_target_file(self, mime: QMimeData) -> str | None:
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            p = Path(url.toLocalFile())
            if p.is_dir():
                for ext in self._valid_extensions:
                    files = list(p.glob(f"*{ext}"))
                    if files:
                        return str(files[0])
                continue
            if not self._valid_extensions:
                return str(p)
            if p.suffix.lower() in [e.lower() for e in self._valid_extensions]:
                return str(p)
        return None

    # -- Drag events ----------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            valid = self._is_valid_drop(event.mimeData())
            event.acceptProposedAction()
            if self._overlay:
                self._overlay.show_overlay(valid=valid)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        if self._overlay:
            self._overlay.hide_overlay()

    def dropEvent(self, event: QDropEvent) -> None:
        if self._overlay:
            self._overlay.hide_overlay()
        target = self._find_target_file(event.mimeData())
        if target:
            event.acceptProposedAction()
            self.file_dropped.emit(target)
            if self._drop_callback:
                self._drop_callback(target)
        else:
            event.ignore()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._overlay:
            self._overlay.setGeometry(self.rect())
