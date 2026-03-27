"""
Scrolling label widget that handles text overflow with animation.
Shows ellipsis when text is truncated, and scrolls on hover.
"""
from typing import Optional
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QFontMetrics, QPainter, QFont


class ScrollingLabel(QLabel):
    """
    Label that scrolls text on hover when it overflows.
    
    Features:
    - Shows ellipsis (...) when text is truncated
    - Smooth scrolling animation on hover
    - Resets position when mouse leaves
    """
    
    SCROLL_SPEED = 50  # pixels per second
    SCROLL_DELAY = 500  # ms before scrolling starts
    PADDING = 4  # extra pixels for smooth appearance
    
    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        
        self._full_text = text
        self._scroll_offset = 0.0
        self._text_width = 0
        self._is_overflowing = False
        
        # Animation
        self._animation = QPropertyAnimation(self, b"scrollOffset")
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        
        # Hover delay timer
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._start_scroll_animation)
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        
        # Clip text
        self.setTextFormat(Qt.TextFormat.PlainText)
    
    def _get_scroll_offset(self) -> float:
        return self._scroll_offset
    
    def _set_scroll_offset(self, value: float) -> None:
        self._scroll_offset = value
        self.update()
    
    scrollOffset = Property(float, _get_scroll_offset, _set_scroll_offset)
    
    def setText(self, text: str) -> None:
        """Set the label text."""
        self._full_text = text
        self._update_overflow_state()
        super().setText(text)
    
    def text(self) -> str:
        """Get the full text."""
        return self._full_text
    
    def resizeEvent(self, event) -> None:
        """Handle resize - recalculate overflow state."""
        super().resizeEvent(event)
        self._update_overflow_state()
    
    def _update_overflow_state(self) -> None:
        """Check if text overflows and update state."""
        fm = QFontMetrics(self.font())
        self._text_width = fm.horizontalAdvance(self._full_text)
        available_width = self.width() - self.contentsMargins().left() - self.contentsMargins().right()
        self._is_overflowing = self._text_width > available_width
    
    def enterEvent(self, event) -> None:
        """Start scroll animation after delay when mouse enters."""
        super().enterEvent(event)
        if self._is_overflowing:
            self._hover_timer.start(self.SCROLL_DELAY)
    
    def leaveEvent(self, event) -> None:
        """Reset scroll position when mouse leaves."""
        super().leaveEvent(event)
        self._hover_timer.stop()
        self._animation.stop()
        
        # Animate back to start
        if self._scroll_offset > 0:
            self._animation.setDuration(200)
            self._animation.setStartValue(self._scroll_offset)
            self._animation.setEndValue(0.0)
            self._animation.start()
    
    def _start_scroll_animation(self) -> None:
        """Start the scrolling animation."""
        if not self._is_overflowing:
            return
        
        available_width = self.width() - self.contentsMargins().left() - self.contentsMargins().right()
        scroll_distance = self._text_width - available_width + self.PADDING * 2
        
        if scroll_distance <= 0:
            return
        
        # Calculate duration based on speed
        duration = int((scroll_distance / self.SCROLL_SPEED) * 1000)
        
        self._animation.setDuration(duration)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(float(scroll_distance))
        self._animation.start()
    
    def paintEvent(self, event) -> None:
        """Custom paint to handle scrolling."""
        if not self._is_overflowing or self._scroll_offset == 0:
            # Default painting with ellipsis
            super().paintEvent(event)
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font())
        
        # Get text color from stylesheet (fallback to palette)
        color = self.palette().text().color()
        painter.setPen(color)
        
        # Calculate position
        margins = self.contentsMargins()
        x = margins.left() - int(self._scroll_offset)
        y = margins.top() + self.fontMetrics().ascent()
        
        # Draw text
        painter.drawText(x, y, self._full_text)
        painter.end()


class ElidedLabel(QLabel):
    """
    Label that elides text and shows full text in tooltip.
    Alternative to ScrollingLabel for static behavior.
    """
    
    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        elide_mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
    ):
        super().__init__(text, parent)
        self._full_text = text
        self._elide_mode = elide_mode
        self.setTextFormat(Qt.TextFormat.PlainText)
    
    def setText(self, text: str) -> None:
        """Set the label text."""
        self._full_text = text
        self._update_elided_text()
    
    def text(self) -> str:
        """Get the full text."""
        return self._full_text
    
    def resizeEvent(self, event) -> None:
        """Handle resize - recalculate elided text."""
        super().resizeEvent(event)
        self._update_elided_text()
    
    def _update_elided_text(self) -> None:
        """Update the displayed elided text."""
        fm = QFontMetrics(self.font())
        available_width = self.width() - self.contentsMargins().left() - self.contentsMargins().right()
        
        elided = fm.elidedText(self._full_text, self._elide_mode, available_width)
        super().setText(elided)
        
        # Set tooltip if text is elided
        if elided != self._full_text:
            self.setToolTip(self._full_text)
        else:
            self.setToolTip("")
