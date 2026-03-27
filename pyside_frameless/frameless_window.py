"""
Frameless window with native Aero Snap support.

Provides a QMainWindow subclass that removes the default window frame
and reimplements window management via:
- WM_NCHITTEST / WM_NCCALCSIZE on Windows for native snap/resize
- Cross-platform fallback using mouse events
- DPI-aware edge detection and resize
- Double-click title-bar maximize toggle

Subclass and call ``set_title_bar_widget`` to designate which widget
acts as the drag region.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QMainWindow, QWidget, QPushButton, QApplication
from PySide6.QtCore import Qt, QPoint, QRect, QEvent
from PySide6.QtGui import QCloseEvent

logger = logging.getLogger(__name__)

# Windows native constants
if sys.platform == "win32":
    HTCLIENT = 1
    HTCAPTION = 2
    HTLEFT = 10
    HTRIGHT = 11
    HTTOP = 12
    HTTOPLEFT = 13
    HTTOPRIGHT = 14
    HTBOTTOM = 15
    HTBOTTOMLEFT = 16
    HTBOTTOMRIGHT = 17
    WM_NCHITTEST = 0x0084
    WM_NCCALCSIZE = 0x0083


class FramelessWindow(QMainWindow):
    """
    A frameless QMainWindow with native Aero Snap on Windows
    and cross-platform fallback resize handling.

    Usage::

        class MyWindow(FramelessWindow):
            def __init__(self):
                super().__init__()
                header = self._build_header()
                self.set_title_bar_widget(header)

    Override ``on_maximize_changed(is_maximized: bool)`` to update
    your maximize button icon when the state changes.
    """

    RESIZE_MARGIN = 8

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # Title-bar widget registered externally
        self._title_bar: QWidget | None = None

        # Fallback resize state (non-Windows)
        self._resize_edge: str | None = None
        self._resize_start_pos: QPoint | None = None
        self._resize_start_geometry: QRect | None = None

        # Manual maximize tracking
        self._maximized_state: bool = False
        self._normal_geometry: QRect | None = None

        self._apply_frameless_flags()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_title_bar_widget(self, widget: QWidget) -> None:
        """Designate *widget* as the title bar (drag region)."""
        self._title_bar = widget

    def toggle_maximize(self) -> None:
        """Toggle between maximized and normal window state."""
        if sys.platform == "win32":
            import ctypes

            SW_MAXIMIZE = 3
            SW_RESTORE = 9
            hwnd = int(self.winId())

            if self._maximized_state:
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)

                if self._normal_geometry and self._normal_geometry.isValid():
                    screen = QApplication.screenAt(self.geometry().center())
                    if not screen:
                        screen = QApplication.primaryScreen()
                    if screen:
                        sg = screen.availableGeometry()
                        w = min(self._normal_geometry.width(), sg.width())
                        h = min(self._normal_geometry.height(), sg.height())
                        x = sg.x() + (sg.width() - w) // 2
                        y = sg.y() + (sg.height() - h) // 2
                        self.setGeometry(x, y, w, h)
            else:
                ctypes.windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)
        else:
            if self._maximized_state:
                self.showNormal()
                if self._normal_geometry and self._normal_geometry.isValid():
                    self.setGeometry(self._normal_geometry)
                self._maximized_state = False
            else:
                self._maximized_state = True
                self.showMaximized()
            self.on_maximize_changed(self._maximized_state)

    def on_maximize_changed(self, is_maximized: bool) -> None:
        """Override to react to maximize state changes (e.g. update icon)."""

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _apply_frameless_flags(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # Show / Aero Snap setup
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._normal_geometry is None:
            self._normal_geometry = self.geometry()
        if sys.platform == "win32":
            self._setup_windows_aero_snap()

    def _setup_windows_aero_snap(self) -> None:
        try:
            import ctypes

            GWL_STYLE = -16
            WS_THICKFRAME = 0x00040000
            WS_MINIMIZEBOX = 0x00020000
            WS_MAXIMIZEBOX = 0x00010000
            WS_SYSMENU = 0x00080000

            hwnd = int(self.winId())
            style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
            style |= WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
            ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)

            SWP_FRAMECHANGED = 0x0020
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            ctypes.windll.user32.SetWindowPos(
                hwnd, None, 0, 0, 0, 0,
                SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER,
            )
        except Exception as e:
            logger.warning("Failed to setup Windows Aero Snap: %s", e)

    # ------------------------------------------------------------------
    # Resize edge helpers
    # ------------------------------------------------------------------

    def _get_resize_edge(self, pos: QPoint) -> str | None:
        if self.windowState() & Qt.WindowState.WindowMaximized:
            return None

        rect = self.rect()
        m = self.RESIZE_MARGIN

        left = pos.x() < m
        right = pos.x() > rect.width() - m
        top = pos.y() < m
        bottom = pos.y() > rect.height() - m

        if top and left:
            return "top-left"
        if top and right:
            return "top-right"
        if bottom and left:
            return "bottom-left"
        if bottom and right:
            return "bottom-right"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return None

    def _update_cursor_for_edge(self, edge: str | None) -> None:
        cursor_map = {
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "top-left": Qt.CursorShape.SizeFDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
        }
        if edge in cursor_map:
            self.setCursor(cursor_map[edge])
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------
    # Mouse events (fallback resize)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._get_resize_edge(event.pos())
            if edge:
                self._resize_edge = edge
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geometry = self.geometry()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._resize_edge and self._resize_start_pos and self._resize_start_geometry:
            diff = event.globalPosition().toPoint() - self._resize_start_pos
            geo = QRect(self._resize_start_geometry)
            min_w, min_h = self.minimumWidth(), self.minimumHeight()

            if "left" in self._resize_edge:
                new_w = geo.width() - diff.x()
                if new_w >= min_w:
                    geo.setX(geo.x() + diff.x())
                    geo.setWidth(new_w)
                else:
                    geo.setWidth(min_w)
                    geo.setX(self._resize_start_geometry.right() - min_w + 1)

            if "right" in self._resize_edge:
                new_w = geo.width() + diff.x()
                geo.setWidth(max(new_w, min_w))

            if "top" in self._resize_edge:
                new_h = geo.height() - diff.y()
                if new_h >= min_h:
                    geo.setY(geo.y() + diff.y())
                    geo.setHeight(new_h)
                else:
                    geo.setHeight(min_h)
                    geo.setY(self._resize_start_geometry.bottom() - min_h + 1)

            if "bottom" in self._resize_edge:
                new_h = geo.height() + diff.y()
                geo.setHeight(max(new_h, min_h))

            self.setGeometry(geo)
        else:
            edge = self._get_resize_edge(event.pos())
            self._update_cursor_for_edge(edge)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._resize_edge = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._title_bar and self._title_bar.geometry().contains(event.pos()):
                self.toggle_maximize()
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    # Native event handling (Windows)
    # ------------------------------------------------------------------

    def nativeEvent(self, eventType, message):
        if sys.platform != "win32":
            return super().nativeEvent(eventType, message)
        if eventType != b"windows_generic_MSG":
            return super().nativeEvent(eventType, message)

        try:
            import ctypes
            from ctypes import wintypes

            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("message", wintypes.UINT),
                    ("wParam", wintypes.WPARAM),
                    ("lParam", wintypes.LPARAM),
                    ("time", wintypes.DWORD),
                    ("pt", wintypes.POINT),
                ]

            msg = MSG.from_address(int(message))

            if msg.message == WM_NCCALCSIZE:
                return True, 0

            if msg.message == WM_NCHITTEST:
                x_phys = msg.lParam & 0xFFFF
                y_phys = (msg.lParam >> 16) & 0xFFFF
                if x_phys > 32767:
                    x_phys -= 65536
                if y_phys > 32767:
                    y_phys -= 65536

                dpr = self.devicePixelRatio()
                x_logical = int(x_phys / dpr)
                y_logical = int(y_phys / dpr)

                widget_at_pos = QApplication.widgetAt(x_logical, y_logical)
                if widget_at_pos is not None:
                    w_check = widget_at_pos
                    while w_check is not None and w_check is not self:
                        if isinstance(w_check, QPushButton):
                            return True, HTCLIENT
                        w_check = w_check.parentWidget()

                hwnd = int(self.winId())
                rect = wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))

                rel_x = x_phys - rect.left
                rel_y = y_phys - rect.top
                w = rect.right - rect.left
                h = rect.bottom - rect.top

                border = int(8 * dpr)
                title_height = int(40 * dpr) if self._title_bar else int(8 * dpr)

                is_maximized = bool(self.windowState() & Qt.WindowState.WindowMaximized)

                if not is_maximized:
                    if rel_x < border and rel_y < border:
                        return True, HTTOPLEFT
                    if rel_x > w - border and rel_y < border:
                        return True, HTTOPRIGHT
                    if rel_x < border and rel_y > h - border:
                        return True, HTBOTTOMLEFT
                    if rel_x > w - border and rel_y > h - border:
                        return True, HTBOTTOMRIGHT
                    if rel_x < border:
                        return True, HTLEFT
                    if rel_x > w - border:
                        return True, HTRIGHT
                    if rel_y < border:
                        return True, HTTOP
                    if rel_y > h - border:
                        return True, HTBOTTOM

                if rel_y < title_height:
                    return True, HTCAPTION

                return True, HTCLIENT

        except Exception as e:
            logger.warning("nativeEvent error: %s", e)

        return super().nativeEvent(eventType, message)

    # ------------------------------------------------------------------
    # Window state tracking
    # ------------------------------------------------------------------

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            old_state = event.oldState() if hasattr(event, "oldState") else Qt.WindowState.WindowNoState
            new_state = self.windowState()
            self._maximized_state = bool(new_state & Qt.WindowState.WindowMaximized)
            self.on_maximize_changed(self._maximized_state)
        super().changeEvent(event)

    def moveEvent(self, event) -> None:
        if not (self.windowState() & Qt.WindowState.WindowMaximized):
            self._normal_geometry = self.geometry()
        super().moveEvent(event)

    def resizeEvent(self, event) -> None:
        if not (self.windowState() & Qt.WindowState.WindowMaximized):
            self._normal_geometry = self.geometry()
        super().resizeEvent(event)
